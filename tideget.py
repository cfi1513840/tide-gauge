from datetime import datetime, timedelta
import json
import requests
import socket
import urllib3.util.connection
import logging
import math
import feedparser
import logging

class GetWeather:
    def __init__(self, cons, val, notify):
        self.cons = cons
        self.val = val
        self.notify = notify
        self.wx_und_report_flag = 0
        self.wx_opn_report_flag = 0
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
                    f"Subject: BBI {source} Failure",
                    "To: "+email_recipient,"MIME-Versiion:1.0",
                    "Content-Type:text/html"]
            email_headers = "\r\n".join(email_headers)
            text_message = ("From "+self.cons.HOSTNAME+": "+
            self.message_time+
            f" - 5 consecutive failures requesting {source} data")
            logging.debug (email_headers+' '+text_message)
            self.notify.send_email(email_recipient, email_headers,
              text_message, self.cons.debug)
        for twilio_phone_recipient in self.cons.ADMIN_TEL_NBRS:
            self.notify.send_SMS(twilio_phone_recipient,
              text_message, self.cons.debug)
            
    def report_success(self, count, source):
        for email_recipient in self.cons.ADMIN_EMAIL:
            email_headers = [
              "From: " + self.cons.EMAIL_USERNAME,
              f"Subject: BBI {source} Restored",
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
              self.cons.debug)
        for twilio_phone_recipient in self.cons.ADMIN_TEL_NBRS:
            self.notify.send_SMS(twilio_phone_recipient,
              text_message, self.cons.debug)
        pline = f'{source} restored'
        logging.info(pline)

class GetNDBC:
    """ Read marine observation data from the NDBC API"""     
    def __init__(self, cons, val, notify):
        self.cons = cons
        self.val = val
        self.notify = notify
        #urllib3.util.connection.allowed_gai_family = socket.AF_INET
       
    def read_station(self, tide_only):
        #print ('getting NDBC')
        if tide_only: return {}
        stations = self.cons.NDBC_STATIONS
        ndbc_keys = [
          'DateTime',
          'Location',
          'Air Temperature',
          'Wind Direction',
          'Wind Speed',
          'Wind Gust',
          'Wave Height',
          'Wave Period',
          'Air Temperature',
          'Water Temperature',
          'Wave Direction',
          'Atmospheric Pressure']
        ndbc_dict = {
          'DateTime': '',
          'Location': '',
          'Air Temperature': '',
          'Wind Direction': '',
          'Wind Speed': '',
          'Wind Gust': '',
          'Wave Height': '',
          'Wave Period': '',
          'Air Temperature': '',
          'Water Temperature': '',
          'Wave Direction': '',
          'Atmospheric Pressure': ''}
        try:
            count = 0
            for station in stations:
                """ for testing, read data from file
                  if count == 0:
                      with open('ndbc.txt', 'r') as file:
                          obsfull = file.read()
                      count += 1
                  else:
                      with open('ndbc2.txt', 'r') as file:
                          obsfull = file.read()
                  """       
                obsfull =  str(feedparser.parse(
                  f'https://www.ndbc.noaa.gov/data/latest_obs/{station}.rss'))
                
                work_dict = {}
                #
                # extract and save time
                #        
                #print (obsfull)
                date_found = False
                dteindx = obsfull.find('EDT')
                print ('dteindx: '+str(dteindx))
                if dteindx == -1:
                    dteindx = obsfull.find('EST')
                    print ('dteindx: '+str(dteindx))
                if dteindx != -1:
                    dtsindx = obsfull.find('>', dteindx-35)+1
                    print ('dtsindx: '+str(dtsindx))
                    if dtsindx != -1:
                        print ('dtsindx: '+str(dtsindx)+' dteindx: '+str(dteindx))
                        print (obsfull[dtsindx:dteindx])
                        date_found = True
                if dtsindx != -1:
                    xtime = datetime.strptime(
                      obsfull[dtsindx:dteindx].strip(),'%B %d, %Y %I:%M %p')
                    dtime = datetime.strftime(xtime,'%Y-%m-%d %H:%M:00')
                    work_dict['DateTime'] = dtime
                for key in ndbc_keys:
                    #
                    # Extract and save observation values using key list
                    #
                    kidx = obsfull.find(key)
                    if kidx != -1:
                        dtsindx = obsfull.find('>', kidx)
                        dtsindx += 1
                        dteindx = obsfull.find('<', dtsindx)
                        value = " ".join(obsfull[dtsindx:dteindx].split())
                        if key != 'Location':
                            dteindx = value.find(' ')
                            value = value[:dteindx]
                        value = value.replace('&#176;F', '')
                        work_dict[key] = value
                ndbc_dict = ndbc_dict | work_dict
            return ndbc_dict
        except:
            logging.warning('Error obtaining NDBC data')
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
            

