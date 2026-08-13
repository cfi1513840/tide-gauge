import os
import sqlite3
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client_3 import InfluxDBClient3
import logging
import pytz
import tidecrypto

class DbManage:
    """Manages access to the sqlite3 and InfluxDB databases"""
    def __init__(self, cons):
        
        self.cons = cons
        self.sqlpath = cons.SQL_PATH
        # Write client -- local InfluxDB 3 Core, v2-compatible write endpoint.
        # Unchanged in behavior from pre-migration code; only the URL/token
        # it's constructed with (in tidehelper.py) changed.
        self.influxdb_client = cons.INFLUXDB_WRITE_CLIENT
        # Query client -- InfluxDB 3 native client, required because InfluxDB 3
        # does not support the Flux-based query API the old influxdb_query_api
        # used. Queries local only; nothing currently reads the cloud copy back.
        self.influxdb_local_query_client = cons.INFLUXDB_LOCAL_QUERY_CLIENT
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

    def insert_tide(self, data_dict):
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
            # Attach the sensor height above MLLW (feet, 2 decimal places)
            # for this record's station, sourced from the station<n>cal
            # parameter in the sqlite3 iparams table. This makes the raw
            # sensor_measurement_mm distance-above-water reading meaningful
            # on its own (transformable to feet MLLW) and self-correcting
            # if the sensor is ever relocated to a different height.
            try:
                station_num = data_dict.get('S')
                if station_num is not None:
                    self.sql_cursor.execute(
                      f"select station{int(station_num)}cal from iparams")
                    cal_row = self.sql_cursor.fetchone()
                    if cal_row and cal_row[0] is not None:
                        data_dict['H'] = cal_row[0]
            except Exception as errmsg:
                logging.warning(
                  'insert_tide: sensor height (station cal) lookup '
                  'failed: '+str(errmsg), exc_info=True)
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
            write_api = self.influxdb_client.write_api(
              write_options=SYNCHRONOUS)
            result = write_api.write(self.cons.INFLUXDB_LOCAL_DATABASE,
              self.cons.ORG_FOR_LOCAL_WRITES, point_command)

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

        Local-first, decoupled design: this only ever reads from local
        InfluxDB and writes to cloud. It never blocks or affects the
        local write path in insert_tide(). On any failure (query or
        write), the watermark is simply not advanced -- the next
        scheduled cycle retries from the same point. No explicit
        retry-count/backoff, by design (see design discussion).

        NOT YET VERIFIED against live InfluxDB 3 Core + Cloud Serverless
        instances -- test on TestBelfastTide before relying on this in
        production on any node with real alert-critical data.
        """
        measurement = self.cons.INFLUXDB_MEASUREMENT
        try:
            with open(self.cloud_sync_watermark_path, 'r') as f:
                watermark = f.read().strip()
        except FileNotFoundError:
            # First run on this node -- sync everything currently in
            # local InfluxDB rather than assuming a start time.
            watermark = '1970-01-01T00:00:00.000000Z'

        sync_query = (
            f'SELECT * FROM "{measurement}" '
            f"WHERE time > '{watermark}' "
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
        newest_time = None
        try:
            for dbvalues in records:
                timetag = dbvalues.pop('time')
                point_command = Point(measurement)
                for key, value in dbvalues.items():
                    if value is None:
                        continue
                    # location/sensor_num are tags in the local write path
                    # (insert_tide) -- preserve that distinction on the
                    # cloud copy rather than writing everything as fields.
                    if key in ('location', 'sensor_type', 'sensor_num'):
                        point_command.tag(key, value)
                    else:
                        point_command.field(key, value)
                point_command.time(timetag, WritePrecision.NS)
                write_api.write(self.cons.INFLUXDB_CLOUD_BUCKET,
                  self.cons.INFLUXDB_CLOUD_ORG, point_command)
                if newest_time is None or timetag > newest_time:
                    newest_time = timetag
        except Exception as errmsg:
            logging.warning('sync_influxdb_cloud write failed: '+str(errmsg), exc_info=True)
            return  # watermark NOT advanced -- retry from the same point next cycle

        if newest_time is not None:
            try:
                with open(self.cloud_sync_watermark_path, 'w') as f:
                    f.write(str(newest_time))
            except Exception as errmsg:
                logging.warning(
                  'sync_influxdb_cloud watermark write failed: '+str(errmsg), exc_info=True)

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
