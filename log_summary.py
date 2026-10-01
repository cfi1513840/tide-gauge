#!/usr/bin/env python3
"""log_summary.py -- summarize the warnings and errors in newtide.log.

Sorts each warning/error (with its traceback, if any) from the last N
hours into routine categories -- network glitches, sensor reporting
gaps, rejected outliers, garbled radio packets -- and things that need
a look: errors in the code itself, local database trouble, and
network outages that went on for a long time. Also checks that tide.py
is running and that new readings are still arriving.

Usage, on a station:
    python3 log_summary.py [--hours 24] [--verbose]
or from the development PC, without installing anything on the station
(this is what tidelogs.ps1 -Summary does):
    ssh tide@ssh.<domain> python3 - --hours 24 < log_summary.py

Exit status: 0 nothing flagged, 1 something flagged, 2 could not read
the log.

Standard library only, and Python 3.9 compatible (bbitide).
"""
import argparse
import glob
import gzip
import os
import re
import sqlite3
from datetime import datetime, timedelta

LOG_DEFAULT = '/home/tide/bin/tidegauge/newtide.log'

# Thresholds for flagging routine categories. Per window, which is 24 h
# unless --hours says otherwise; they scale with the window.
NETWORK_EPISODE_GAP_MIN = 20    # errors closer than this are one episode
NETWORK_LONG_EPISODE_MIN = 60   # an episode at least this long is flagged
LOCAL_DB_ERRORS_FLAG = 3        # local InfluxDB (127.0.0.1:8181) problems
SENSOR_GAP_TOTAL_FLAG_MIN = 120 # one sensor's reporting gaps, added up
OUTLIERS_FLAG = 20              # rejected readings for one sensor
GARBLED_FLAG = 60               # garbled LoRa packets
READING_STALE_MIN = 30          # newest reading in tides.db older than this

ENTRY = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ \[(\w+)\] ?(.*)$')
EXC_LINE = re.compile(r'^([A-Za-z_][\w.]*(?:Error|Exception|Timeout|Exit|Interrupt|timeout))(?::\s*(.*))?$')
TIDE_FRAME = re.compile(r'File "[^"]*/tidegauge/([\w.]+)", line (\d+), in (\w+)')

CODE_ERRORS = {
    'TypeError', 'AttributeError', 'KeyError', 'NameError', 'IndexError',
    'ValueError', 'ZeroDivisionError', 'UnboundLocalError', 'ImportError',
    'ModuleNotFoundError', 'AssertionError', 'RecursionError', 'SyntaxError',
    'JSONDecodeError', 'json.decoder.JSONDecodeError', 'UnicodeDecodeError',
    'UnicodeEncodeError', 'OverflowError',
}
SYSTEM_PATTERNS = re.compile(
    r'sqlite3\.|database is locked|disk I/O error|No space left|'
    r'PermissionError|Permission denied|MemoryError|Read-only file system|'
    r'FileNotFoundError|No such file', re.I)
NETWORK_PATTERNS = re.compile(
    r'name resolution|NameResolution|gaierror|getaddrinfo|timed out|Timeout|'
    r'Connection\w*Error|Connection (?:reset|refused|aborted)|'
    r'Max retries exceeded|RemoteDisconnected|Network is unreachable|'
    r'No route to host|SSLError|SSL:|EOF occurred|IncompleteRead|'
    r'ProtocolError|ChunkedEncodingError|\b429\b|Too Many Requests|'
    r'\b50[0234]\b|Bad Gateway|Service Unavailable|Gateway Time-?out|'
    r'SMTPServerDisconnected|SMTPConnectError', re.I)
LOCAL_DB_PATTERNS = re.compile(r'127\.0\.0\.1|localhost|:8181\b')
GAP = re.compile(r'sensor (\w+) reporting gap of (\d+)s')
ALERT_GAP = re.compile(r'check_alerts: reporting gap of (\d+)s')
OUTLIER = re.compile(r'rejecting outlier for sensor (\w+)')
INVALID_TIDE = re.compile(r'invalid tide level')
GARBLED = re.compile(r'garbled|incomplete/garbled|Discarding incomplete', re.I)


def log_files(path, hours):
    """The current log plus enough rotated ones to cover the window,
    oldest first. Rotation is daily at midnight."""
    days = int(hours // 24) + 2
    files = []
    for n in range(days, 0, -1):
        for cand in (f'{path}.{n}', f'{path}.{n}.gz'):
            if os.path.exists(cand):
                files.append(cand)
    if os.path.exists(path):
        files.append(path)
    return files


def read_entries(files):
    entries = []
    current = None
    for name in files:
        opener = gzip.open if name.endswith('.gz') else open
        with opener(name, 'rt', encoding='utf-8', errors='replace') as f:
            for raw in f:
                line = raw.rstrip('\n').replace('\x00', '')
                m = ENTRY.match(line)
                if m:
                    current = {
                        'time': datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S'),
                        'level': m.group(2), 'msg': m.group(3), 'extra': []}
                    entries.append(current)
                elif current is not None:
                    current['extra'].append(line)
    return entries


def exception_of(entry):
    """(exception type, its message, deepest tidegauge frame) from the
    entry's traceback, or (None, None, None)."""
    exc_type = exc_msg = where = None
    for line in entry['extra']:
        if line and not line[0].isspace():
            m = EXC_LINE.match(line)
            if m:
                exc_type, exc_msg = m.group(1), (m.group(2) or '')
        m = TIDE_FRAME.search(line)
        if m:
            where = f'{m.group(1)}:{m.group(2)} in {m.group(3)}'
    return exc_type, exc_msg, where


def normalize(text):
    text = re.sub(r'0x[0-9a-fA-F]+', '#', text)
    text = re.sub(r'\d+(\.\d+)?', '#', text)
    return text[:160]


def classify(entry):
    exc_type, exc_msg, where = exception_of(entry)
    short_type = exc_type.rsplit('.', 1)[-1] if exc_type else None
    text = ' '.join([entry['msg'], exc_type or '', exc_msg or ''])
    if short_type in CODE_ERRORS or exc_type in CODE_ERRORS:
        return 'code', exc_type, exc_msg, where
    if 'unsupported operand' in text or 'object has no attribute' in text:
        return 'code', exc_type, exc_msg, where
    if SYSTEM_PATTERNS.search(text) and not NETWORK_PATTERNS.search(text):
        return 'system', exc_type, exc_msg, where
    if NETWORK_PATTERNS.search(text) or (exc_type and 'urllib3' in exc_type):
        if LOCAL_DB_PATTERNS.search(text):
            return 'localdb', exc_type, exc_msg, where
        return 'network', exc_type, exc_msg, where
    if GAP.search(text) or ALERT_GAP.search(text):
        return 'gap', exc_type, exc_msg, where
    if OUTLIER.search(text) or INVALID_TIDE.search(text):
        return 'outlier', exc_type, exc_msg, where
    if GARBLED.search(text):
        return 'garbled', exc_type, exc_msg, where
    return 'other', exc_type, exc_msg, where


def network_target(entry, exc_msg):
    text = entry['msg'] + ' ' + (exc_msg or '') + ' ' + ' '.join(entry['extra'][-3:])
    m = re.search(r"host='([^']+)'", text) or re.search(r'https?://([^/\s:]+)', text)
    if m:
        host = m.group(1)
        if 'influxdata' in host:
            return 'InfluxDB Cloud'
        if 'brevo' in host or 'smtp' in host:
            return 'email (Brevo)'
        if 'twilio' in host:
            return 'SMS (Twilio)'
        if 'ndbc' in host or 'noaa' in host:
            return 'NOAA/NDBC'
        if 'weather' in host or 'openweathermap' in host or 'wunderground' in host:
            return 'weather service'
        return host
    low = text.lower()
    for key, label in (('cloud', 'InfluxDB Cloud'), ('smtp', 'email (Brevo)'),
                       ('email', 'email (Brevo)'), ('sms', 'SMS (Twilio)'),
                       ('ndbc', 'NOAA/NDBC'), ('weather', 'weather service'),
                       ('notehub', 'Notehub')):
        if key in low:
            return label
    return 'unknown host'


def episodes(times):
    """Group times into episodes (gaps under NETWORK_EPISODE_GAP_MIN)."""
    out = []
    for t in sorted(times):
        if out and (t - out[-1][1]) <= timedelta(minutes=NETWORK_EPISODE_GAP_MIN):
            out[-1][1] = t
            out[-1][2] += 1
        else:
            out.append([t, t, 1])
    return out


def tide_process():
    found = []
    for d in glob.glob('/proc/[0-9]*'):
        try:
            with open(os.path.join(d, 'cmdline'), 'rb') as f:
                argv = f.read().decode('utf-8', 'replace').split('\x00')
        except OSError:
            continue
        # The program itself must be Python, and one of its arguments
        # tide.py or tidemonitor.py -- so a shell that merely mentions
        # tide.py in its command line doesn't count.
        if (argv and os.path.basename(argv[0]).startswith('python') and
                any(os.path.basename(a) in ('tide.py', 'tidemonitor.py') for a in argv[1:])):
            found.append((os.path.basename(d), ' '.join(argv).strip()))
    return found


def newest_reading(log_path):
    env = os.path.join(os.path.dirname(log_path), 'tide.env')
    db = '/var/www/html/tides.db'
    try:
        with open(env) as f:
            for line in f:
                m = re.match(r"\s*SQL_PATH\s*=\s*['\"]?([^'\"\s]+)", line)
                if m:
                    db = m.group(1)
    except OSError:
        pass
    if not os.path.exists(db):
        return None, f'database {db} not found'
    try:
        con = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=5)
        row = con.execute('select max(dtime) from sensors').fetchone()
        con.close()
    except sqlite3.Error as e:
        return None, f'could not read {db}: {e}'
    if not row or not row[0]:
        return None, f'no readings in {db}'
    try:
        return datetime.strptime(str(row[0])[:19], '%Y-%m-%d %H:%M:%S'), None
    except ValueError:
        return None, f'unrecognized time {row[0]!r} in {db}'


def fmt_min(seconds):
    m = int(round(seconds / 60))
    return f'{m // 60} h {m % 60} min' if m >= 60 else f'{m} min'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--hours', type=float, default=24)
    ap.add_argument('--log', default=LOG_DEFAULT)
    ap.add_argument('--verbose', action='store_true',
                    help='list every distinct message, not just the flagged ones')
    args = ap.parse_args()

    now = datetime.now()
    start = now - timedelta(hours=args.hours)
    scale = args.hours / 24.0
    files = log_files(args.log, args.hours)
    if not files:
        print(f'  ! cannot find {args.log}')
        return 2
    entries = [e for e in read_entries(files)
               if e['time'] >= start and e['level'] in ('WARNING', 'ERROR', 'CRITICAL')]

    flags, routine = [], []

    # --- is it running, and is data arriving? ---
    procs = tide_process()
    if procs:
        running = ', '.join(f'{c.split()[-1].rsplit("/", 1)[-1]} (pid {p})' for p, c in procs)
        status_line = f'running: {running}'
        if len([c for p, c in procs if c.endswith('tide.py')]) > 1:
            flags.append('more than one tide.py is running -- they will compete for port 8088 and the sensors')
    else:
        status_line = 'tide.py is NOT running'
        flags.append('tide.py is not running')
    newest, err = newest_reading(args.log)
    if err:
        flags.append(err)
    else:
        age = (now - newest).total_seconds()
        status_line += f'; newest reading {fmt_min(max(age, 0))} ago'
        if age > READING_STALE_MIN * 60:
            flags.append(f'newest reading in tides.db is {fmt_min(age)} old ({newest:%Y-%m-%d %H:%M})')

    # --- sort the log entries ---
    groups = {}
    net_times, net_targets = [], {}
    gap_by_sensor, outliers_by_sensor = {}, {}
    alert_gaps = 0
    garbled = 0
    for e in entries:
        cat, exc_type, exc_msg, where = classify(e)
        if cat == 'network':
            net_times.append(e['time'])
            tgt = network_target(e, exc_msg)
            net_targets[tgt] = net_targets.get(tgt, 0) + 1
        elif cat == 'gap':
            m = GAP.search(e['msg'])
            if m:
                s = gap_by_sensor.setdefault(m.group(1), [0, 0, 0])
                s[0] += 1
                s[1] += int(m.group(2))
                s[2] = max(s[2], int(m.group(2)))
            else:
                alert_gaps += 1
        elif cat == 'outlier':
            m = OUTLIER.search(e['msg'])
            key = m.group(1) if m else 'active station (alerts)'
            outliers_by_sensor[key] = outliers_by_sensor.get(key, 0) + 1
        elif cat == 'garbled':
            garbled += 1
        if cat in ('code', 'system', 'localdb', 'other') or args.verbose:
            if exc_type:
                label = f'{exc_type}: {exc_msg}'.strip()
            else:
                label = e['msg']
            key = (cat, normalize(label), where)
            g = groups.setdefault(key, {'count': 0, 'first': e['time'], 'last': e['time'],
                                        'label': label, 'msg': e['msg']})
            g['count'] += 1
            g['last'] = e['time']

    titles = {'code': 'Code error', 'system': 'System/database error',
              'localdb': 'Local InfluxDB problem', 'other': 'Unclassified',
              'network': 'Network', 'gap': 'Sensor gap', 'outlier': 'Outlier',
              'garbled': 'Garbled packet'}
    for (cat, _, where), g in sorted(groups.items(), key=lambda kv: kv[1]['last']):
        when = (f"{g['last']:%m-%d %H:%M}" if g['count'] == 1 else
                f"{g['first']:%m-%d %H:%M} .. {g['last']:%m-%d %H:%M}")
        text = f"{titles[cat]} x{g['count']} ({when}): {g['label'][:140]}"
        if where:
            text += f'  [at {where}]'
        if cat in ('code', 'system', 'other') or (
                cat == 'localdb' and g['count'] >= LOCAL_DB_ERRORS_FLAG * scale):
            flags.append(text)
        elif cat == 'localdb' or args.verbose:
            routine.append(text)

    # --- routine categories, flagged only past their thresholds ---
    if net_times:
        eps = episodes(net_times)
        longest = max(eps, key=lambda x: x[1] - x[0])
        longest_s = (longest[1] - longest[0]).total_seconds()
        tgts = ', '.join(f'{k} {v}' for k, v in sorted(net_targets.items(), key=lambda kv: -kv[1]))
        text = (f'Network errors x{len(net_times)} in {len(eps)} episode(s), longest '
                f'{fmt_min(longest_s)} ({longest[0]:%m-%d %H:%M}); {tgts}')
        if longest_s >= NETWORK_LONG_EPISODE_MIN * 60:
            flags.append(text + ' -- long outage')
        else:
            routine.append(text)
        if (now - max(net_times)) <= timedelta(minutes=NETWORK_EPISODE_GAP_MIN):
            routine.append(f'  (network errors still occurring: last at {max(net_times):%H:%M})')
    for sensor, (n, total, mx) in sorted(gap_by_sensor.items()):
        text = (f'Sensor {sensor}: {n} reporting gap(s) over 5 min, '
                f'{fmt_min(total)} in all, longest {fmt_min(mx)}')
        (flags if total >= SENSOR_GAP_TOTAL_FLAG_MIN * 60 * scale else routine).append(text)
    if alert_gaps:
        routine.append(f'Alert check: {alert_gaps} reporting gap(s) on the active station')
    for sensor, n in sorted(outliers_by_sensor.items()):
        text = f'Sensor {sensor}: {n} reading(s) rejected as outliers'
        (flags if n >= OUTLIERS_FLAG * scale else routine).append(text)
    if garbled:
        text = f'Garbled LoRa packets discarded: {garbled}'
        (flags if garbled >= GARBLED_FLAG * scale else routine).append(text)

    # --- report ---
    span = f'last {args.hours:g} h'
    print(f"  {'ATTENTION' if flags else 'OK'} -- {status_line}")
    print(f'  {len(entries)} warning/error entries in the {span}')
    for f in flags:
        print(f'  ! {f}')
    for r in routine:
        print(f'    {r}')
    if not flags and not routine:
        print('    (nothing logged)')
    return 1 if flags else 0


if __name__ == '__main__':
    raise SystemExit(main())
