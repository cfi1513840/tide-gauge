"""tidecloud.py

Reads a station's 'cloud' sensor slots from InfluxDB Cloud: readings
any sensor already has there (a Notecard sensor written by the
Cloudflare Worker, or a LoRa sensor synced up by another station),
selected by sensor ID (STATION<n>_SENSOR_ID in tide.env).

Non-blocking. At the start of each one-minute interval tide.py calls
start_query(), which runs the query on a background thread (unless the
previous one is still going) and returns at once. Every 5-second pass
tide.py calls poll(), which takes whatever the thread has finished and
stores each new reading through tidesensors.ingest_records() -- the
same db.insert_tide() (sqlite3 "sensors" table and local InfluxDB) and
per-reading alert checks Notecard readings get. All database writes
stay on tide.py's main thread; the thread only talks to the network.

How far back each query goes is set by the data, not a fixed window:
for each sensor, the query asks only for readings newer than the
newest one already stored -- the end of its last successful report.
However long a Notecard waits between reports (cellular conditions,
battery voltage), the next report is picked up whole, from its oldest
reading. Readings already handled are also skipped by exact
timestamp, so each one is stored and alert-checked once.

Once every SWEEP_INTERVAL (an hour) the query instead covers the last
MAX_CATCHUP (24 hours), to pick up a report that reached the cloud
after a newer one -- e.g. one Notehub had to retry -- which the
newest-reading start would otherwise pass over.

On the first query after tide.py starts, the timestamps already in
local InfluxDB are loaded first, so a restart neither repeats readings
nor leaves a gap. If local InfluxDB can't be read, the cloud is not
queried until it can (retried each minute). A failed query changes
nothing, so the next one starts from the same readings and an outage
is caught up. No query goes back more than MAX_CATCHUP; a sensor with
nothing stored in that time is read from MAX_CATCHUP back.
"""
import logging
import queue
import threading
from datetime import datetime, timedelta, timezone

import tidesensors

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Cloud field name -> record code, as in sensor_fields.json. Battery
# voltage is stored in millivolts; records carry volts, the way
# Notecard records do, and insert_tide() converts back.
FIELDS = (('sensor_measurement_mm', 'R'), ('correlation_count', 'M'),
          ('signal_strength', 'P'), ('battery_milliVolts', 'V'),
          ('temperature', 't'), ('message_count', 'C'),
          ('solar_milliVolts', 's'))


def epoch_ms(ts):
    """Whole milliseconds since 1970 UTC for a query result time: a
    pandas Timestamp or a datetime, naive (UTC) or aware."""
    value = getattr(ts, 'value', None)
    if isinstance(value, int):          # pandas Timestamp: ns since epoch
        return value // 1_000_000
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (ts - EPOCH) // timedelta(milliseconds=1)


def iso(when):
    return when.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


class CloudReader:
    MAX_CATCHUP = timedelta(hours=24)
    SWEEP_INTERVAL = timedelta(hours=1)
    SLOW_QUERY = timedelta(minutes=2)
    FAILURE_LOG_INTERVAL = timedelta(minutes=15)

    def __init__(self, cons, ctx, cloud_client=None, local_client=None):
        self.cons = cons
        self.ctx = ctx
        self.id_to_slot = {ctx.sensor_ids[n]: n
                           for n in ctx.slots_of_type('cloud')}
        self._queue = queue.Queue()
        self._thread = None
        self._started = None
        self._slow_logged = False
        # Used only by the query thread (one at a time):
        self._cloud_client = cloud_client
        self._local_client = local_client
        self._seeded = False
        self._last_sweep = None
        # Used only by tide.py's main thread, in poll():
        self._seen = {n: set() for n in self.id_to_slot.values()}
        self._failing_since = None
        self._failure_logged = None

    # ---- main thread -------------------------------------------------

    def start_query(self):
        """Start a cloud query on a background thread and return at once.
        Skipped while the previous query is still running, or when every
        cloud slot is shut off (s<n>enable). Returns True if started."""
        now = datetime.now(timezone.utc)
        if self._thread is not None and self._thread.is_alive():
            if not self._slow_logged and now - self._started > self.SLOW_QUERY:
                self._slow_logged = True
                logging.warning(
                  f'Cloud read started at {self._started:%H:%M:%S} UTC is '
                  f'still running; skipping new reads until it finishes')
            return False
        # Newest reading already handled, per enabled sensor (None if
        # nothing in the last MAX_CATCHUP): each query starts there.
        newest = {sid: max(self._seen[n], default=None)
                  for sid, n in self.id_to_slot.items()
                  if self.ctx.enabled.get(n)}
        if not newest:
            return False
        self._started = now
        self._slow_logged = False
        self._thread = threading.Thread(
          target=self._run, args=(newest, now), daemon=True,
          name='cloud-read')
        self._thread.start()
        return True

    def poll(self):
        """Store whatever finished queries have returned; never waits.
        Returns the number of new readings passed on."""
        handled = 0
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == 'seed':
                for sid, times in payload.items():
                    slot = self.id_to_slot.get(sid)
                    if slot is not None:
                        self._seen[slot].update(times)
            elif kind == 'error':
                self._query_failed(payload)
            elif kind == 'rows':
                if self._failing_since is not None:
                    logging.warning(
                      f'Cloud read working again (failing since '
                      f'{self._failing_since:%H:%M} UTC)')
                    self._failing_since = None
                records = self._new_records(payload)
                handled += tidesensors.ingest_records(self.ctx, records,
                                                      'cloud')
        self._prune()
        return handled

    def _query_failed(self, message):
        now = datetime.now(timezone.utc)
        if self._failing_since is None:
            self._failing_since = now
            self._failure_logged = now
            logging.warning(f'Cloud read failed: {message} -- retrying '
                            f'each minute, catching up when it works')
        elif now - self._failure_logged >= self.FAILURE_LOG_INTERVAL:
            self._failure_logged = now
            logging.warning(
              f'Cloud read still failing since {self._failing_since:%H:%M} '
              f'UTC: {message}')

    def _new_records(self, rows):
        """Rows not seen before, as Notecard-style records, oldest first."""
        records = []
        for row in rows:
            slot = self.id_to_slot.get(row.get('sensor_id'))
            if slot is None or row.get('time') is None:
                continue
            if row.get('sensor_measurement_mm') is None:
                continue
            ms = epoch_ms(row['time'])
            if ms in self._seen[slot]:
                continue
            self._seen[slot].add(ms)
            record = {'T': ms / 1000, 'S': slot, 'I': row['sensor_id'],
                      # The sensor's own radio link, as the cloud has it
                      'L': row.get('link_type') or 'cloud',
                      'H': self.ctx.cal.get(slot)}
            for name, code in FIELDS:
                value = row.get(name)
                if value is None:
                    continue
                if code == 'V':
                    value = value / 1000
                record[code] = value
            record['R'] = int(record['R'])
            records.append(record)
        records.sort(key=lambda r: r['T'])
        return records

    def _prune(self):
        """Forget timestamps older than any window can reach."""
        cutoff = epoch_ms(datetime.now(timezone.utc) - self.MAX_CATCHUP
                          - timedelta(hours=1))
        for slot, times in self._seen.items():
            if times and min(times) < cutoff:
                self._seen[slot] = {t for t in times if t >= cutoff}

    # ---- query thread ------------------------------------------------

    def _run(self, newest, now):
        """newest: {sensor_id: newest handled reading in ms, or None}."""
        try:
            ids = list(newest)
            if not self._seeded:
                try:
                    seed = self._local_times(ids, now - self.MAX_CATCHUP)
                except Exception as errmsg:
                    if 'not found' not in str(errmsg).lower():
                        # Without local InfluxDB's timestamps, readings
                        # already stored could be stored again; wait for
                        # it rather than guess.
                        raise RuntimeError(
                          f'cannot read local InfluxDB: {errmsg}')
                    seed = {}   # no local table yet (new station)
                self._queue.put(('seed', seed))
                self._seeded = True
                for sid in ids:
                    times = seed.get(sid)
                    if times:
                        newest[sid] = max(newest[sid] or 0, max(times))
            floor = now - self.MAX_CATCHUP
            sweep = (self._last_sweep is not None and
                     now - self._last_sweep >= self.SWEEP_INTERVAL)
            starts = {}
            for sid, ms in newest.items():
                if sweep or ms is None:
                    starts[sid] = floor
                else:
                    starts[sid] = max(floor,
                                      EPOCH + timedelta(milliseconds=ms))
            rows = self._query_cloud(starts)
            self._queue.put(('rows', rows))
            if sweep or self._last_sweep is None:
                self._last_sweep = now
        except Exception as errmsg:
            self._queue.put(('error', f'{type(errmsg).__name__}: {errmsg}'))

    def _id_list(self, ids):
        # Sensor IDs are checked as letters and digits at startup
        # (tidesensors.check_station_config), so quoting them is safe.
        return ', '.join(f"'{sid}'" for sid in ids)

    def _query_cloud(self, starts):
        """Rows newer than each sensor's start: {sensor_id: datetime}."""
        if self._cloud_client is None:
            from influxdb_client_3 import InfluxDBClient3
            self._cloud_client = InfluxDBClient3(
              host=self.cons.INFLUXDB_CLOUD_URL,
              token=self.cons.INFLUXDB_CLOUD_TOKEN,
              database=self.cons.INFLUXDB_CLOUD_BUCKET)
        # Sensor IDs are checked as letters and digits at startup
        # (tidesensors.check_station_config), so quoting them is safe.
        where = ' OR '.join(f"(sensor_id = '{sid}' AND time > '{iso(t)}')"
                            for sid, t in starts.items())
        query = (f'SELECT * FROM "{self.cons.INFLUXDB_MEASUREMENT}" '
                 f'WHERE {where} ORDER BY time ASC')
        return self._cloud_client.query(query=query, language='sql').to_pylist()

    def _local_times(self, ids, start):
        """{sensor_id: {ms, ...}} already in local InfluxDB since start."""
        if self._local_client is None:
            from influxdb_client_3 import InfluxDBClient3
            self._local_client = InfluxDBClient3(
              host=self.cons.INFLUXDB_LOCAL_URL,
              token=self.cons.INFLUXDB_LOCAL_TOKEN,
              database=self.cons.INFLUXDB_LOCAL_DATABASE)
        query = (f'SELECT time, sensor_id FROM '
                 f'"{self.cons.INFLUXDB_MEASUREMENT}" '
                 f"WHERE time > '{iso(start)}' "
                 f'AND sensor_id IN ({self._id_list(ids)})')
        seed = {}
        for row in self._local_client.query(query=query,
                                            language='sql').to_pylist():
            seed.setdefault(row['sensor_id'], set()).add(
              epoch_ms(row['time']))
        return seed
