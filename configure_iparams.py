#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""configure_iparams.py

Interactively configures the iparams table of a freshly-copied tides.db
for a new station: which sensors (1-3) are installed, each one's LoRa or
Notecard link type and calibration value, and which sensor serves as the
primary station display (stationid). Meant to run once, immediately after
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
        sensors[n] = {'enable': 0, 'type': None, 'cal': None}
        continue
    while True:
        link_type = input(f"  Sensor {n} link type -- lora or note: ").strip().lower()
        if link_type in ('lora', 'note'):
            break
        print("  Please enter 'lora' or 'note'.")
    while True:
        cal_raw = input(f"  Sensor {n} calibration value (e.g. 14.08): ").strip()
        try:
            cal = float(cal_raw)
            break
        except ValueError:
            print("  Please enter a number.")
    sensors[n] = {'enable': 1, 'type': link_type, 'cal': cal}

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
cur.execute(
    "UPDATE iparams SET stationid=?, "
    "station1cal=?, s1enable=?, s1type=?, "
    "station2cal=?, s2enable=?, s2type=?, "
    "station3cal=?, s3enable=?, s3type=?",
    (
        stationid,
        sensors[1]['cal'], sensors[1]['enable'], sensors[1]['type'],
        sensors[2]['cal'], sensors[2]['enable'], sensors[2]['type'],
        sensors[3]['cal'], sensors[3]['enable'], sensors[3]['type'],
    )
)
if cur.rowcount == 0:
    # iparams was genuinely empty (no starter row to update) -- insert one.
    cur.execute(
        "INSERT INTO iparams (stationid, "
        "station1cal, s1enable, s1type, "
        "station2cal, s2enable, s2type, "
        "station3cal, s3enable, s3type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            stationid,
            sensors[1]['cal'], sensors[1]['enable'], sensors[1]['type'],
            sensors[2]['cal'], sensors[2]['enable'], sensors[2]['type'],
            sensors[3]['cal'], sensors[3]['enable'], sensors[3]['type'],
        )
    )
con.commit()
con.close()

print()
print(f"iparams updated: stationid={stationid}")
for n in (1, 2, 3):
    s = sensors[n]
    if s['enable']:
        print(f"  sensor {n}: enabled, type={s['type']}, cal={s['cal']}")
    else:
        print(f"  sensor {n}: disabled")
