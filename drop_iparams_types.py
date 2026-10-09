#!/usr/bin/env python3
"""drop_iparams_types.py

Removes the s1type, s2type and s3type columns from the iparams table
in tides.db. The sensor slot types now live in tide.env
(STATION<n>_TYPE), so these columns are no longer used.

The table is rebuilt: a new table is created with every other column,
in the same order and with the same declared types, the rows are copied
across, the old table is dropped and the new one renamed to iparams.
Column order is kept because tideplot.py reads iparams by position.
All of it runs in one transaction, so the table is either fully
rebuilt or left exactly as it was.

Run it with tide.py stopped:

    sudo systemctl stop tide          (or however tide.py is stopped)
    python3 drop_iparams_types.py
    sudo systemctl start tide

Before changing anything it:
  - stops if tide.py appears to be running (override with --force)
  - stops if tide.env is missing any STATION<n>_TYPE line, since tide.py
    would then have nothing to fall back to
  - shows the current s<n>type values beside tide.env's STATION<n>_TYPE
    and stops if they differ (override with --force)
  - writes a backup copy of the database beside it
    (tides.db.bak-YYYYmmdd-HHMMSS)

Options:
    [db_path]     database to change; default SQL_PATH from tide.env,
                  else /var/www/html/tides.db
    --env PATH    tide.env to check; default the one beside this script
    --dry-run     show what would be done and change nothing
    --force       skip the tide.py-running and type-mismatch checks
    --no-backup   don't write the backup copy

Running it again after the columns are gone does nothing.
"""
import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

DROP = ('s1type', 's2type', 's3type')
DEFAULT_DB = '/var/www/html/tides.db'


def read_env(path):
    """tide.env as {name: value}, quotes stripped; {} if unreadable."""
    values = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                name, value = line.split('=', 1)
                values[name.strip()] = value.strip().strip('\'"')
    except OSError:
        return {}
    return values


def tide_py_running():
    try:
        r = subprocess.run(['pgrep', '-f', r'python.*tide\.py'],
                           capture_output=True, text=True)
    except FileNotFoundError:
        return False
    return r.returncode == 0


def main():
    here = os.path.dirname(os.path.realpath(__file__))
    ap = argparse.ArgumentParser(
      description='Remove s1type/s2type/s3type from the iparams table.')
    ap.add_argument('db_path', nargs='?')
    ap.add_argument('--env', default=os.path.join(here, 'tide.env'))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--no-backup', action='store_true')
    args = ap.parse_args()

    env = read_env(args.env)
    db_path = args.db_path or env.get('SQL_PATH') or DEFAULT_DB
    print(f'Database: {db_path}')
    if not os.path.isfile(db_path):
        sys.exit(f'No such database file: {db_path}')

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    # (cid, name, type, notnull, dflt_value, pk)
    cols = cur.execute("PRAGMA table_info('iparams')").fetchall()
    if not cols:
        sys.exit('The database has no iparams table.')
    present = [c[1] for c in cols if c[1] in DROP]
    if not present:
        print('iparams has no s<n>type columns; nothing to do.')
        return 0
    keep = [c for c in cols if c[1] not in DROP]

    # Anything else attached to iparams would be lost in the rebuild.
    attached = cur.execute(
      "SELECT type, name FROM sqlite_master "
      "WHERE tbl_name = 'iparams' AND type IN ('index', 'trigger')"
    ).fetchall()
    if attached:
        sys.exit('iparams has indexes or triggers this script does not '
                 f'recreate: {attached}. Nothing changed.')

    # Current values beside tide.env's.
    row = cur.execute(
      f"SELECT {', '.join(present)} FROM iparams LIMIT 1").fetchone()
    db_types = dict(zip(present, row)) if row else {}
    print(f'tide.env: {args.env}' + ('' if env else '  (not found)'))
    missing, differ = [], []
    for n in (1, 2, 3):
        col = f's{n}type'
        env_val = env.get(f'STATION{n}_TYPE')
        db_val = db_types.get(col)
        db_show = '' if db_val is None else str(db_val).strip().lower()
        env_show = '(missing)' if env_val is None else repr(env_val.lower())
        print(f'  slot {n}:  iparams {col} = {db_show!r:9}  '
              f'tide.env STATION{n}_TYPE = {env_show}')
        if env_val is None:
            missing.append(n)
        elif env_val.strip().lower() != db_show:
            differ.append(n)
    if missing:
        sys.exit(f'tide.env has no STATION<n>_TYPE for slot(s) {missing}. '
                 'Add them before removing the iparams columns. '
                 'Nothing changed.')
    if differ:
        msg = (f'Slot(s) {differ} differ between iparams and tide.env. '
               'tide.py already uses tide.env, so this only matters if '
               'tide.env is wrong.')
        if not args.force:
            sys.exit(msg + ' Check tide.env, or rerun with --force. '
                     'Nothing changed.')
        print('Warning: ' + msg)

    if tide_py_running() and not args.force:
        sys.exit('tide.py appears to be running. Stop it first, or rerun '
                 'with --force. Nothing changed.')

    nrows = cur.execute('SELECT COUNT(*) FROM iparams').fetchone()[0]

    def coldef(c):
        _, name, ctype, notnull, dflt, pk = c
        d = f'"{name}"' + (f' {ctype}' if ctype else '')
        if notnull:
            d += ' NOT NULL'
        if dflt is not None:
            d += f' DEFAULT {dflt}'
        return d

    pks = [c for c in keep if c[5]]
    defs = [coldef(c) for c in keep]
    if pks:
        defs.append('PRIMARY KEY (' + ', '.join(
          f'"{c[1]}"' for c in sorted(pks, key=lambda c: c[5])) + ')')
    names = ', '.join(f'"{c[1]}"' for c in keep)
    create = f'CREATE TABLE iparams_new ({", ".join(defs)})'
    copy = f'INSERT INTO iparams_new ({names}) SELECT {names} FROM iparams'

    print(f'Removing column(s): {", ".join(present)}')
    print(f'Keeping {len(keep)} column(s), {nrows} row(s):')
    print('  ' + ', '.join(c[1] for c in keep))
    if args.dry_run:
        print('Dry run; would execute:')
        for sql in (create, copy, 'DROP TABLE iparams',
                    'ALTER TABLE iparams_new RENAME TO iparams'):
            print('  ' + sql)
        return 0

    if not args.no_backup:
        backup = db_path + '.bak-' + datetime.now().strftime('%Y%m%d-%H%M%S')
        dst = sqlite3.connect(backup)
        con.backup(dst)
        dst.close()
        try:
            st = os.stat(db_path)
            os.chown(backup, st.st_uid, st.st_gid)
            os.chmod(backup, st.st_mode & 0o777)
        except OSError:
            pass
        print(f'Backup: {backup}')

    con.isolation_level = None          # explicit transaction below
    try:
        cur.execute('BEGIN IMMEDIATE')
        cur.execute('DROP TABLE IF EXISTS iparams_new')
        cur.execute(create)
        cur.execute(copy)
        copied = cur.execute('SELECT COUNT(*) FROM iparams_new').fetchone()[0]
        if copied != nrows:
            raise RuntimeError(f'copied {copied} rows, expected {nrows}')
        cur.execute('DROP TABLE iparams')
        cur.execute('ALTER TABLE iparams_new RENAME TO iparams')
        cur.execute('COMMIT')
    except Exception as err:
        cur.execute('ROLLBACK')
        sys.exit(f'Failed, nothing changed: {err}')

    after = [c[1] for c in cur.execute("PRAGMA table_info('iparams')")]
    check = cur.execute('PRAGMA integrity_check').fetchone()[0]
    con.close()
    print(f'Done. iparams columns now: {", ".join(after)}')
    print(f'Integrity check: {check}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
