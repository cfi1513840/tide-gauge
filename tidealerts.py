import sqlite3
from datetime import datetime
from cryptography.fernet import Fernet
import time
import pytz

class TideAlerts:
    """Check conditions against alert table and provide notification as required"""
    def __init__(self, cons, db, notify):
        self.cons = cons
        self.db = db
        self.notify = notify
        self.sql_connection = sqlite3.connect(f'/home/tide/bin/tides.db')
        self.sql_cursor = self.sql_connection.cursor()
        self.save_alert_list = []
        self.tide_average = [0 for x in range(0,20)]
        self.last_average = 0
        self.average = 0
        self.tide_count = 0
        self.phase = ''
        self.wind_samples = [0 for x in range(0,30)]
       
    def check_alerts(self, tide, weather, ndbc_data, sunrise, sunset, debug):
        current_time = datetime.now()
        message_time = datetime.strftime(current_time, self.cons.TIME_FORMAT)
        temperature = weather.get('temperature')
        wind_speed = weather.get('wind_speed')
        wind_gust = weather.get('wind_gust')
        wind_direction = weather.get('wind_direction_symbol')
        tide_level = tide
        water_temp = ndbc_data.get('Water Temperature')
        #
        # Get the times for the next high and low tides
        #
        self.sql_cursor.execute(
          f"select * from predicts where dtime >= '{str(current_time)}' limit 2")
        nextides = self.sql_cursor.fetchall()
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

        with open('/home/tide/bin/k1','rb') as kfile:
           key1 = kfile.read()
        with open('/home/tide/bin/k2','rb') as kfile:
           key2 = kfile.read()
        f1 = Fernet(key1)
        f2 = Fernet(key2)
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
        if self.tide_count > 5:
            check_tide = sum(self.tide_average[15:])/5
            if tide_level > check_tide+1 or tide_level < check_tide-1:
                print ('invalid tide level')
                return
        self.tide_count += 1
        self.tide_average = self.tide_average[1:]+[tide_level]
        if self.tide_count < 20:
            return                
        self.average = sum(self.tide_average[10:])/10
        self.last_average = sum(self.tide_average[:10])/10
        for index, alert_dict in enumerate(alert_list):
            emailAddress = alert_dict['email_address'].encode()
            emailAddress = f1.decrypt(emailAddress).decode()
            email_recipient = emailAddress
            alert_dict['email_address'] = email_recipient
            if (alert_dict['phone_number'] != None and 
              alert_dict['phone_number'] != '' and
              alert_dict['phone_number'] != 0):
                telnbr = alert_dict['phone_number'].encode()
                telnbr = f2.decrypt(telnbr).decode()
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
            
            if ((enabled and activated and (not dayonly or (dayonly and 
              (localtime > sunrise and localtime < sunset)))) and
              value != ''):
                db_level = float(value)
                if self.average > self.last_average + 0.05:
                    self.phase = 'Rising'
                elif self.average < self.last_average - 0.05:
                    self.phase = 'Falling'
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
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" - The tide level is "+
                          format(tide_level, '.2f')+
                          " feet and Rising, please check "+
                          "https://bbitide.org/bbitide.html "+
                          "for current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 

                elif status == 0 and self.phase == 'Falling':          
                    if (tide_level <= db_level and
                      tide_level > db_level-0.1):
                        alert_list[index]['tide_level_status'] = 1
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" - The tide Level is "+
                          format(tide_level, '.2f')+
                          " feet and Falling, please check "+
                          "https://bbitide.org/bbitide.html "+
                          "for current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 

                elif status == 1 and self.phase == 'Rising':
                    if (tide_level >= db_level and
                      tide_level < db_level+0.1):
                        alert_list[index]['tide_level_status'] = 2
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" - The tide level is "+
                          format(tide_level, '.2f')+
                          " feet and Rising, please check "+
                          "https://bbitide.org/bbitide.html "+
                          "for current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 
                            
                elif status == 2 and self.phase == 'Falling':
                    if (tide_level <= db_level and
                      tide_level > db_level-0.1):
                        alert_list[index]['tide_level_status'] = 1
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" - The tide level is "+
                          format(tide_level, '.2f')+" feet and Falling, "+
                          "please check https://bbitide.org/bbitide.html "+
                          "for current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 
            #
            # Process air temperature alerts
            #
            enabled = alert_dict['air_temp_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['air_temp_day_only']
            status = alert_dict['air_temp_status']
            value = alert_dict['air_temp']
            
            if ((enabled and activated and (not dayonly or (dayonly and 
              (localtime > sunrise and localtime < sunset)))) and
              value != ''):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Air Temperature Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)

                if status == 0:
                    if (temperature != '' and temperature >= db_level-0.1 and
                      temperature < db_level+0.1):
                        alert_list[index]['air_temp_status'] = 1
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+
                          " - The Air Temperature has reached "+
                          str(temperature)+" degrees F"+
                          ", please check https://bbitide.org/bbitide.html "+
                          "for current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 
                else:
                    if (temperature != '' and temperature <= db_level-2.5 or
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
            
            if ((enabled and activated and (not dayonly or (dayonly and 
              (localtime > sunrise and localtime < sunset)))) and
              value != ''):
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
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+
                          " - The Water Temperature has reached "+
                          str(int(round(water_temp)))+" degrees F,"+ 
                          " please check https://bbitide.org/bbitide.html for "+
                          "current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 
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
            direction = alert_dict['wind_direction']
            
            if ((enabled and activated and (not dayonly or (dayonly and 
              (localtime > sunrise and localtime < sunset)))) and
              value != ''):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Wind Speed Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)
                if wind_speed != '' and wind_gust != '':
                    windfact = max(wind_speed,wind_gust)
                    self.wind_samples = self.wind_samples[1:]+[windfact]
                else:
                    windfact = 0
                if status == 0:
                    if ((windfact > db_level) and (direction == '' or
                      direction == wind_direction)):
                        alert_list[index]['wind_speed_status'] = 1
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+
                          " The wind speed has exceeded "+str(db_level)+ 
                          " mph "+direction+" - please check "+
                          "https://bbitide.org/bbitide.html for "+
                          "current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug) 
                
                else:
                    if max(wind_samples) < db_level:
                        alert_list[index]['wind_speed_status'] = 0
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" - The wind speed has abated to "+
                          "less than "+str(db_level)+" mph, please check "+
                          "https://bbitide.org/bbitide.html for "+
                          "current conditions")
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug)
            #
            # Process tidal variance alerts
            #
            enabled = alert_dict['tidal_variation_enable']
            activated = alert_dict['alerts_activated']
            dayonly = alert_dict['tidal_variation_day_only']
            status = alert_dict['tidal_variation_status']
            value = alert_dict['tidal_variation']
           
            if ((enabled and activated and (not dayonly or (dayonly and 
              (localtime > sunrise and localtime < sunset)))) and
              value != ''):
                db_level = float(value)
                email_headers = ["From: " + self.cons.EMAIL_USERNAME,
                  "Subject: Tidal Variation Alert", "To: "+
                  email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers = "\r\n".join(email_headers)

                if (db_level > 0 and
                  (tide_level-nexthightide_f) >= db_level and secstohigh < 60):
                    dispdiff = format(abs(tide_level-nexthightide_f), '.2f')
                    text_message = ("From "+self.cons.HOSTNAME+": "+
                      message_time+" - The tide level is higher than the "+
                      "predicted high tide by "+dispdiff+" feet"+
                      ", please check https://bbitide.org/bbitide.html for "+
                      "current conditions")
                    self.notify.send_email(email_recipient,
                      email_headers, text_message, debug)
                    if len(telnbr) != 0:
                        self.notify.send_SMS(telnbr,
                          text_message, debug)

                elif (db_level < 0 and
                  (tide_level-nextlowtide_f) <= db_level and secstolow < 60):
                    dispdiff = format(abs(tide_level-nextlowtide_f), '.2f')
                    text_message = ("From "+self.cons.HOSTNAME+": "+
                      message_time+" - The tide level is lower than the "+
                      "predicted low tide by "+dispdiff+" feet"+
                      ", please check https://bbitide.org/bbitide.html for "+
                      "current conditions")
                    self.notify.send_email(email_recipient,
                      email_headers, text_message, debug)
                    if len(telnbr) != 0:
                        self.notify.send_SMS(telnbr,
                          text_message, debug)
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
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" - The next predicted low tide "+
                          "of "+nextlowtide+" feet will occur in "+
                          str(mintolow)+" minutes at "+str(nextlowtime))
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug)
                        if repeat != 0:
                            repeat = repeat-1
                            alert_list[index]['event_repeat'] = repeat
                            
                elif notice == mintohigh and event_type == 2:
                    if (thresh == '' or thresh == None or
                      thresh < nexthightide_f): 
                        text_message = ("From "+self.cons.HOSTNAME+": "+
                          message_time+" The next predicted high tide of "+
                          nexthightide+" feet will occur in "+
                          str(mintohigh)+" minutes at "+str(nexthightime))
                        self.notify.send_email(email_recipient,
                          email_headers, text_message, debug)
                        if len(telnbr) != 0:
                            self.notify.send_SMS(telnbr,
                              text_message, debug)
                        if repeat != 0:
                            repeat = repeat-1
                            alert_list[index]['event_repeat'] = repeat

        self.save_alert_list = alert_list
