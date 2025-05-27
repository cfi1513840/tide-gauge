#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: tide.py
Author: K. Howell
Version: 1.0
Date: 2025-03-29
Description:
Acquire, process and display the data obtained from various sensors and
weather reports. Combine current observations with atmospheric and marine
forecasts for local display and website presentation.
"""
import sys
import subprocess
from datetime import datetime, timedelta
import logging
import tidehelper
import tideget
import tidedatabase
import tidepredict
import tideprocess
import tidealerts
import tidehtml
import tidewxhtml
#
# Setup Logging to console and file
#
logger = logging.getLogger(__name__)
level = logging.WARNING
if 'debug' in sys.argv:
    level = logging.DEBUG
elif 'log' in sys.argv:
    level = logging.INFO

logging.basicConfig(filename='newtide.log',
  level = level,
  format="%(asctime)s [%(levelname)s] %(message)s")
#logging.basicConfig"filename='newtide.log',
#  level = logging.INFO if 'log' in sys.argv else logging.WARNING,
#  format="%(asctime)s [%(levelname)s] %(message)s")
console = logging.StreamHandler()
#console.setLevel(logging.INFO if 'print' in sys.argv else logging.WARNING)
console.setLevel(level)
logging.getLogger('').addHandler(console)
logging.info('tide.py initializing')

sunny = tidehelper.SunTime()
cons = tidehelper.Constants()
state = tidehelper.TideState()
notify = tidehelper.Notify(cons)
getwx = tideget.GetWeather(cons, notify)
db = tidedatabase.DbManage(cons)
getndbc = tideget.GetNDBC(cons, notify)
getnoaa = tideget.GetNOAA(cons)
if 'sim' not in sys.argv:    
    sensor = tideget.ReadSensor(cons)
predict = tidepredict.TidePredict(cons, db)
alerts = tidealerts.TideAlerts(cons, db, notify)
html = tidehtml.CreateHTML(cons)
wxhtml = tidewxhtml.CreateWxHTML(cons)

class Tide:
    """The Tide class is the primary tide station processor and scheduler"""
    def __init__(self):
        self.current_time = datetime.now()
        self.message_time = datetime.strftime(
          self.current_time, cons.TIME_FORMAT)
        self.display = None
        self.newtime = 0
        self.last_ndbc_time = self.current_time
        self.last_alert_time = self.current_time
        self.last_weather_time = self.current_time
        self.last_station1_time = self.current_time
        self.last_station2_time = self.current_time
        self.main_loop_count = 0
        self.debug = 0
        self.tide1 = 0
        self.tide2 = 0
        self.tide_ft = 99
        self.weather = {}
        self.ndbc_data = {}
        self.save_the_day = datetime.strftime(self.current_time, "%d")
        self.iparams_dict = db.fetch_iparams()
        #
        # Extract the value of the test argument, if specified. This will be
        # used to determine the test cases to be run on various modules.
        #
        for arg in sys.argv:
            if "=" in arg:
                name, value = arg.split("=", 1)
                if name == "test":
                    state.test_mode = int(value)
        if 'notk' in sys.argv:
            self.tk_mode = False
        else:
            self.tk_mode = True
        if self.tk_mode:
            import tidedisplay
            self.iparams_dict = db.fetch_iparams()
            self.stationid = self.iparams_dict.get('stationid')
            self.station1cal = self.iparams_dict.get('station1cal')
            self.station2cal = self.iparams_dict.get('station2cal')
            self.s1enable = self.iparams_dict.get('s1enable')
            self.s2enable = self.iparams_dict.get('s2enable')
            self.debug = self.iparams_dict.get('debug')
            display_date_and_time = sunny.get_suntimes(cons, db)
            self.sunrise = display_date_and_time[3]
            self.sunset = display_date_and_time[4]
            self.display = tidedisplay.TideDisplay(self.stationid, cons)
            self.display.master.title(
              f"{cons.STATION_LOCATION} Tide Monitor Panel "+
              display_date_and_time[0]+" Sunrise: "+display_date_and_time[1]+
              " Sunset: "+display_date_and_time[2])
            self.main()
            twilio_phone_recipient = cons.TWILIO_PHONE_RECIPIENT
            email_recipient = cons.ADMIN_EMAIL[0]
            text = f'Tide Station startup at {self.message_time}'
            notify.send_SMS(twilio_phone_recipient, text, self.debug)
            email_headers = ["From: " + cons.EMAIL_USERNAME,
              F"Subject: {cons.STATION_LOCATION} Tide Station Alert Message", "To: "
              +email_recipient,"MIME-Versiion:1.0",
              "Content-Type:text/html"]
            email_headers =  "\r\n".join(email_headers)
            notify.send_email(email_recipient, email_headers, text, self.debug,)
            self.weather = getwx.weather_underground()
            if not self.weather:
                self.weather = getwx.open_weather_map()
            if self.weather:
                db.insert_weather(self.weather)
            wxhtml.wxproc(self.iparams_dict)
            #print ('get ndbcdata')
            self.ndbc_data = getndbc.read_station()
            if self.ndbc_data:
                db.insert_ndbc_data(self.ndbc_data)
            self.display.update(self.weather, self.ndbc_data)
            if 'noaa' in sys.argv:
                noaa_tide = getnoaa.noaa_tide()
                if noaa_tide:
                    db.insert_tide_predicts(noaa_tide)
            predict_list = predict.tide_predict()
            tide_readings = []
            if 'sim' not in sys.argv:    
                tide_readings = sensor.read_sensor()
            if tide_readings:
                db.insert_tide(tide_readings)
            tide_list = db.fetch_tide_24h(
              self.stationid, self.station1cal, self.station2cal)
            self.process = tideprocess.ProcTide(tide_list)
            self.tide_list = self.process.get_tide_list()

            if predict_list and self.tide_list:
                self.display.tide(predict_list, tide_list)
            self.display.master.mainloop()

    def main(self):
        """The primary scheduling loop"""
        self.current_time = datetime.now()
        self.message_time = datetime.strftime(self.current_time, cons.TIME_FORMAT)
        current_day = datetime.strftime(self.current_time, "%d")
        current_minute = datetime.strftime(self.current_time, "%M")
        if self.display:
            #
            # If in the tkinter display mode, apply timing correction
            # to the next scheduled iteration, as required.
            #
            correction = 0
            if self.newtime == 0:
                self.display.master.after(5000, self.main)
                self.newtime = self.current_time + timedelta(seconds=5)
            else:
                tdelta = self.current_time - self.newtime
                correction = int((
                  tdelta.microseconds+tdelta.seconds*1000000)/5000)
                self.display.master.after(5000-correction, self.main)
                self.newtime = self.newtime + timedelta(seconds=5)

        self.main_loop_count += 1
        #
        # The task scheduler operates as a loop that executes once every
        # five seconds. The tide sensor is read every iteration. Other tasks
        # such as reading data or weather inputs from the web or access to
        # the databases are scheduled at different intervals during
        # each minute to distribute CPU time and to avoid database access
        # conflicts. NOAA tide predictions are updated daily.
        #
        tide_readings = []
        if 'sim' not in sys.argv:    
            tide_readings = sensor.read_sensor()
        if tide_readings:
            db.insert_tide(tide_readings)
            volts = 0
            rssi = 0
            try:
                tide_mm = int(tide_readings['R'])
                station = int(tide_readings['S'])
                volts = float(tide_readings['V'])/1000
                rssi = int(tide_readings['P'])
                if station == 1:
                    self.last_station1_time = self.current_time
                    if self.stationid == 1:
                        self.display.station_battery_voltage_tk_var.set(
                          str(volts))
                        self.display.station_signal_strength_tk_var.set(
                          str(rssi))
                        self.tide_ft = round(self.station1cal-tide_mm/304.8, 2)
                elif station == 2:
                    self.last_station2_time = self.current_time
                    if self.stationid == 2:
                        self.display.station_battery_voltage_tk_var.set(
                          str(volts))
                        self.display.station_signal_strength_tk_var.set(
                          str(rssi))
                        self.tide_ft = round(self.station2cal-tide_mm/304.8, 2)
                if self.tide_ft != 99:
                    self.tide_list = self.process.update_tide_list(
                      self.tide_list, self.tide_ft)
            except:
                pass

        if (self.main_loop_count == 2 and
          self.current_time >= self.last_weather_time + timedelta(minutes=3)):
            #
            # Local weather is updated every three minutes
            #
            self.last_weather_time = self.current_time
            #print ('Updating Weather')
            self.weather = getwx.weather_underground()
            if not self.weather:
                self.weather = getwx.open_weather_map()
            if self.weather:
                db.insert_weather(self.weather)
                self.display.update(self.weather, self.ndbc_data)

        if self.main_loop_count == 3:
            valkeys = db.fetch_userpass()
            if valkeys:
                for valkey in valkeys:
                    #print (str(valkey[0]),valkey[1])
                    valtime = datetime.strptime(valkey[0],'%Y-%m-%d %H:%M:%S.%f')
                    if self.current_time >= valtime+timedelta(minutes=10):
                        db.update_userpass(valkey[1], valkey[2], valkey[3])

        if (self.main_loop_count == 4 and
          self.current_time >= self.last_ndbc_time + timedelta(minutes=10)):
            #
            # The marine observation is updated every 10 minutes
            #
            self.last_ndbc_time = self.current_time
            self.ndbc_data = getndbc.read_station()
            if self.ndbc_data:
                db.insert_ndbc_data(self.ndbc_data)

        if (self.main_loop_count == 5 and self.current_time.hour == 7 and
          self.current_time.minute == 0):
            #
            # Webpage visit reports are sent to admin every day at 07:00
            #
            self.send_visit_report()

        if (self.main_loop_count == 6 and self.save_the_day != current_day):
            #
            # The display title bar and NOAA tide predictions are update daily
            #
            self.save_the_day = current_day
            display_date_and_time = sunny.get_suntimes(cons, db)
            self.sunrise = display_date_and_time[3]
            self.sunset = display_date_and_time[4]
            self.display.master.title(f"{cons.STATION_LOCATION} Tide Monitor Panel "+
              display_date_and_time[0]+" Sunrise: "+display_date_and_time[1]+
              " Sunset: "+display_date_and_time[2])
            noaa_tide = getnoaa.noaa_tide()
            if noaa_tide:
                db.insert_tide_predicts(noaa_tide)

        if self.main_loop_count >= 12:
            self.main_loop_count = 0
            self.iparams_dict = db.fetch_iparams()
            self.stationid = self.iparams_dict.get('stationid')
            self.station1cal = self.iparams_dict.get('station1cal')
            self.station2cal = self.iparams_dict.get('station2cal')
            self.debug = self.iparams_dict.get('debug')
            #print (self.ndbc_data)
            #print (self.weather)
            self.display.active_station_tk_var.set(str(self.stationid))
            predict_list = predict.tide_predict()
            self.display.update(self.weather, self.ndbc_data)
            self.display.tide(predict_list, self.tide_list)
            if current_minute == '00':
                wxhtml.wxproc(self.iparams_dict)
            html.create(self.weather, self.ndbc_data, predict_list,
              self.tide_list, self.iparams_dict)
            alt_station = 2 if self.stationid == 1 else 1
            if ((self.stationid == 1 and self.current_time >
              self.last_station1_time + timedelta(minutes=5)) or
              (self.stationid == 2 and self.current_time >
              self.last_station2_time + timedelta(minutes=5))):
                twilio_phone_recipient = cons.TWILIO_PHONE_RECIPIENT
                email_recipient = cons.ADMIN_EMAIL[0]
                text = (self.message_time+f' Station {self.stationid} has not reported in '+
                  f'over 5 minutes, switching to Station {str(alt_station)}')
                notify.send_SMS(twilio_phone_recipient, text, self.debug)
                email_headers = ["From: " + cons.EMAIL_USERNAME,
                  f"Subject: {cons.STATION_LOCATION} Tide Station Alert Message", "To: "
                  +email_recipient,"MIME-Versiion:1.0",
                  "Content-Type:text/html"]
                email_headers =  "\r\n".join(email_headers)
                notify.send_email(email_recipient, email_headers, text,
                  self.debug)
                self.stationid = alt_station
                db.update_stationid(alt_station)
            if self.tide_ft != 99:
                alerts.check_alerts(self.tide_ft, self.weather,
                  self.ndbc_data, self.sunrise, self.sunset, self.debug)
            #print (tide_list)

    def send_visit_report(self):

        grephome = ["grep -o 'CoastalMaine.png' /var/log/apache2/access.log.1  | wc -l"]
        greptide = ["grep -o 'POST /tide.html' /var/log/apache2/access.log.1  | wc -l"]
        grepuser = ["grep -o 'GET /alertlogin.html' /var/log/apache2/access.log.1  | wc -l"]
        grepumod = ["grep -o 'POST /cgi-bin/alertform.cgi' /var/log/apache2/access.log.1  | wc -l"]
        homecount = subprocess.check_output(grephome,shell=True)
        homecount = int(homecount)
        tidecount = subprocess.check_output(greptide,shell=True)
        tidecount = int(tidecount)
        usercount = subprocess.check_output(grepuser,shell=True)
        usercount = int(usercount)
        umodcount = subprocess.check_output(grepumod,shell=True)
        umodcount = int(umodcount)
        with open('/var/log/apache2/access.log.1', 'r') as visfile:
            vislines = visfile.readlines()
        visfields = vislines[0].split()
        visdate = visfields[3][1:12]
        for email_recip in cons.ADMIN_EMAIL:
            if email_recip == 'None':
                continue
            headers = ["From: " + cons.EMAIL_USERNAME,
              "Subject: BBI Tide Station Visits", "To: "+
              email_recip,"MIME-Versiion:1.0","Content-Type:text/html"]
            headers = "\r\n".join(headers)
            email_message = ("From "+cons.HOSTNAME+": "+self.message_time+
              " - Page Hits on "+visdate+
              "<br />Home Page - "+str(homecount)+
              "<br />Current Tide Page - "+str(tidecount)+
              "<br />User Alert Login Form - "+str(usercount)+
              "<br />User Alert Update - "+str(umodcount))
            text_message = ("From "+cons.HOSTNAME+": "+self.message_time+
              " - Page Hits on "+visdate+
              "\nHome Page - "+str(homecount)+
              "\nTide Page - "+str(tidecount)+
              "\nAlert Login Page - "+str(usercount)+
              "\nAlert Form - "+str(umodcount))

            twilio_phone_recipient = cons.TWILIO_PHONE_RECIPIENT
            email_recipient = cons.ADMIN_EMAIL[0]
            notify.send_SMS(twilio_phone_recipient, text_message, self.debug)
            email_headers = ["From: " + cons.EMAIL_USERNAME,
              f"Subject: {cons.STATION_LOCATION} Tide Station Visits", "To: "
              +email_recipient,"MIME-Versiion:1.0",
              "Content-Type:text/html"]
            email_headers =  "\r\n".join(email_headers)
            notify.send_email(email_recipient, email_headers,
              email_message, self.debug,)
#
# Start the ball rolling
#
tide = Tide()
