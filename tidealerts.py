import sqlite3
from datetime import datetime
from statistics import median
import time
import pytz
import logging
import tidecrypto

class TideAlerts:
    """Check conditions against alert table and provide notification as required"""
    def __init__(self, cons, db, notify):
        self.cons = cons
        self.db = db
        self.notify = notify
        self.sql_connection = sqlite3.connect(self.cons.SQL_PATH)
        self.sql_cursor = self.sql_connection.cursor()
        self.save_alert_list = []
        # Validated 20-minute rolling window of tide levels, used both to
        # flag an implausible reading (deviates > OUTLIER_MAX_DEVIATION_FT
        # from the window) and to detect rising/falling phase. Starts
        # empty rather than pre-seeded with 20 zeros: a candidate is only
        # added once it has passed the check below, so a bad reading
        # during startup (or ever) can't corrupt the baseline it's being
        # judged against. The first few samples are accepted outright
        # (nothing to meaningfully compare against yet); from there,
        # candidates are checked against the MEDIAN of what's validated
        # so far while the window is still filling (median stays robust
        # with only a handful of samples, unlike a mean, which a single
        # bad value can drag arbitrarily far off), then against the MEAN
        # once the full 20-sample window is established (steady state).
        self.tide_average = []
        self._last_stationid = None
        self.OUTLIER_MAX_DEVIATION_FT = 1
        self.OUTLIER_BOOTSTRAP_UNCONDITIONAL = 4
        self.OUTLIER_WINDOW_SIZE = 20
        self.last_average = 0
        self.average = 0
        self.phase = ''
        self.wind_samples = [0 for x in range(0,30)]
        self.f1 = tidecrypto.EMAIL_KEY
        self.f2 = tidecrypto.PHONE_KEY
       
    def check_alerts(self, tide, weather, ndbc_data, sunrise, sunset, debug,
      stationid=None):
        # tide_average is a single shared buffer for whichever station is
        # currently selected -- it isn't keyed per sensor the way
        # insert_tide()'s outlier buffers are. If the active station
        # changes (manual iparams change, or the automatic failover
        # logic in tide.py's main()), the two sensors' calibrated
        # readings may not agree closely enough to both sit inside the
        # existing 1 ft window, even when neither is malfunctioning --
        # so treat a station change exactly like a fresh restart: reset
        # the buffer and let it re-bootstrap against the new sensor,
        # rather than judging its readings against a baseline that no
        # longer applies.
        if stationid is not None and stationid != self._last_stationid:
            self.tide_average = []
            self._last_stationid = stationid
        current_time = datetime.now()
        message_time = datetime.strftime(current_time, self.cons.TIME_FORMAT)

        def to_float_or_none(raw_value):
            # External weather/NDBC sources may hand back a proper float,
            # an int, a numeric string, an empty string, or None depending
            # on the source and conditions -- normalize all of that to
            # either a real float or None, so every comparison downstream
            # can safely rely on "not None means it's a usable number."
            if raw_value is None:
                return None
            try:
                return float(raw_value)
            except (TypeError, ValueError):
                return None

        temperature = to_float_or_none(weather.get('temperature'))
        wind_speed = to_float_or_none(weather.get('wind_speed'))
        wind_gust = to_float_or_none(weather.get('wind_gust'))
        wind_direction = weather.get('wind_direction_symbol')
        tide_level = tide
        water_temp = to_float_or_none(ndbc_data.get('Water Temperature'))
        #
        # Get the times for the next high and low tides
        #
        self.sql_cursor.execute(
          f"select * from predicts where dtime >= '{str(current_time)}' limit 2")
        nextides = self.sql_cursor.fetchall()
        nextlowtime = datetime.now()
        nexthightime = datetime.now()
        for nextide in nextides:
            if nextide[2] == 'L':
                nextlowtide_f = nextide[1]
                nextlowtide = format(nextide[1],'.2f')
                nextlowtime = nextide[0]
                nextlowtime = datetime.strptime(
                  nextlowtime, self.cons.TIME_FORMAT)
            elif nextide[2] == 'H':
                nexthightide_f = nextide[1]
                nexthightide = format(nextide[1],'.2f')
                nexthightime = nextide[0]
                nexthightime = datetime.strptime(
                  nexthightime, self.cons.TIME_FORMAT)
                  
        localtime = datetime.now(pytz.timezone('US/Eastern'))
        secstohigh = round((nexthightime-current_time).total_seconds())
        mintohigh = round(secstohigh/60)
        secstolow = round((nextlowtime-current_time).total_seconds())
        mintolow = round(secstolow/60)

        self.sql_cursor.execute("select * from useralerts")
        column_names = [description[0] for description in self.sql_cursor.description]
        #print (column_names)
        rows = self.sql_cursor.fetchall()
        alert_list = []
        for row in rows:
            alert_dict= {}
            for index, column in enumerate(row):
                alert_dict[column_names[index]] = column
            alert_list.append(alert_dict)
        if self.save_alert_list:
            for index, alert_dict in enumerate(alert_list):
                for sindex, save_entry in enumerate(self.save_alert_list):
                    if save_entry['dtime'] == alert_dict['dtime']:
                        #print ('entry found, updating status to ',
                        #  str(save_entry['tide_level_status']))
                        alert_list[index]['tide_level_status'] = \
                          save_entry['tide_level_status']
                        alert_list[index]['air_temp_status'] = \
                          save_entry['air_temp_status']
                        alert_list[index]['wind_speed_status'] = \
                          save_entry['wind_speed_status']
                        alert_list[index]['tidal_variation_status'] = \
                          save_entry['tidal_variation_status']
                        alert_list[index]['water_temp_status'] = \
                          save_entry['water_temp_status']
                        alert_list[index]['event_repeat'] = \
                          save_entry['event_repeat']
        n = len(self.tide_average)
        if n < self.OUTLIER_BOOTSTRAP_UNCONDITIONAL:
            # Not enough samples yet to meaningfully judge a candidate --
            # accept it outright.
            self.tide_average.append(tide_level)
            return
        elif n < self.OUTLIER_WINDOW_SIZE:
            # Still filling the window: check against the median of what
            # has been validated so far (robust to the few outliers that
            # might already be mixed in), then add if it passes.
            check_tide = median(self.tide_average)
            if (tide_level > check_tide + self.OUTLIER_MAX_DEVIATION_FT or
              tide_level < check_tide - self.OUTLIER_MAX_DEVIATION_FT):
                logging.warning(message_time+' invalid tide level: '+
                  str(tide_level)+' versus running median: '+str(check_tide))
                return
            self.tide_average.append(tide_level)
            return
        # Steady state: full 20-sample window established. Check against
        # the mean of the current window BEFORE adding the candidate, so
        # a rejected reading never enters the window at all (previously,
        # the candidate was added first and could still skew the average
        # for the following 19 cycles even when the alert cycle itself
        # was skipped for it).
        check_tide = sum(self.tide_average)/self.OUTLIER_WINDOW_SIZE
        if (tide_level > check_tide + self.OUTLIER_MAX_DEVIATION_FT or
          tide_level < check_tide - self.OUTLIER_MAX_DEVIATION_FT):
            logging.warning (message_time+' invalid tide level: '+
              str(tide_level)+' versus 20 minute average: '+str(check_tide))
            return
        self.tide_average = self.tide_average[1:]+[tide_level]
        self.average = sum(self.tide_average[10:])/10
        self.last_average = sum(self.tide_average[:10])/10
        if self.average > self.last_average + 0.05:
            self.phase = 'Rising'
        elif self.average < self.last_average - 0.05:
            self.phase = 'Falling'
        for index, alert_dict in enumerate(alert_list):
            emailAddress = alert_dict['email_address'].encode()
            emailAddress = self.f1.decrypt(emailAddress).decode()
            email_recipient = emailAddress
            alert_dict['email_address'] = email_recipient
            if (alert_dict['phone_number'] != None and 
              alert_dict['phone_number'] != '' and
              alert_dict['phone_number'] != 0):
                telnbr = alert_dict['phone_number'].encode()
                telnbr = self.f2.decrypt(telnbr).decode()
                alert_dict['phone_number'] = telnbr
            else:
                telnbr = ''
            #
            # Process tide level alerts
            #
            enabled = alert_dict['tide_level_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['tide_level_day_only']
            status = alert_dict['tide_level_status']
            value = alert_dict['tide_level']
            if value == None:
                value = ''
            
            if (enabled and activated and tide_level != None and value != ''):
                db_level = float(value)
                email_headers = [
                  "From: " +self.cons.EMAIL_USERNAME, 
                  "Subject: Tide Level Alert",
                  "To: "+email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)
                if status == 0 and self.phase == 'Rising':                        
                    if (tide_level >= db_level and 
                      tide_level < db_level+0.1):
                        alert_list[index]['tide_level_status'] = 2
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+" - The tide level is "+
                              format(tide_level, '.2f')+
                              " feet and Rising, please check "+
                              f"{self.cons.TIDE_URL} "+
                              "for current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION) 

                elif status == 0 and self.phase == 'Falling':          
                    if (tide_level <= db_level and
                      tide_level > db_level-0.1):
                        alert_list[index]['tide_level_status'] = 1
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+" - The tide Level is "+
                              format(tide_level, '.2f')+
                              " feet and Falling, please check "+
                              f"{self.cons.TIDE_URL} "+
                              "for current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                              text_message, debug, self.cons.STATION_LOCATION) 

                elif status == 1 and self.phase == 'Rising':
                    if (tide_level >= db_level and
                      tide_level < db_level+0.1):
                        alert_list[index]['tide_level_status'] = 2
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+" - The tide level is "+
                              format(tide_level, '.2f')+
                              " feet and Rising, please check "+
                              f"{self.cons.TIDE_URL} "+
                              "for current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION) 
                            
                elif status == 2 and self.phase == 'Falling':
                    if (tide_level <= db_level and
                      tide_level > db_level-0.1):
                        alert_list[index]['tide_level_status'] = 1
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+" - The tide level is "+
                              format(tide_level, '.2f')+" feet and Falling, "+
                              f"please check {self.cons.TIDE_URL} "+
                              "for current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION) 
            #
            # Process air temperature alerts
            #
            enabled = alert_dict['air_temp_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['air_temp_day_only']
            status = alert_dict['air_temp_status']
            value = alert_dict['air_temp']
            if value == None:
                value = ''
            
            if (enabled and activated and temperature != None and value != ''):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Air Temperature Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)

                if status == 0:
                    if (temperature is not None and temperature >= db_level-0.1 and
                      temperature < db_level+0.1):
                        alert_list[index]['air_temp_status'] = 1
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+
                              " - The Air Temperature has reached "+
                              str(temperature)+" degrees F"+
                              f", please check {self.cons.TIDE_URL} "+
                              "for current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION) 
                else:
                    if (temperature is not None and temperature <= db_level-2.5 or
                      temperature >= db_level+2.5):
                        alert_list[index]['air_temp_status'] = 0

            #
            # Process water temperature alerts
            #
            enabled = alert_dict['water_temp_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['water_temp_day_only']
            status = alert_dict['water_temp_status']
            value = alert_dict['water_temp']
            if value == None:
                value = ''
            
            if (enabled and activated and water_temp != None and value != ''):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Water Temperature Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)

                if status == 0:
                    if (water_temp >= db_level-0.5 and 
                      water_temp < db_level+0.5):
                        alert_list[index]['water_temp_status'] = 1
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+
                              " - The Water Temperature has reached "+
                              str(int(round(water_temp)))+" degrees F,"+ 
                              f" please check {self.cons.TIDE_URL} for "+
                              "current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION) 
                else:
                    if (water_temp <= db_level-1.0 or
                      water_temp >= db_level+1.0):
                        alert_list[index]['water_temp_status'] = 0

            #
            # Process wind alerts
            #
            enabled = alert_dict['wind_speed_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['wind_speed_day_only']
            status = alert_dict['wind_speed_status']
            value = alert_dict['wind_speed']
            if value == None:
                value = ''
            direction = alert_dict['wind_direction']
            
            if (enabled and activated and wind_speed != None and value != ''):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Wind Speed Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)
                if wind_speed is not None and wind_gust is not None:
                    windfact = max(wind_speed,wind_gust)
                    self.wind_samples = self.wind_samples[1:]+[windfact]
                else:
                    windfact = 0
                if status == 0:
                    if ((windfact > db_level) and (direction == '' or
                      direction == wind_direction)):
                        alert_list[index]['wind_speed_status'] = 1
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+
                              " The wind speed has exceeded "+str(db_level)+ 
                              " mph "+direction+" - please check "+
                              f"{self.cons.TIDE_URL} for "+
                              "current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION) 

                elif status == 1:
                    if max(self.wind_samples) < db_level:
                        logging.debug('db: '+str(db_level)+'stat: '+str(status)+' wind_samples: '+str(self.wind_samples))
                        alert_list[index]['wind_speed_status'] = 0
                        if (not dayonly or (dayonly and (localtime > sunrise and
                          localtime < sunset))):
                            text_message = (
                              message_time+" - The wind speed has abated to "+
                              "less than "+str(db_level)+" mph, please check "+
                              f"{self.cons.TIDE_URL} for "+
                              "current conditions")
                            self.notify.send_email(email_recipient,
                              email_headers, text_message, debug)
                            if len(telnbr) != 0:
                                self.notify.send_SMS(telnbr,
                                  text_message, debug, self.cons.STATION_LOCATION)
            #
            # Process tidal variance alerts
            #
            enabled = alert_dict['tidal_variation_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['tidal_variation_day_only']
            status = alert_dict['tidal_variation_status']
            value = alert_dict['tidal_variation']
            if value == None:
                value = ''
           
            if (enabled and activated and tide_level != None and
              value != '' and (not dayonly or (dayonly and (localtime > sunrise and
              localtime < sunset)))):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Tidal Variation Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)

                if (db_level > 0 and
                  (tide_level-nexthightide_f) >= db_level and secstohigh < 60):
                    dispdiff = format(abs(tide_level-nexthightide_f), '.2f')
                    text_message = (
                      message_time+" - The tide level is higher than the "+
                      "predicted high tide by "+dispdiff+" feet"+
                      f", please check {self.cons.TIDE_URL} for "+
                      "current conditions")
                    self.notify.send_email(email_recipient,
                      email_headers, text_message, debug)
                    if len(telnbr) != 0:
                        self.notify.send_SMS(telnbr,
                          text_message, debug, self.cons.STATION_LOCATION)

                elif (db_level < 0 and
                  (tide_level-nextlowtide_f) <= db_level and secstolow < 60):
                    dispdiff = format(abs(tide_level-nextlowtide_f), '.2f')
                    text_message = (
                      message_time+" - The tide level is lower than the "+
                      "predicted low tide by "+dispdiff+" feet"+
                      f", please check {self.cons.TIDE_URL} for "+
                      "current conditions")
                    self.notify.send_email(email_recipient,
                      email_headers, text_message, debug)
                    if len(telnbr) != 0:
                        self.notify.send_SMS(telnbr,
                          text_message, debug, self.cons.STATION_LOCATION)
            #
            # Process tidal event alert
            #
            enabled = alert_dict['event_notice_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['event_day_only']
            event_type = alert_dict['event_type']
            notice = alert_dict['event_notice']
            repeat = alert_dict['event_repeat']
            thresh = alert_dict['event_thresh']
           
            if ((enabled and activated and (not dayonly or (dayonly and 
              (localtime > sunrise and localtime < sunset)))) and
              repeat != 0 and notice != ''):
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Tidal Event Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)

                if notice == mintolow and event_type == 1:
                    if (thresh == '' or thresh == None or
                      thresh > nextlowtide_f): 
                        text_message = (
                          message_time+" - The next predicted low tide "+
                          "of "+nextlowtide+" feet will occur in "+
                          str(mintolow)+" minutes at "+str(nextlowtime))
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug, self.cons.STATION_LOCATION)
                        if repeat != 0:
                            repeat = repeat-1
                            alert_list[index]['event_repeat'] = repeat
                            
                elif notice == mintohigh and event_type == 2:
                    if (thresh == '' or thresh == None or
                      thresh < nexthightide_f): 
                        text_message = (
                          message_time+" The next predicted high tide of "+
                          nexthightide+" feet will occur in "+
                          str(mintohigh)+" minutes at "+str(nexthightime))
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug, self.cons.STATION_LOCATION)
                        if repeat != 0:
                            repeat = repeat-1
                            alert_list[index]['event_repeat'] = repeat

        self.save_alert_list = alert_list
