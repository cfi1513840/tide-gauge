from datetime import datetime, timedelta
import json
import requests
import socket
import urllib3.util.connection
import logging
import math
import feedparser
import logging
import wget
import os
import pytz

class GetWeather:
    def __init__(self, cons, val, notify):
        self.cons = cons
        self.val = val
        self.notify = notify
        self.wx_und_report_flag = 0
        self.wx_opn_report_flag = 0
        self.wx_link_report_flag = 0
        self.wx_error_count = 0
        self.last_baro = 0
        #urllib3.util.connection.allowed_gai_family = socket.AF_INET
        
    def weather_underground(self, tide_only):
        #print ('getting wx underground')
        if tide_only: return {}
        """Method to get Weather Underground observations for the local area"""
        current_time = datetime.now()
        self.message_time = current_time.strftime(
          self.cons.TIME_FORMAT)
        try:
            wxundurl = ('https://api.weather.com/v2/pws/observations/'+
                    f'current?stationId={self.cons.WX_UND_STATION_ID}&'+
                    'format=json&units=e&'+
                    f'apiKey={self.cons.WEATHER_UNDERGROUND_API}')
            #print('requesting data from wx und url')
            response = requests.get(wxundurl)
        except Exception as errmsg:
            if not self.wx_und_report_flag and self.wx_error_count > 2:
                self.wx_und_report_flag = True
                pline = ('Network read failure '+
                  'requesting Weather Underground data\n'+str(errmsg))
                logging.warning(pline)
            self.wx_error_count += 1
            if self.wx_error_count == 5:
                self.report_error('Weather Underground')
            return {}
        if str(response) != '<Response [200]>':
            if not self.wx_und_report_flag and self.wx_error_count > 2:
                self.wx_und_report_flag = True
                pline = ('Error response from '+
                  'Weather Underground network request\n'+str(response))
                logging.warning(pline)
            self.wx_error_count += 1
            if self.wx_error_count == 5:
                self.report_error('Weather Underground')
            return {}
        #
        # Log and print success message if error previously reported
        #
        if self.wx_und_report_flag:
            self.wx_und_report_flag = False
            pline = (
              'Successful Weather Underground data request\n'+str(response))
            logging.info(pline)
        #
        # Also provide email and text message success notification if required
        #
        if self.wx_error_count > 5:
            self.report_success(self.wx_error_count, 'Weather Underground')
        self.wx_error_count = 0
        #
        # Process json response from weather underground query.
        # Validate parameter formats and set corresponding local variables
        #
        try:
            result=response.json()
            #print (str(result))
            """ for testing, read data from file
              with open('wxresponse.json', 'r') as file:
                result = json.load(file)
              """
            dumpedic = json.dumps(result)
            loadedic = json.loads(dumpedic)
            observations = loadedic['observations']
            obs_time  = ''
            try:
                this_time = datetime.strptime(observations[0]['obsTimeLocal'], "%Y-%m-%d %H:%M:%S")
                obs_time = datetime.strftime(this_time, '%b %d, %Y %H:%M')
            except:
                print (observations[0]['obsTimeLocal'])
                #pass
            weather = {
              'temperature': self.val.var_type(observations[0]['imperial']['temp'], float),
              'humidity': self.val.var_type(observations[0]['humidity'], int),
              'baro': round(self.val.var_type(observations[0]['imperial']['pressure'], float),2),
              'dewpoint': self.val.var_type(observations[0]['imperial']['dewpt'], int),
              'wind_speed': self.val.var_type(observations[0]['imperial']['windSpeed'], int),
              'wind_direction_degrees': self.val.var_type(observations[0]['winddir'], int),
              'rain_rate': self.val.var_type(observations[0]['imperial']['precipRate'], float),
              'rain_today': self.val.var_type(observations[0]['imperial']['precipTotal'], float),
              'wind_gust': self.val.var_type(observations[0]['imperial']['windGust'], int),
              'obs_time': obs_time
              }
            weather['wind_direction_symbol'] = self.deg_to_direction(
                weather['wind_direction_degrees'])
            baro = weather['baro']

            if self.last_baro == 0:
                self.last_baro = baro
                weather['baro_trend'] = 0
            else:
                weather['baro_trend'] = round(baro-self.last_baro, 2)
                self.last_bar = baro
            return weather
        except Exception as errmsg:
            logging.warning(errmsg)

    def open_weather_map(self, tide_only):
        #print ('getting open_weather_map')
        if tide_only: return {}
        """Method to get OpenWeatherMap observations for the local area"""
        try:
            wxurl = ('https://api.openweathermap.org/data/2.5/weather?'+
              f'lat={self.cons.LATITUDE}&lon={self.cons.LONGITUDE}&'+
              f'units=imperial&appid={self.cons.OPEN_WEATHERMAP_API}')
            response = requests.get(wxurl)
            #print (str(response))
        except Exception as errmsg:
            if not self.wx_opn_report_flag and self.wx_error_count > 2:
                self.wx_opn_report_flag = True
                pline = ('Network read failure '+
                  'requesting OpenWeatherMap data\n'+str(errmsg))
                logging.warning(pline)
            self.wx_error_count += 1
            if self.wx_error_count == 5:
                self.report_error('OpenWeatherMap')
            return {}
        if str(response) != '<Response [200]>':
            if not self.wx_und_report_flag and self.wx_error_count > 2:
                self.wx_und_report_flag = True
                pline = ('Error response from '+
                  'OpenWeatherMap network request\n'+str(response))
                logging.warning(pline)
            self.wx_error_count += 1
            if self.wx_error_count == 5:
                self.report_error('Weather Underground')
            return {}
        #
        # Log and print success message if error previously reported
        #
        if self.wx_opn_report_flag:
            self.wx_opn_report_flag = False
            pline = (
              'Successful OpenWeatherMap data request\n'+str(response))
            logging.info(pline)
        #
        # Also provide email and text message success notification if required
        #
        if self.wx_error_count > 5:
            self.report_success(self.wx_error_count, 'OpenWeatherMap')
        self.wx_error_count = 0
        #
        # Extract weather parameters from OpenWeatherMap json response
        #
        weather = {
          'temperature': '',
          'humidity': '',
          'baro': '',
          'dewpoint': '',
          'wind_speed': '',
          'wind_direction_degrees': '',
          'rain_rate': '',
          'rain_today': '',
          'wind_gust': '',
          'wind_direction_symbol': '',
          'obs_time': ''
          }        
        try:
            result=response.json()
            #print (str(result))
            dumpedic = json.dumps(result)
            loadedic = json.loads(dumpedic)
            main = loadedic['main']
            dtime = loadedic['dt']
            if 'wind' in loadedic:
                wind = loadedic['wind']
                if 'speed' in wind:
                    weather['wind_speed'] = round(wind['speed'])
                if 'gust' in wind:                
                    weather['wind_gust'] = round(wind['gust'])
                if 'deg' in wind:
                    weather['wind_direction_degrees'] = wind['deg']
                    weather['wind_direction_symbol'] = self.deg_to_direction(
                      weather['wind_direction_degrees'])
            if 'rain' in loadedic:
                rain = loadedic['rain']
                if '1h' in rain:
                    weather['rain_rate'] = rain['1h']
                if '3h' in rain:
                    weather['rain_today'] = rain['3h']
        except ValueError as errmsg:
            logging.warning('Error processing OpenWeatherMap response')
            return {}
        weather['obs_time'] = datetime.strftime(datetime.fromtimestamp(dtime),'%b %d, %Y %H:%M')
        temperature = main['temp']
        tempcel = (temperature-32)/1.8
        pressure = main['pressure']
        weather['baro'] = format(pressure/33.864, '.2f')
        humidity = main['humidity']
        weather['humidity'] = humidity
        dewpoint = 243.04*(math.log(humidity/100)+((17.625*tempcel)/
          (243.04+tempcel)))/(17.625-math.log(humidity/100)-
          ((17.625*tempcel)/(243.04+tempcel)))
        weather['dewpoint'] = int(dewpoint*1.8+32)
        weather['temperature'] = round(temperature)
        return weather
######################################################################
    def weather_link(self, tide_only):
        #print ('getting weather link')
        if tide_only: return {}
        """Method to get WeatherLink observations for the local area"""
        #
        # Extract weather parameters from WeatherLink json response
        #
        parameters = {
          "api-key": self.cons.WEATHER_LINK_API,
          "station-id": self.cons.WX_LINK_STATION_ID,
          "t": int(time.time())
        }
        parameters = collections.OrderedDict(sorted(parameters.items()))
        apiSecret = self.cons.WEATHER_LINK_API_SECRET
        data = ""
        for key in parameters:
            data = data+key+str(parameters[key])
         #print("data string to hash is: \"{}\"".format(data))
        apiSignature = hmac.new(
            apiSecret.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        #print("API Signature is: \"{}\"".format(apiSignature))
        wxlinkurl = "https://api.weatherlink.com/v2/current/{}?api-key={}&api-signature={}&t={}".format(parameters["station-id"],parameters["api-key"], apiSignature, parameters["t"])
        #print (wxlinkurl)
        response = requests.get(wxlinkurl)

        if str(response) != '<Response [200]>':
            if not self.wx_und_report_flag and self.wx_error_count > 2:
                pline = ('Error response from '+
                  'Weather Link network request\n'+str(response))
                logging.warning(pline)
            self.wx_error_count += 1
            if self.wx_error_count == 5:
                self.wx_und_report_flag = True
                self.report_error('WeatherLink')
            return {}
        else:
            #
            # Log and print success message if error previously reported
            #
            if self.wx_link_report_flag:
                self.wx_link_report_flag = False
                pline = (
                  'Successful Weather Link data request\n'+str(response))
                logging.info(pline)
            #
            # Also provide email and text message success notification if required
            #
            if self.wx_error_count > 5:
                self.report_success(self.wx_error_count, 'Weather Underground')
            self.wx_error_count = 0
            result=response.json()
            dumpedic = json.dumps(result)
            loadedic = json.loads(dumpedic)
            sense = loadedic['sensors']
            mytime = loadedic['generated_at']
            obs_time = datetime.fromtimestamp(mytime)            
            obs_time = datetime.strftime(obs_time, '%b %d, %Y %H:%M')

            weather = {
              'temperature': self.val.var_type(sense[0]['data'][0]['temp'], float),
              'humidity': self.val.var_type(sense[0]['data'][0]['hum'], int),
              'heatindex': self.val.var_type(sense[0]['data'][0]['thw_index'], float),
              'baro': round(self.val.var_type(sense[1]['data'][0]['bar_sea_level'], float),2),
              'baro_trend': round(self.val.var_type(sense[1]['data'][0]['bar_trend'], float),3),
              'dewpoint': self.val.var_type(sense[0]['data'][0]['dew_point'], int),
              'wind_speed': self.val.var_type(sense[0]['data'][0]['wind_speed_hi_last_2_min'], int),
              'wind_direction_degrees': self.val.var_type(sense[0]['data'][0]['wind_dir_last'], int),
              'rain_rate': self.val.var_type(sense[0]['data'][0]['rain_rate_last_in'], float),
              'rain_today': self.val.var_type(sense[0]['data'][0]['rainfall_daily_in'], float),
              'wind_gust': self.val.var_type(sense[0]['data'][0]['wind_speed_hi_last_10_min'], int),
              'obs_time': obs_time
              }
            weather['wind_direction_symbol'] = self.deg_to_direction(
                weather['wind_direction_degrees'])
            return weather
        
    def deg_to_direction(self,deg):
        """Convert degrees to compass direction"""
        if deg is None:
            return ''
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        indx = int((deg+22.5) // 45) % 8
        return directions[indx]

    def report_error(self, source):
        """Generate email and text notification for weather read errors"""
        for email_recipient in self.cons.ADMIN_EMAIL:
            email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                    f"Subject: {self.cons.HOSTNAME} {source} Failure",
                    "To: "+email_recipient,"MIME-Versiion:1.0",
                    "Content-Type:text/html"]
            email_headers = "\r\n".join(email_headers)
            text_message = ("From "+self.cons.HOSTNAME+": "+
            self.message_time+
            f" - 5 consecutive failures requesting {source} data")
            logging.debug (email_headers+' '+text_message)
            self.notify.send_email(email_recipient, email_headers,
              text_message, 1)
        for twilio_phone_recipient in self.cons.ADMIN_TEL_NBRS:
            self.notify.send_SMS(twilio_phone_recipient,
              text_message, 1)
            
    def report_success(self, count, source):
        for email_recipient in self.cons.ADMIN_EMAIL:
            email_headers = [
              "From: " + self.cons.EMAIL_USERNAME,
              f"Subject: {self.cons.HOSTNAME} {source} Restored",
              "To: "+email_recipient,"MIME-Versiion:1.0",
              "Content-Type:text/html"]
            email_headers = "\r\n".join(email_headers)
            text_message = (
              "From "+self.cons.HOSTNAME+": "+
              self.message_time+
              f" - {source} query successful "+
              f"following {str(count)} consecutive failures")
            self.notify.send_email(
              email_recipient,
              email_headers,
              text_message,
              1)
        for twilio_phone_recipient in self.cons.ADMIN_TEL_NBRS:
            self.notify.send_SMS(twilio_phone_recipient,
              text_message, 1)
        pline = f'{source} restored'
        logging.info(pline)

class GetNDBC:
    """ Read marine observation data from the NDBC API"""     
    def __init__(self, cons, val, notify):
        self.cons = cons
        self.local_tz = pytz.timezone('America/New_york')
        #self.val = val
        #self.notify = notify
        #self.save_time = 0
        #self.air_temperature = 0
        #self.wind_direction = 0
        #self.wind_speed = 0
        #self.wind_gust = 0
        #self.wave_height = 0
        #self.wave_period = 0
        #self.water_temperature = 0
        #self.wave_direction = 0
        #self.atmospheric_pressure = 0
       
    def deg_to_direction(self,deg):
        """Convert degrees to compass direction"""
        if deg is None:
            return ''
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        indx = int((deg+22.5) // 45) % 8
        return directions[indx]

    def read_station(self, tide_only):
        #print ('getting NDBC')
        if tide_only: return {}
        stations = self.cons.NDBC_STATIONS
        location = ''

        try:
            ndbc_dict = {}
            for station in stations:
                if location != '':
                    location = location+','+station
                else:
                    location = station
                    
                url = f'https://www.ndbc.noaa.gov/data/realtime2/{station}.txt'
                if os.path.exists(f'{station}.txt'):
                    os.remove(f'{station}.txt')
                wget.download(url)
                with open(f'{station}.txt', 'r') as infile:
                    filines = infile.readlines()
                report_dict = dict(
                  YY='',MM='',DD='',hh='',mm='',WDIR='',WSPD='',GST='',WVHT='',DPD='',
                  APD='',MWD='',PRES='',ATMP='',WTMP='',DEWP='',VIS='',PTDY='',TIDE='')  
        
                work_dict = {} 
        
                for indx in range(0,49):
                    lindx = 50-indx
                    inline = filines[lindx]
                    fields = inline.split()
                    for kindx, key in enumerate(report_dict.keys()):
                        if fields[kindx] != 'MM':
                            report_dict[key] = fields[kindx]
        
                report_time = report_dict.get('YY')+'-'+report_dict.get('MM')+'-'+\
                           report_dict.get('DD')+' '+report_dict.get('hh')+':'+\
                           report_dict.get('mm')+':00'
                           
                utc_dt = datetime.strptime(report_time,"%Y-%m-%d %H:%M:%S")
                local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(self.local_tz)
                ndbc_time = datetime.strftime(local_dt,'%b %d, %Y %H:%M')
        
                work_dict['DateTime'] = ndbc_time
                work_dict['Location'] = location
                if report_dict.get('ATMP') != '':
                    work_dict['Air Temperature'] = str(round(float(report_dict.get('ATMP'))*1.8+32,1))
                if report_dict.get('WDIR') != '':
                    work_dict['Wind Direction'] = self.deg_to_direction(float(report_dict.get('WDIR')))
                if report_dict.get('WSPD') != '':
                    work_dict['Wind Speed'] = str(round(float(report_dict.get('WSPD'))/0.51444,1))
                if report_dict.get('GST') != '':
                    work_dict['Wind Gust'] = str(round(float(report_dict.get('GST'))/0.51444,1))
                if report_dict.get('WVHT') != '':
                    work_dict['Wave Height'] = str(round(float(report_dict.get('WVHT'))*3.28084,1))
                if report_dict.get('DPD') != '':
                    work_dict['Wave Period'] = str(report_dict.get('DPD'))
                if report_dict.get('WTMP') != '':
                    work_dict['Water Temperature'] = str(round(float(report_dict.get('WTMP'))*1.8+32,1))
                if report_dict.get('PRES') != '':
                    work_dict['Atmospheric Pressure'] = str(round(float(report_dict.get('PRES'))*0.02953,2))
                if report_dict.get('VIS') != '':
                    work_dict['Visibility'] = str(round(float(report_dict.get('VIS')),1))

                for key in work_dict.keys():
                     ndbc_dict[key] = work_dict[key]

            if 'Wave Direction' not in ndbc_dict:
                ndbc_dict['Wave Direction'] = ''                         
            if 'Atmospheric Pressure' not in ndbc_dict:
                ndbc_dict['Atmospheric Pressure'] = ''                         
            if 'Visibility' not in ndbc_dict:
                ndbc_dict['Visibility'] = ''                         
            return ndbc_dict 
        
        except Exception as errmsg:
            print ('tideget: Error attemping to read NDBC data: '+str(errmsg))
            return {}

class GetNOAA:
    """Retrieve tide predictions from the NOAA website"""
    def __init__(self, cons, val):
        self.cons = cons
        self.val = val
        #urllib3.util.connection.allowed_gai_family = socket.AF_INET

    def noaa_tide(self):
        #print ('getting noaa')
        #urllib3.util.connection.allowed_gai_family = socket.AF_INET
        noaa_data = []
        try:
            current_time = datetime.now()
            display_date = current_time.strftime("%b %d, %Y")
            purgetime = current_time - timedelta(days=7)
            pline = 'Issuing new data request to NOAA website'
            logging.info(pline)
            tidetime = current_time - timedelta(hours=36)
            begin = datetime.strftime(tidetime, "%Y%m%d")
            stationid = self.cons.NOAA_STATION
            response = requests.get("https://tidesandcurrents.noaa.gov/"
              "api/datagetter?product=predictions&"
              "application=NOS.COOPS.TAC.WL"
              f"&begin_date={begin}&range=360&datum=MLLW"
              f"&station={stationid}&time_zone=lst_ldt&units=english&"
              "interval=hilo&format=csv")   
            datalist = response.content
            strdata = str(datalist)
            datastr = strdata.split('\\n')
            #print ('noaa response',datastr)
   
            for ent in datastr:
                #print (ent)
                line = ent.split(',')
                this_time = line[0]+":00"
                try:
                    #
                    # skip incorrectly formatted time in the response
                    #
                    thisto = datetime.strptime(
                      this_time,"%Y-%m-%d %H:%M:%S")
                except:
                    continue
                noaa_data.append([this_time,self.val.var_type(line[1], float),line[2]])
            return noaa_data
        except Exception as errmsg:
            logging.warning(' Error obtaining NOAA tide - '+str(errmsg))
            return []
class ReadSensor:
    """Read sensor reading from serial port"""
    def __init__(self, cons, val):
        import serial
        self.cons = cons
        self.val = val
        self.usb_serial_input = serial.Serial(
          '/dev/ttyUSB0',9600, 8, 'N', 1, timeout = 1000)
        self.usb_serial_input.reset_input_buffer()
        
    def read_sensor(self):
        #print ('reading sensor')
        try:
            data_dict = {}
            if self.usb_serial_input.in_waiting > 0:
                now = datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S")
                packet = self.usb_serial_input.readline()
                #print (packet)
                try:
                    packet = packet.decode().split(',')
                except:
                    return data_dict
                if packet[0][0] != 'S':
                    return data_dict
                for field in packet:
                    if field[0].isalpha():
                        this_var = self.val.var_type(field[1:], int)
                        if this_var == 0:
                            data_dict = {}
                            break
                        data_dict[field[0]] = this_var
                    else:
                        continue
                return data_dict
        except Exception as errmsg:
            logging.warning('Invalid sensor data '+str(errmsg))
            

