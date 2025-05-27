import sqlite3
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import logging
import pytz
from cryptography.fernet import Fernet

class DbManage:
    """Manages access to the sqlite3 and InfluxDB databases"""
    def __init__(self, cons):
        
        self.cons = cons
        self.sqlpath = cons.SQL_PATH
        self.influxdb_org = cons.INFLUXDB_ORG
        self.influxdb_client = cons.INFLUXDB_CLIENT
        self.influxdb_query_api = cons.INFLUXDB_QUERY_API
        self.sql_connection = sqlite3.connect(f'{self.sqlpath}')
        self.sql_cursor = self.sql_connection.cursor()
        self.local_tz = pytz.timezone('US/Eastern')
   
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

    def insert_ndbc_data(self, ndbc_data):
        now = datetime.now()
        self.sql_cursor.execute("select reporttime from ndbcdata "+
          "order by reporttime desc limit 1")
        sql_reply = self.sql_cursor.fetchone()
        new_report_time = ndbc_data.get('DateTime')
        if sql_reply and sql_reply[0] == new_report_time:
            return            
        database_time = datetime.strftime(now, self.cons.TIME_FORMAT)
        database_values = (
          database_time,
          ndbc_data.get('DateTime'), 
          ndbc_data.get('Location'), 
          ndbc_data.get('Wind Direction'), 
          ndbc_data.get('Wind Speed'), 
          ndbc_data.get('wind Gust'), 
          ndbc_data.get('Wave Height'),
          ndbc_data.get('Wave Period'), 
          ndbc_data.get('Temperature'), 
          ndbc_data.get('Water Temperature'), 
          ndbc_data.get('Wave Direction'),
          ndbc_data.get('Atmospheric Pressure'))

        self.sql_cursor.execute(
          f"INSERT INTO ndbcdata VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
          database_values)
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
            try:
                station = int(data_dict.get('S'))
                location = 'River 1' if station == 1 else 'River 2'
                distance = int(data_dict['R'])
                distance_feet = round(distance*0.03937007874,2)
                database_values = (
                  database_time,
                  station,
                  location,                    
                  int(data_dict.get('P')), 
                  round(float(data_dict.get('V'))/1000,3),'', 
                  int(data_dict.get('C')),
                  distance_feet,
                  distance,
                  int(data_dict.get('M'))          
                  )
            except:
                return
            self.sql_cursor.execute(
              f"INSERT INTO sensors VALUES (?,?,?,?,?,?,?,?,?,?)",
              database_values)
            self.sql_connection.commit()
            message_time = datetime.utcnow()
            point_tide_station = Point("tide_station") \
              .tag("location", "Beaufort River SC") \
              .tag(self.cons.INFLUXDB_COLUMN_NAMES["S"],
                int(data_dict["S"])) \
              .tag("sensor_type", "ultrasonic MB7389") \
              .field(self.cons.INFLUXDB_COLUMN_NAMES["V"],
                int(data_dict["V"])) \
              .field(self.cons.INFLUXDB_COLUMN_NAMES["C"],
                int(data_dict["C"])) \
              .field(self.cons.INFLUXDB_COLUMN_NAMES["R"],
                int(data_dict["R"])) \
              .field(self.cons.INFLUXDB_COLUMN_NAMES["M"],
                int(data_dict["M"])) \
              .field(self.cons.INFLUXDB_COLUMN_NAMES["P"],
                int(data_dict["P"])) \
              .time(message_time, WritePrecision.MS)
            write_api = self.influxdb_client.write_api(
              write_options=SYNCHRONOUS)
            result = write_api.write(self.cons.INFLUXDB_BUCKET,
              self.cons.INFLUXDB_ORG, point_tide_station)

        except Exception as errmsg:
            logging.warning('insert_tide: '+str(errmsg))            

    def fetch_predicts(self, tide_start_time):
        try:        
            self.sql_cursor.execute(
              f"select * from predicts where dtime >= '{tide_start_time}' "+
                "order by dtime")
            return self.sql_cursor.fetchall()

        except Exception as errmsg:
            logging.warning('fetch_predicts: '+str(errmsg))
            return None            
 
    def fetch_iparams(self):
        iparams_list = (
          'stationid',
          'noalert',
          'wxavail',
          'wxsource',
          'wxtime',
          'station1cal',
          'station2cal',
          's1enable',
          's2enable',
          'debug'
        )
        banner_list = (
          'alertmsg',
          'sunrise',
          'sunset',
          'dispdate',
          'banflag'
        )
        iparams_dict = {}
        try:        
            self.sql_cursor.execute("select * from iparams")
            params = self.sql_cursor.fetchone()
            for index, entry in enumerate(params):
                iparams_dict[iparams_list[index]] = entry
            self.sql_cursor.execute("select * from banner")
            params = self.sql_cursor.fetchone()
            for index, entry in enumerate(params):
                iparams_dict[banner_list[index]] = entry
            return iparams_dict                

        except Exception as errmsg:
            logging.warning('fetch_iparams: '+str(errmsg))
            return None

    def fetch_tide_24h(self, stationid, station1cal ,station2cal):
        """Fetch the last 24 hours of tide measurements for plotting"""
        self.influx_query = ('from(bucket:"TideData") '+
          '|> range(start: -24h) '+
          '|> filter(fn:(r) => r._measurement == "tide_station") '+
          '|> filter(fn: (r) => r.location == "Beaufort River SC") '+
          f'|> filter(fn: (r) => r.sensor_num == "{str(stationid)}") '+
          '|> filter(fn: (r) => r._field == "sensor_measurement_mm")')
        tide_list = []
        try:
            query_result = self.influxdb_query_api.query(
            org=self.influxdb_org, query=self.influx_query)
            for table in query_result:
                for record in table.records:
                    utc_time = record.get_time()
                    local_time = utc_time.replace(
                      tzinfo=pytz.utc).astimezone(self.local_tz)
                    local_time = self.local_tz.normalize(local_time)
                    local_time = datetime.strftime(
                      local_time,"%Y-%m-%d %H:%M:%S")
                    tide_mm = record.get_value()
                    if tide_mm:
                        if stationid == 1:
                            tide = station1cal-tide_mm/304.8
                        else:
                            tide = station2cal-tide_mm/304.8                            
                        tide_list.append([local_time, tide, ''])
                   
            return tide_list
            
        except Exception as errmsg:
            logging.warning('fetch_tide_24h: '+str(errmsg))

    def update_stationid(self, stationid):
        self.sql_cursor.execute(f"update iparams set stationid = {stationid}")
        self.sql_connection.commit()
        
    def fetch_userpass(self):
        self.sql_cursor.execute("select dtime, emailaddr, valstat, valkey from userpass where valkey != ''")
        return self.sql_cursor.fetchall()

    def update_userpass(self, emailaddr, valstat, valkey):       
        with open('k1','rb') as kfile:
           key1 = kfile.read()
        f1 = Fernet(key1)
        if valstat == 1:
            self.sql_cursor.execute(f"UPDATE userpass set valkey = '' where valkey = '{valkey}'")
        else:
            self.sql_cursor.execute(f"delete from userpass where valkey = '{valkey}'")
            self.sql_connection.commit()
            val_address = emailaddr.encode()
            val_address = f1.decrypt(val_address).decode()
            pline = (f'Request window expired for {val_address}')
            logging.info(pline)
        
    def update_datetime(self, date, sunrise, sunset):
        self.sql_cursor.execute(f"update banner set dispdate = '{date}',"+
          f"sunrise = '{sunrise}', sunset = '{sunset}'")
        self.sql_connection.commit()
