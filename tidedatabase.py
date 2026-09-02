"""tidedatabase.py

Central persistence layer for the tide station: everything the rest of
the codebase reads or writes to storage goes through DbManage. Three
separate storage backends live behind this one class:

  - sqlite3 (local file, self.sqlpath): raw sensor readings (the
    "sensors" table -- a secondary diagnostic log, distinct from
    InfluxDB), cached NOAA tide predictions and NDBC/weather data,
    station configuration ("iparams"/"banner"), and alert-subscriber
    credentials ("userpass").
  - InfluxDB, local (InfluxDB 3 Core on this RPi): the tide station's
    primary time-series store. Writes go through the older
    v2-compatible endpoint (proven reliable -- the native v3 write API
    was tried and reverted after it silently failed to persist data on
    a heavily-fragmented table with no clear error), dispatched onto a
    background daemon thread (_write_worker) so a slow write can never
    stall the Tk main loop or delay a Notehub response. Queries go
    through the native v3 client instead, since InfluxDB 3 doesn't
    support the old Flux query language writes still use.
  - InfluxDB, cloud (InfluxDB Cloud Serverless): a decoupled, one-way
    sync (sync_influxdb_cloud) that periodically pushes new local rows
    to the cloud copy, tracked by a watermark file so it always resumes
    from where it left off. Local-first by design: nothing here ever
    waits on cloud connectivity. Notecard-sourced stations bypass this
    sync entirely (routed directly from Notehub to InfluxDB Cloud
    instead) via the per-station STATION_CLOUD_ENABLE flags.

insert_tide() also runs every reading through a per-sensor outlier
filter (_check_outlier), delegated to the shared tidehelper.OutlierTracker,
before it's allowed to reach sqlite3 or InfluxDB at all -- a single
tracked baseline value (not an average) that rejects implausible
jumps, and resets itself if too long has passed since the last
trustworthy reading for that sensor (a real reporting gap, not just
noise).
"""
import os
import sqlite3
import queue
import threading
import time
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client_3 import InfluxDBClient3
import logging
import pytz
import tidecrypto
import tidehelper

class DbManage:
    """Manages access to the sqlite3 and InfluxDB databases"""
    def __init__(self, cons):
        
        self.cons = cons
        self.sqlpath = cons.SQL_PATH
        # Local write client -- v2-compatible endpoint (reverted from the
        # native v3 write_lp API; see tidehelper.py for why). Writes are
        # dispatched through a background thread (self._write_worker) so
        # a slow/blocked write can never stall the Tk main loop or delay
        # a Notehub HTTP response -- insert_tide() only builds the Point
        # and enqueues it, returning immediately.
        self.influxdb_client = cons.INFLUXDB_WRITE_CLIENT
        self._influxdb_write_api = self.influxdb_client.write_api(
          write_options=SYNCHRONOUS)
        self._write_queue = queue.Queue()
        self._write_thread = threading.Thread(
          target=self._write_worker, daemon=True)
        self._write_thread.start()
        # Query client -- InfluxDB 3 native client, required because InfluxDB 3
        # does not support the Flux-based query API the old influxdb_query_api
        # used. Queries local only; nothing currently reads the cloud copy back.
        self.influxdb_local_query_client = cons.INFLUXDB_LOCAL_QUERY_CLIENT
        # Outlier rejection: same design as tidealerts.py's alert-side
        # check (see tidehelper.OutlierTracker for the full rationale),
        # applied here to the database write path instead, since alerts
        # operate on live in-memory data and never touch insert_tide() --
        # a reading bad enough to trip the alert check could otherwise
        # still land in both databases untouched. Keyed per sensor_id
        # (the record's "I" field), since multiple distinct physical
        # sensors share this one write path and each needs its own
        # independent tracker.
        self._outlier_trackers = {}
        self.sql_connection = sqlite3.connect(f'{self.sqlpath}')
        self.sql_cursor = self.sql_connection.cursor()
        self.local_tz = pytz.timezone('US/Eastern')
        self.last_message_count = 100
        self.initial_start = "-24h"
        self.last_time = None
        self.f1 = tidecrypto.EMAIL_KEY
        # Cloud sync watermark: tracks the timestamp of the newest local row
        # already pushed to InfluxDB Cloud, so _sync_influxdb_cloud() only
        # sends what's new since the last successful sync. Stored in a flat
        # file (not the database) so it survives tide.py restarts.
        self.cloud_sync_watermark_path = os.path.join(
          self.cons.HOME_DIRECTORY, '.cloud_sync_watermark')

    def _write_worker(self):
        """Background thread: pulls Points off self._write_queue and
        writes them to local InfluxDB one at a time, off the Tk main
        thread. Runs for the life of the process (daemon thread, so it
        doesn't block interpreter shutdown). A slow or stuck write here
        never blocks main(), sensor reads, or Notehub HTTP responses --
        it only delays how quickly OTHER queued points get written.
        """
        while True:
            point_command = self._write_queue.get()
            try:
                self._influxdb_write_api.write(
                  self.cons.INFLUXDB_LOCAL_DATABASE,
                  self.cons.ORG_FOR_LOCAL_WRITES, point_command)
            except Exception as errmsg:
                logging.warning(
                  'insert_tide (background write thread): '+str(errmsg),
                  exc_info=True)
            finally:
                self._write_queue.task_done()

    def insert_weather(self, weather):
        now = datetime.now()
        database_time = datetime.strftime(now, self.cons.TIME_FORMAT)
        database_values = (
          database_time,
          weather.get('temperature'), 
          weather.get('baro'), 
          weather.get('humidity'), 
          weather.get('wind_speed'),           
          weather.get('wind_direction_degrees'), 
          weather.get('wind_gust'),
          weather.get('baro_trend'), 
          weather.get('dewpoint'), 
          weather.get('rain_rate'), 
          weather.get('rain_today'))

        self.sql_cursor.execute(
          f"INSERT INTO wxdata VALUES (?,?,?,?,?,?,?,?,?,?,?)",
          database_values)
        self.sql_connection.commit()

    def insert_ndbc_data(self, ndbc_data, init_flag):
        now = datetime.now()
        if init_flag:
            self.sql_cursor.execute("delete from ndbcdata")
            self.sql_connection.commit()
        else:            
            self.sql_cursor.execute("select reporttime from ndbcdata")
            sql_reply = self.sql_cursor.fetchone()
            new_report_time = ndbc_data.get('DateTime')
            if sql_reply and sql_reply[0] == new_report_time:
                return            
        database_time = datetime.strftime(now, self.cons.TIME_FORMAT)
        database_columns = ['dtime','reporttime','location','windir','windspeed','windgust',
          'waveheight','waveperiod','airtemp','watertemp','wavedirection','barometer']
        database_values = (
          database_time,
          ndbc_data.get('DateTime'), 
          ndbc_data.get('Location'), 
          ndbc_data.get('Wind Direction'), 
          ndbc_data.get('Wind Speed'), 
          ndbc_data.get('Wind Gust'), 
          ndbc_data.get('Wave Height'),
          ndbc_data.get('Wave Period'), 
          ndbc_data.get('Air Temperature'), 
          ndbc_data.get('Water Temperature'), 
          ndbc_data.get('Wave Direction'),
          ndbc_data.get('Atmospheric Pressure'))
        if init_flag:
            self.sql_cursor.execute (
              f"INSERT INTO ndbcdata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              database_values)
        else:             
            for indx, value in enumerate(database_values):
                if value != '' and value != None:
                    self.sql_cursor.execute (
                      f"update ndbcdata set {database_columns[indx]} = '{value}'")
        self.sql_connection.commit()          
        
    def insert_tide_predicts(self, noaa_data):
        db_commit = False
        for predict in noaa_data:
            self.sql_cursor.execute(
              f"select dtime from predicts where dtime = '{predict[0]}'")
            sqlist = self.sql_cursor.fetchone()
            if not sqlist:
                db_commit = True
                dbvals = (predict[0],float(predict[1]),predict[2])
                self.sql_cursor.execute(
                f"INSERT INTO predicts VALUES (?,?,?)", dbvals)
        if db_commit:
            self.sql_connection.commit()

    def _check_outlier(self, sensor_id, candidate_ft, candidate_time):
        """Delegates to tidehelper.OutlierTracker (see there for the full
        rationale), keeping one tracker per sensor_id since multiple
        physical sensors share this write path and each needs its own
        independent baseline. Returns True to accept (write it), False
        to reject it.

        candidate_time is this specific reading's own timestamp --
        Notecard's embedded 'T' when available, otherwise the RPi's
        current wall-clock time as a fallback for LoRa readings (which
        don't carry their own timestamp).
        """
        tracker = self._outlier_trackers.setdefault(
          sensor_id, tidehelper.OutlierTracker())
        accepted, baseline, gap_reset_seconds = tracker.check(
          candidate_ft, candidate_time)
        if gap_reset_seconds is not None:
            logging.warning(
              f'insert_tide: sensor {sensor_id} reporting gap of '
              f'{gap_reset_seconds:.0f}s exceeds '
              f'{tracker.OUTLIER_GAP_RESET_SECONDS}s -- resetting outlier '
              f'baseline to re-establish')
        if not accepted:
            logging.warning(
              f'insert_tide: rejecting outlier for sensor {sensor_id}: '
              f'{candidate_ft} versus baseline {baseline}')
        return accepted

    def insert_tide(self, data_dict):
        # Reject an implausible reading before it reaches either database
        # (sqlite3 or InfluxDB). Only possible when both a sensor_id and
        # a computable tide-in-feet value are present; if either is
        # missing (e.g. sensor height not yet calibrated), fall through
        # to the existing unfiltered behavior rather than blocking writes
        # entirely on a config gap.
        sensor_id = data_dict.get('I')
        raw_mm = data_dict.get('R', data_dict.get('U'))
        height_ft = data_dict.get('H')
        if sensor_id is not None and raw_mm is not None and height_ft is not None:
            candidate_ft = height_ft - raw_mm / 304.8
            # Prefer the reading's own embedded timestamp (Notecard's
            # 'T', Unix epoch seconds) so a batch of backlogged readings
            # delivered at once after an outage is judged against the
            # actual gap in real tide measurements, not the moment the
            # RPi happened to process the backlog. LoRa readings don't
            # carry their own timestamp, so fall back to wall-clock time.
            if "T" in data_dict:
                candidate_time = datetime.fromtimestamp(
                  data_dict["T"], tz=timezone.utc)
            else:
                candidate_time = datetime.now(timezone.utc)
            if not self._check_outlier(sensor_id, candidate_ft, candidate_time):
                return
        try:
            now = datetime.now()
            database_time = datetime.strftime(now, self.cons.TIME_FORMAT)
            if "T" in data_dict:
                database_time = datetime.fromtimestamp(data_dict["T"]).strftime(self.cons.TIME_FORMAT)  
            location = self.cons.INFLUXDB_LOCATION
            measurement = self.cons.INFLUXDB_MEASUREMENT
            sensor = self.cons.INFLUXDB_SENSOR
            try:
                station = data_dict.get('S')
                if 'R' in data_dict:
                    distance = data_dict.get('R')
                    distance_feet = round(distance*0.03937007874,2)
                elif 'U' in data_dict:
                    distance = data_dict.get('U')
                    distance_feet = round(distance*0.03937007874,2)
                if 's' in data_dict:
                    solar = data_dict.get('s')
                    solarv = round(solar/1000,3)
                else:
                    solar = 0
                    solarv = 0
                if 't' in data_dict:
                    therm = data_dict.get('t')
                else:
                    therm = 0
                if 'M' in data_dict:
                    corr = data_dict.get('M')
                else:
                    corr = 0
                if 'P' in data_dict:
                    rssi = data_dict.get('P')
                elif 'r' in data_dict:
                    rssi = data_dict.get('r')
                else:
                    rssi = 0
                if "T" in data_dict:
                    voltage = data_dict.get('V')
                else:                      
                    voltage = round(data_dict.get('V')/1000,3) 
                database_values = (
                  database_time,
                  station,
                  location,                    
                  rssi,
                  voltage,'',
                  data_dict.get('C'),
                  distance_feet,
                  distance,
                  corr,
                  solarv,
                  therm                  
                  )
                self.sql_cursor.execute(
                  f"INSERT INTO sensors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  database_values)
                self.sql_connection.commit()
            except Exception as errmsg:
                logging.warning('sqlite3 db insertion failed: '+str(errmsg), exc_info=True)
                pass
            message_time = datetime.now(timezone.utc)
            if "T" in data_dict:
                message_time = int(data_dict["T"]*1000)
            # Sensor height above MLLW ("H") is expected to already be set
            # on data_dict by the caller (tide.py), using its in-memory
            # cached stationNcal values -- not queried here on every write,
            # since that added a synchronous sqlite3 read to the hot path
            # of every InfluxDB write (multiplied per measurement for
            # batched Notecard events), which was slowing down Notehub
            # HTTP responses on TestBelfastTide.
            point_command = Point(f'{measurement}')
            point_command.tag("location", f"{location}")
            point_command.tag("sensor_type", f"{sensor}")
            for name, value in self.cons.INFLUXDB_NAMES.items():
                if data_dict.get(name) != None:
                    if value[2] == 'int':
                        if name == 'V' and 'T' in data_dict:
                            data_dict[name] = int(data_dict.get(name)*1000)
                        else:
                            data_dict[name] = int(data_dict.get(name))
                    elif value[2] == 'str':
                        data_dict[name] = str(data_dict.get(name))
                    else:
                        data_dict[name] = float(data_dict.get(name))
                    if value[0] == 'fld':
                        point_command.field(value[1], data_dict.get(name))
                    else:
                        point_command.tag(value[1], data_dict.get(name))
            point_command.time(message_time, WritePrecision.MS)
            # Hand off to the background write thread (see
            # _write_worker) instead of writing synchronously here --
            # this call returns immediately regardless of how long the
            # actual InfluxDB write takes.
            self._write_queue.put(point_command)

        except Exception as errmsg:
            logging.warning('insert_tide: '+str(errmsg), exc_info=True)            

    def fetch_predicts(self, tide_start_time):
        try:        
            self.sql_cursor.execute(
              f"select * from predicts where dtime >= '{tide_start_time}' "+
                "order by dtime")
            return self.sql_cursor.fetchall()

        except Exception as errmsg:
            logging.warning('fetch_predicts: '+str(errmsg), exc_info=True)
            return None            
 
    def fetch_iparams(self):
        iparams_dict = {}
        self.sql_cursor.execute("SELECT name FROM PRAGMA_table_info('iparams')")
        colnames = [row[0] for row in self.sql_cursor.fetchall()]
        for colname in colnames:
            self.sql_cursor.execute(f"select {colname} from iparams")
            colval = self.sql_cursor.fetchone()
            iparams_dict[f"{colname}"] = colval[0]
            
        self.sql_cursor.execute("SELECT name FROM PRAGMA_table_info('banner')")
        colnames = [row[0] for row in self.sql_cursor.fetchall()]
        for colname in colnames:
            self.sql_cursor.execute(f"select {colname} from banner")
            colval = self.sql_cursor.fetchone()
            iparams_dict[f"{colname}"] = colval[0]
                        
        return iparams_dict

    def fetch_ndbc(self):
        ndbc_list = (
          '',
          'DateTime', 
          'Location', 
          'Wind Direction', 
          'Wind Speed', 
          'Wind Gust', 
          'Wave Height',
          'Wave Period', 
          'Air Temperature', 
          'Water Temperature', 
          'Wave Direction',
          'Atmospheric Pressure')
        ndbc_dict = {}
        try:        
            self.sql_cursor.execute("select * from ndbcdata")
            params = self.sql_cursor.fetchone()
            for index, entry in enumerate(params):
                if index == 0:
                    continue
                ndbc_dict[ndbc_list[index]] = entry
            return ndbc_dict                

        except Exception as errmsg:
            logging.warning('fetch_ndbc: '+str(errmsg), exc_info=True)
            return None

    def fetch_tide(self, stationid, stationcal, duration):
        """Fetch the last 24 hours of tide measurements for plotting.

        InfluxDB 3 MIGRATION NOTE: rewritten from a Flux query (which
        InfluxDB 3 cannot execute at all -- /api/v2/query does not work
        against v3-stored data) to SQL against the InfluxDB 3 native query
        client. The old Flux pivot() step is no longer needed: InfluxDB 3
        already returns each point as a single wide row (all fields as
        columns), rather than Flux's one-row-per-field format that pivot()
        had to reassemble -- so this version is actually simpler than the
        code it replaces, not just a syntax translation.

        `duration` currently only ever arrives as '-24h' (see tide.py's
        self.influx_duration) -- that is the only value handled explicitly
        below. If some other Flux-style duration literal is ever passed,
        it will fall through to the '-24h'-equivalent branch rather than
        being parsed, which is a latent limitation carried over from
        never being exercised in the original code either.

        NOT YET VERIFIED against a live InfluxDB 3 instance -- test the
        exact column names in the returned rows (tag columns vs. field
        columns may not be named identically to the old Flux dbvalues
        dict) before relying on this in production.
        """
        tide_mm = ''
        batv = ''
        solarv = ''
        rssi = ''
        location = self.cons.INFLUXDB_LOCATION
        measurement = self.cons.INFLUXDB_MEASUREMENT
        local_time  = ''
        if self.last_time is not None and duration != '-24h':
            start_clause = (f"time > '"
              f"{(self.last_time + timedelta(microseconds=1)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')}'")
        else:
            start_clause = "time > now() - INTERVAL '24 hours'"
        self.influx_query = (
            f'SELECT * FROM "{measurement}" '
            f"WHERE {start_clause} "
            f"AND location = '{location}' "
            f"AND sensor_num = '{str(stationid)}' "
            f'ORDER BY time ASC'
        )
        tide_list = []
        field_list = []
        field_dict = {}
        newest_time = None
        try:
            result_table = self.influxdb_local_query_client.query(
              query=self.influx_query, language="sql")
            records = result_table.to_pylist()
            for dbvalues in records:
                timetag = dbvalues.get('time')
                if newest_time is None or timetag > newest_time:
                    newest_time = timetag
                utc_time = timetag
                if getattr(utc_time, 'tzinfo', None) is None:
                    utc_time = utc_time.replace(tzinfo=pytz.utc)
                local_time = utc_time.astimezone(self.local_tz)
                local_time = self.local_tz.normalize(local_time)
                local_time = datetime.strftime(
                  local_time,"%Y-%m-%d %H:%M:%S")
                tide_mm = dbvalues.get(self.cons.INFLUXDB_NAMES.get('R')[1])
                batv = dbvalues.get(self.cons.INFLUXDB_NAMES.get('V')[1])
                solarv = dbvalues.get(self.cons.INFLUXDB_NAMES.get('s')[1])
                message_count = dbvalues.get(self.cons.INFLUXDB_NAMES.get('C')[1])
                correlation_count = dbvalues.get(self.cons.INFLUXDB_NAMES.get('M')[1])
                temperature = dbvalues.get(self.cons.INFLUXDB_NAMES.get('t')[1])
                rssi = dbvalues.get(self.cons.INFLUXDB_NAMES.get('P')[1])
                if tide_mm != None:
                    #self.last_message_count = message_count
                    tide = stationcal-tide_mm/304.8
                    tide_list.append([local_time, tide, ''])
                    field_dict = {
                      "T": local_time,
                      "S": stationid,
                      "V": batv,
                      "C": message_count,
                      "R": tide_mm,
                      "M": correlation_count,
                      "s": solarv,
                      "t": temperature,
                      "P": rssi
                    }
                    field_list.append(field_dict)
            if newest_time is not None:
                self.last_time = newest_time
            #print (local_time+str(field_dict))
            return tide_list, field_list
            
        except Exception as errmsg:
            logging.warning('fetch_tide: '+str(errmsg), exc_info=True)
            return tide_list, field_list

    def sync_influxdb_cloud(self):
        """Push local InfluxDB rows newer than the sync watermark to
        InfluxDB Cloud (org TideGauge, bucket TideData). Called from
        tide.py's main loop at main_loop_count == 9, gated to every 15
        minutes (offset to :02 past the hour to avoid contending with
        weather/NDBC processing at minute zero) -- see tide.py.

        Only forwards data for stations whose S<n>CLOUD_ENABLE flag is
        set (see STATION_CLOUD_ENABLE in tidehelper.py) -- intended for
        LoRa-sourced stations, since Notecard-sourced stations are now
        routed directly from Notehub to InfluxDB Cloud, bypassing this
        RPi-local sync entirely (no advantage in keeping the extra hop:
        if Notehub is down, neither this path nor the direct one would
        receive data anyway).

        Local-first, decoupled design: this only ever reads from local
        InfluxDB and writes to cloud. It never blocks or affects the
        local write path in insert_tide(). Writes are chunked into
        batches of CLOUD_SYNC_BATCH_SIZE points (one write() call per
        batch, not one per point) to stay well under InfluxDB Cloud
        Serverless's write-rate limits -- confirmed in production that
        a large backlog (e.g. after a watermark reset) sent as
        one-request-per-point can trigger a 429 "system overloaded"
        response. The watermark advances after EACH successful batch,
        not just at the very end, so a failure partway through a large
        backlog only costs the current batch's retry -- the next cycle
        resumes from the last successfully-written batch instead of
        restarting the whole backlog from scratch every time. A small
        delay between batches (CLOUD_SYNC_BATCH_DELAY_SECONDS) further
        reduces burst request rate for large backlogs; skipped entirely
        when there's only one batch, which covers ordinary operation.
        """
        CLOUD_SYNC_BATCH_SIZE = 500
        CLOUD_SYNC_BATCH_DELAY_SECONDS = 0.5

        measurement = self.cons.INFLUXDB_MEASUREMENT
        try:
            with open(self.cloud_sync_watermark_path, 'r') as f:
                watermark = f.read().strip()
        except FileNotFoundError:
            # First run on this node -- sync everything currently in
            # local InfluxDB rather than assuming a start time.
            watermark = '1970-01-01T00:00:00.000000Z'

        # Exclude any station whose S<n>CLOUD_ENABLE flag is off --
        # those stations' data is now routed directly from Notehub to
        # InfluxDB Cloud (see STATION_CLOUD_ENABLE in tidehelper.py), so
        # forwarding it here again would just duplicate it.
        disabled_stations = [
          n for n, enabled in self.cons.STATION_CLOUD_ENABLE.items()
          if not enabled]
        station_filter = ''
        if disabled_stations:
            station_filter = (
              ' AND sensor_num NOT IN (' +
              ','.join(str(n) for n in disabled_stations) + ')')

        sync_query = (
            f'SELECT * FROM "{measurement}" '
            f"WHERE time > '{watermark}'"
            f'{station_filter} '
            f'ORDER BY time ASC'
        )
        try:
            result_table = self.influxdb_local_query_client.query(
              query=sync_query, language="sql")
            records = result_table.to_pylist()
        except Exception as errmsg:
            logging.warning('sync_influxdb_cloud query failed: '+str(errmsg), exc_info=True)
            return

        if not records:
            return  # nothing new since the last sync -- watermark unchanged

        cloud_client = self.cons.INFLUXDB_CLOUD_WRITE_CLIENT
        write_api = cloud_client.write_api(write_options=SYNCHRONOUS)
        # Tag names, derived from sensor_fields.json (the single source of
        # truth for which fields are tags vs regular fields on the local
        # write path) plus 'location'/'sensor_type', which insert_tide()
        # tags directly rather than via sensor_fields.json. Computed once
        # per sync call, not hardcoded, so a future tag added to
        # sensor_fields.json (e.g. link_type) is automatically classified
        # correctly here too, instead of silently landing as a field on
        # the cloud copy until someone remembers to update a second list.
        known_tags = {'location', 'sensor_type'} | {
          full_name for (typ, full_name, cast)
          in self.cons.INFLUXDB_NAMES.values() if typ == 'tag'
        }

        batches = [records[i:i + CLOUD_SYNC_BATCH_SIZE]
                   for i in range(0, len(records), CLOUD_SYNC_BATCH_SIZE)]

        for batch_num, batch in enumerate(batches):
            points = []
            batch_newest_time = None
            for dbvalues in batch:
                timetag = dbvalues.pop('time')
                point_command = Point(measurement)
                for key, value in dbvalues.items():
                    if value is None:
                        continue
                    if key in known_tags:
                        point_command.tag(key, value)
                    else:
                        point_command.field(key, value)
                point_command.time(timetag, WritePrecision.NS)
                points.append(point_command)
                if batch_newest_time is None or timetag > batch_newest_time:
                    batch_newest_time = timetag

            try:
                write_api.write(self.cons.INFLUXDB_CLOUD_BUCKET,
                  self.cons.INFLUXDB_CLOUD_ORG, points)
            except Exception as errmsg:
                logging.warning(
                  'sync_influxdb_cloud write failed on batch '
                  f'{batch_num + 1}/{len(batches)}: '+str(errmsg), exc_info=True)
                return  # watermark reflects only prior successful batches

            try:
                with open(self.cloud_sync_watermark_path, 'w') as f:
                    f.write(str(batch_newest_time))
            except Exception as errmsg:
                logging.warning(
                  'sync_influxdb_cloud watermark write failed: '+str(errmsg), exc_info=True)
                return  # don't risk further batches if we can't persist progress

            if len(batches) > 1 and batch_num < len(batches) - 1:
                time.sleep(CLOUD_SYNC_BATCH_DELAY_SECONDS)

    def update_stationid(self, stationid):
        self.sql_cursor.execute(f"update iparams set stationid = {stationid}")
        self.sql_connection.commit()
        
    def fetch_userpass(self):
        self.sql_cursor.execute("select dtime, emailaddr, valstat, valkey from userpass where valkey != ''")
        return self.sql_cursor.fetchall()

    def update_userpass(self, emailaddr, valstat, valkey):       
        if valstat == 1:
            self.sql_cursor.execute(f"UPDATE userpass set valkey = '' where valkey = '{valkey}'")
        else:
            self.sql_cursor.execute(f"delete from userpass where valkey = '{valkey}'")
            self.sql_connection.commit()
            val_address = emailaddr.encode()
            val_address = self.f1.decrypt(val_address).decode()
            pline = (f'Request window expired for {val_address}')
            logging.info(pline)
        
    def update_datetime(self, date, sunrise, sunset):
        self.sql_cursor.execute(f"update banner set dispdate = '{date}',"+
          f"sunrise = '{sunrise}', sunset = '{sunset}'")
        self.sql_connection.commit()
