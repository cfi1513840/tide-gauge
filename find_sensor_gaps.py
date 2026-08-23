#!/usr/bin/env python3
"""find_sensor_gaps.py

Scans the tide station's local sqlite3 "sensors" table for gaps
between consecutive readings, per station, and reports a histogram
of how many gaps fall into each duration bucket. Runs entirely
against sqlite3 directly on the RPi -- no separate export step.

Intended for checking LoRa reception specifically: by default, the
stations analyzed are auto-selected from the iparams table --
whichever of s1/s2/s3 have s<n>type == 'lora' and s<n>enable == 1 --
rather than every station that happens to appear in the data. Use
--station to check just one specific station instead (bypasses the
iparams lookup), or --all-stations to analyze every station present
in the data regardless of iparams (e.g. to also check a Notecard
station for some other purpose).

Default buckets (minutes): 1-5, 5-10, 10-15, 15-30, 30-60, 60+.
Each bucket is [lower, upper) except the last, which is [lower, inf).
Gaps shorter than the smallest boundary (1 min by default) aren't
counted at all -- ordinary reporting jitter, not a real gap.

Usage examples:
    # Last 24 hours, LoRa-enabled stations per iparams, default buckets
    python3 find_sensor_gaps.py

    # Last 48 hours, only station 2 (bypasses iparams lookup)
    python3 find_sensor_gaps.py --hours 48 --station 2

    # Every station present in the data, ignoring iparams entirely
    python3 find_sensor_gaps.py --all-stations

    # A specific window, custom bucket boundaries (in minutes)
    python3 find_sensor_gaps.py --since "2026-08-20 00:00:00" \\
        --until "2026-08-21 00:00:00" --buckets 1,10,30,60,120

    # A different database file
    python3 find_sensor_gaps.py --db /path/to/tides.db
"""
import argparse
import sqlite3
from datetime import datetime, timedelta

DEFAULT_DB_PATH = "/var/www/html/tides.db"
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_BUCKETS = [1, 5, 10, 15, 30, 60]  # minutes


def parse_args():
    p = argparse.ArgumentParser(
        description="Find and bucket gaps in sensor reporting in the tide "
                    "station's sqlite3 database.")
    p.add_argument("--db", default=DEFAULT_DB_PATH,
                    help=f"Path to the sqlite3 database "
                         f"(default: {DEFAULT_DB_PATH})")
    p.add_argument("--hours", type=float, default=24,
                    help="Look back this many hours from now (default: 24). "
                         "Ignored if --since is given.")
    p.add_argument("--since",
                    help="Explicit start time, 'YYYY-MM-DD HH:MM:SS'. "
                         "Overrides --hours.")
    p.add_argument("--until",
                    help="Explicit end time, 'YYYY-MM-DD HH:MM:SS' "
                         "(default: now).")
    p.add_argument("--station", type=int,
                    help="Limit to one station number, bypassing the "
                         "iparams LoRa-enabled lookup.")
    p.add_argument("--all-stations", action="store_true",
                    help="Analyze every station present in the data, "
                         "ignoring iparams entirely.")
    p.add_argument("--buckets", type=str,
                    default=",".join(str(b) for b in DEFAULT_BUCKETS),
                    help="Comma-separated ascending bucket boundaries in "
                         f"minutes (default: "
                         f"{','.join(str(b) for b in DEFAULT_BUCKETS)}). "
                         "Gaps shorter than the first value aren't counted.")
    return p.parse_args()


def lora_enabled_stations(conn):
    """Returns the list of station numbers (from 1/2/3) where iparams
    has s<n>type == 'lora' and s<n>enable == 1 (accepting int 1 or
    string '1' for the enable flag, since sqlite3's storage of it can
    vary). Returns an empty list if iparams has no rows or none match.
    """
    cur = conn.cursor()
    cur.execute("SELECT s1type, s1enable, s2type, s2enable, "
                "s3type, s3enable FROM iparams LIMIT 1")
    row = cur.fetchone()
    if row is None:
        return []
    s1type, s1enable, s2type, s2enable, s3type, s3enable = row
    stations = []
    for n, stype, senable in ((1, s1type, s1enable), (2, s2type, s2enable),
                               (3, s3type, s3enable)):
        if stype == 'lora' and str(senable) == '1':
            stations.append(n)
    return stations


def bucket_gap(minutes, boundaries):
    """Returns the index of the bucket `minutes` falls into (each bucket
    is [boundaries[i], boundaries[i+1]), the last is [boundaries[-1], inf)),
    or None if minutes is below the smallest boundary (not counted).
    """
    if minutes < boundaries[0]:
        return None
    for i in range(len(boundaries) - 1):
        if boundaries[i] <= minutes < boundaries[i + 1]:
            return i
    return len(boundaries) - 1


def bucket_label(i, boundaries):
    if i == len(boundaries) - 1:
        return f"{boundaries[i]:g}min+"
    return f"{boundaries[i]:g}-{boundaries[i + 1]:g}min"


def find_gap_minutes(times):
    """times: sorted list of datetime objects. Returns a list of
    (gap_minutes, gap_start, gap_end) for every consecutive pair.
    """
    gaps = []
    for i in range(1, len(times)):
        delta_minutes = (times[i] - times[i - 1]).total_seconds() / 60.0
        gaps.append((delta_minutes, times[i - 1], times[i]))
    return gaps


def main():
    args = parse_args()

    boundaries = [float(x) for x in args.buckets.split(",")]
    if boundaries != sorted(boundaries):
        raise SystemExit("--buckets values must be in ascending order")

    until = (datetime.strptime(args.until, TIME_FORMAT) if args.until
             else datetime.now())
    since = (datetime.strptime(args.since, TIME_FORMAT) if args.since
             else until - timedelta(hours=args.hours))

    conn = sqlite3.connect(args.db)

    station_filter = None  # None means "all stations in the data"
    if args.station is not None:
        station_filter = [args.station]
    elif not args.all_stations:
        station_filter = lora_enabled_stations(conn)
        if not station_filter:
            print("No LoRa-enabled stations found in iparams "
                  "(s<n>type=='lora' and s<n>enable==1). Use --station "
                  "to check a specific one, or --all-stations to check "
                  "everything present in the data regardless of iparams.")
            conn.close()
            return
        print(f"LoRa-enabled stations per iparams: "
              f"{', '.join(str(s) for s in station_filter)}\n")

    cur = conn.cursor()
    query = ("SELECT database_time, station FROM sensors "
              "WHERE database_time >= ? AND database_time <= ?")
    params = [since.strftime(TIME_FORMAT), until.strftime(TIME_FORMAT)]
    if station_filter is not None:
        placeholders = ",".join("?" * len(station_filter))
        query += f" AND station IN ({placeholders})"
        params.extend(station_filter)
    query += " ORDER BY station, database_time"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    print(f"Analyzing readings from {since} to {until}")
    print(f"Database: {args.db}")
    print(f"Bucket boundaries (minutes): "
          f"{', '.join(bucket_label(i, boundaries) for i in range(len(boundaries)))}\n")

    if not rows:
        print("No readings found in this window.")
        return

    by_station = {}
    for time_str, station in rows:
        by_station.setdefault(station, []).append(time_str)

    for station in sorted(by_station.keys()):
        times = []
        skipped = 0
        for t in by_station[station]:
            try:
                times.append(datetime.strptime(t, TIME_FORMAT))
            except ValueError:
                skipped += 1
        times.sort()

        gaps = find_gap_minutes(times)
        bucket_counts = [0] * len(boundaries)
        bucket_examples = [None] * len(boundaries)  # largest example per bucket
        for minutes, start, end in gaps:
            idx = bucket_gap(minutes, boundaries)
            if idx is None:
                continue
            bucket_counts[idx] += 1
            if (bucket_examples[idx] is None or
              minutes > bucket_examples[idx][0]):
                bucket_examples[idx] = (minutes, start, end)

        print(f"--- Station {station} ---")
        print(f"  Total readings: {len(times)}"
              f"{f' ({skipped} unparseable, skipped)' if skipped else ''}")
        total_bucketed = sum(bucket_counts)
        print(f"  Total gaps >= {boundaries[0]:g} min: {total_bucketed}")
        for i in range(len(boundaries)):
            label = bucket_label(i, boundaries)
            count = bucket_counts[i]
            line = f"    {label:>10s}: {count}"
            if bucket_examples[i]:
                mins, start, end = bucket_examples[i]
                line += f"  (largest in bucket: {mins:.1f} min, {start} to {end})"
            print(line)
        print()


if __name__ == "__main__":
    main()
