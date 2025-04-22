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
import json
import math
import smtplib
import socket
import sqlite3
import time
import smtplib
import tkinter as tk
from tkinter import StringVar
from datetime import datetime, timedelta, timezone
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from cryptography.fernet import Fernet
from suntime import Sun, SunTimeException
from twilio.rest import Client
import feedparser
#import serial
import requests
import logging
import tidehelper
import tideget
import tidedatabase
import tidepredict
import tideprocess

#
# Setup Logging to console and file
#
logger = logging.getLogger(__name__)
logging.basicConfig(filename='newtide.log',
  level = logging.INFO if 'log' in sys.argv else logging.WARNING,
  format="%(asctime)s [%(levelname)s] %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO if 'print' in sys.argv else logging.WARNING)
logging.getLogger('').addHandler(console)
logger.info('tide.py initializing')

sunny = tidehelper.SunTime()
cons = tidehelper.Constants()
state = tidehelper.TideState()
notify = tidehelper.Notify(cons)
getwx = tideget.GetWeather(cons, notify, state)
db = tidedatabase.DbManage(cons)
getndbc = tideget.GetNDBC(cons, notify, state)
getnoaa = tideget.GetNOAA(cons, state)
sensor = tideget.ReadSensor(cons, state)
predict = tidepredict.TidePredict(cons, db)

class Tide:
    def __init__(self):
        current_time = datetime.now()
        self.display = None
        self.newtime = 0
        self.last_ndbc_time = current_time
        self.last_alert_time = current_time
        self.last_weather_time = current_time
        self.main_loop_count = 0
        self.tide1 = 0
        self.tide2 = 0
        self.save_the_day = datetime.strftime(current_time, "%d")
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
        self.tk_mode = False if 'notk' in sys.argv else True
        if self.tk_mode:
            import tidedisplay
            self.iparams_dict = db.fetch_iparams()
            self.stationid = self.iparams_dict.get('stationid')
            self.station1cal = self.iparams_dict.get('station1cal')
            self.station2cal = self.iparams_dict.get('station2cal')
            self.s1enable = self.iparams_dict.get('s1enable')
            self.s2enable = self.iparams_dict.get('s2enable')
            display_date_and_time = sunny.get_suntimes(cons)
            self.display = tidedisplay.TideDisplay(self.stationid, cons)
            self.display.master.title("BBI Tide Monitor Panel "+
              display_date_and_time[0]+" Sunrise: "+display_date_and_time[1]+
              " Sunset: "+display_date_and_time[2])
            self.main()
            twilio_phone_recipient = cons.TWILIO_PHONE_RECIPIENT
            email_recipient = cons.ADMIN_EMAIL[0]
            text = f'testing at {str(datetime.now())}'
            #notify.send_SMS(twilio_phone_recipient, text)
            email_headers = ["From: " + cons.EMAIL_USERNAME,
              "Subject: BBI Tide Station Alert Message", "To: "
              +email_recipient,"MIME-Versiion:1.0",
              "Content-Type:text/html"]
            email_headers =  "\r\n".join(email_headers)
            #notify.send_email(email_recipient, email_headers, text)
            weather = getwx.weather_underground()
            if not weather:
                weather = getwx.open_weather_map()
            if weather:
                db.insert_weather(weather)
            #print ('get ndbcdata')
            ndbc_data = getndbc.read_station()
            #print (state.ndbc_data)
            if ndbc_data:
                db.insert_ndbc_data(ndbc_data)            
            self.display.update(weather, ndbc_data)
            if 'noaa' in sys.argv:
                noaa_tide = getnoaa.noaa_tide()
                if noaa_tide:
                    db.insert_tide_predicts(noaa_tide)
            predict_list = predict.tide_predict()
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
        current_time = datetime.now()
        current_day = datetime.strftime(current_time, "%d")
        if self.display:
            #
            # If in the tkinter display mode, apply timing correction
            # to the next scheduled iteration, as required.
            #
            correction = 0
            if self.newtime == 0:
                self.display.master.after(5000, self.main)
                self.newtime = current_time + timedelta(seconds=5)
            else:
                tdelta = current_time - self.newtime
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
        tide_readings = sensor.read_sensor()
        if tide_readings:
            db.insert_tide(tide_readings)
            tide = 0
            volts = 0
            rssi = 0
            try:
                tide_mm = int(tide_readings['R'])
                station = int(tide_readings['S'])
                volts = float(tide_readings['V'])/1000
                rssi = int(tide_readings['P'])
                if station == 1 and self.stationid == 1:
                    self.display.station1_battery_voltage_tk_var.set(str(volts))    
                    self.display.station1_signal_strength_tk_var.set(str(rssi))    
                    tide = round(self.station1cal-tide_mm/304.8, 2)
                elif station == 2 and self.stationid == 2:
                    self.display.station2_battery_voltage_tk_var.set(str(volts))    
                    self.display.station2_signal_strength_tk_var.set(str(rssi))    
                    tide = round(self.station2cal-tide_mm/304.8, 2)
                if tide != 0:
                    self.tide_list = self.process.update_tide_list(self.tide_list, tide)
            except Exception as errmsg:
                pass

        if (self.main_loop_count == 2 and 
          current_time >= self.last_weather_time + timedelta(minutes=3)):
            #
            # Local weather is updated every three minutes
            #
            self.last_weather_time = current_time
            ndbc_data = {}
            weather = {}
            #print ('Updating Weather')
            weather = getwx.weather_underground()
            if not weather:
                weather = getwx.open_weather_map()
            if weather:
                db.insert_weather(weather)
                self.display.update(weather, ndbc_data)
                
        if (self.main_loop_count == 4 and 
          current_time >= self.last_ndbc_time + timedelta(minutes=10)):
            #
            # The marine observation is updated every 10 minutes
            #
            self.last_ndbc_time = current_time
            weather = {}
            ndbc_data = []
            ndbc_data = getndbc.read_station()
            if ndbc_data:
                db.insert_ndbc_data(ndbc_data)
                self.display.update(weather, ndbc_data)

        if (self.main_loop_count == 6 and self.save_the_day != current_day):
            #
            # The display title bar and NOAA tide predictions are update daily
            #
            self.save_the_day = current_day              
            display_date_and_time = sunny.get_suntimes(cons)
            self.display.master.title("BBI Tide Monitor Panel "+
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
            self.display.active_station_tk_var.set(str(self.stationid))    
            predict_list = predict.tide_predict()
            self.display.tide(predict_list, self.tide_list)
            #print (tide_list)
#
# Start the ball rolling
#
tide = Tide()


    

