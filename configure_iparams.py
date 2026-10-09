#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""configure_iparams.py

Interactively configures the iparams table of a freshly-copied tides.db
for a new station: which sensors (1-3) are installed, each one's
calibration value, and which sensor serves as the primary station
display (stationid). Each sensor's type (lora/note/cloud) is set in
tide.env as STATION<n>_TYPE, not here. Meant to run once, immediately after
tides.db is first copied into place for a fresh install -- not meant to
be re-run against an already-configured, in-service database, since it
overwrites every station-specific iparams field unconditionally.

Usage: python3 configure_iparams.py <path-to-tides.db>
"""
import sqlite3
import sys

if len(sys.argv) != 2:
    print("Usage: configure_iparams.py <path-to-tides.db>")
    sys.exit(1)

db_path = sys.argv[1]

print("Configuring station sensors for this installation.")
print()

sensors = {}
for n in (1, 2, 3):
    while True:
        answer = input(f"Is sensor {n} installed at this station? Y/N: ").strip().lower()
        if answer in ('y', 'n'):
            break
        print("Please answer Y or N.")
    if answer == 'n':
        sensors[n] = {'enable': 0, 'cal': None}
        continue
    while True:
        cal_raw = input(f"  Sensor {n} calibration value (e.g. 14.08): ").strip()
        try:
            cal = float(cal_raw)
            break
        except ValueError:
            print("  Please enter a number.")
    sensors[n] = {'enable': 1, 'cal': cal}

installed = [n for n in (1, 2, 3) if sensors[n]['enable'] == 1]
if not installed:
    print()
    print("No sensors marked as installed -- stationid will default to 1.")
    stationid = 1
elif len(installed) == 1:
    stationid = installed[0]
    print(f"\nSensor {stationid} is the only one installed; using it as the "
          f"primary station display.")
else:
    choices = '/'.join(str(n) for n in installed)
    while True:
        raw = input(f"\nWhich sensor should be the primary station display? "
                     f"({choices}): ").strip()
        if raw.isdigit() and int(raw) in installed:
            stationid = int(raw)
            break
        print(f"  Please enter one of: {', '.join(str(n) for n in installed)}")

con = sqlite3.connect(db_path)
cur = con.cursor()
# The s<n>type columns are no longer used (types are in tide.env); on
# an older database they're left as they are (drop_iparams_types.py
# removes them).
cur.execute(
    "UPDATE iparams SET stationid=?, "
    "station1cal=?, s1enable=?, "
    "station2cal=?, s2enable=?, "
    "station3cal=?, s3enable=?",
    (
        stationid,
        sensors[1]['cal'], sensors[1]['enable'],
        sensors[2]['cal'], sensors[2]['enable'],
        sensors[3]['cal'], sensors[3]['enable'],
    )
)
if cur.rowcount == 0:
    # iparams was genuinely empty (no starter row to update) -- insert one.
    cur.execute(
        "INSERT INTO iparams (stationid, "
        "station1cal, s1enable, "
        "station2cal, s2enable, "
        "station3cal, s3enable) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            stationid,
            sensors[1]['cal'], sensors[1]['enable'],
            sensors[2]['cal'], sensors[2]['enable'],
            sensors[3]['cal'], sensors[3]['enable'],
        )
    )
con.commit()
con.close()

print()
print(f"iparams updated: stationid={stationid}")
for n in (1, 2, 3):
    s = sensors[n]
    if s['enable']:
        print(f"  sensor {n}: enabled, cal={s['cal']}")
    else:
        print(f"  sensor {n}: disabled")
print("Set each installed sensor's type (lora, note or cloud) in tide.env "
      "as STATION<n>_TYPE.")
