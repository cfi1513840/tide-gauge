#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: tidehelper.py
Author: K. Howell
Version: 1.0
Date: 2025-03-29
Description:
Provides the following utility functions: sending email and sms messages,
acquiring sunrise and sunset times and declaring system constants,
and checking variable field types.
"""
import os
import subprocess
import math
import smtplib
import json
import socket
from datetime import datetime, timedelta
import logging
from suntime import Sun
import pytz
from cryptography.fernet import Fernet
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv, find_dotenv
from twilio.rest import Client
from email.message import EmailMessage

class Constants:
    """
    Read and decrypt secure attribute values,
    and declare class attributes (CONSTANTS).
    """
    ADMIN_EMAIL = []
    ADMIN_TEL_NBRS = []
    #
    # Prepare encryption key
    #
    with open('/var/www/html/ku', 'r') as file:
        key = file.read()
    enkey = Fernet(key)
    #
    # Read encrypted variables from json file
    #
    with open('/var/www/html/tide_constants.json','r') as file:
        dictjson = file.read()
    secure_dict = json.loads(dictjson)
    tide_dictionary = {}
    #
    # Save decrypted attributes in dictionary 'secure_dict'
    #
    for ent in secure_dict:
        clearval = enkey.decrypt(secure_dict[ent].encode())
        secure_dict[ent] = clearval.decode()
        tide_dictionary[ent] = secure_dict[ent]
    #
    # Initialize secure instance attributes
    #
    if secure_dict['ADMIN1'] != 'None':
        ADMIN_EMAIL.append(secure_dict['ADMIN1'])

    if secure_dict['ADMIN2'] != 'None':
        ADMIN_EMAIL.append(secure_dict['ADMIN2'])

    if secure_dict['ADMINBRS1'] != 'None':
        ADMIN_TEL_NBRS.append(secure_dict['ADMINBRS1'])

    if secure_dict['ADMINBRS2'] != 'None':
        ADMIN_TEL_NBRS.append(secure_dict['ADMINBRS2'])
    if secure_dict.get('ADMIN') != None:
        ADMIN_EMAIL = secure_dict.get('ADMIN')
    if secure_dict.get('ADMINBRS') != None:
        ADMIN_TEL_NBRS = secure_dict.get('ADMINBRS')   

    EMAIL_USERNAME = secure_dict.get('EMAIL_USERNAME')
    EMAIL_PASSWORD = secure_dict.get('EMAIL_PASSWORD')
    BREVO_ADDRESS = secure_dict.get('BREVO_EMAIL_ADDRESS')
    BREVO_USERNAME = secure_dict.get('BREVO_EMAIL_USERNAME')
    BREVO_PASSWORD = secure_dict.get('BREVO_EMAIL_PASSWORD')
    INFLUXDB_TOKEN = secure_dict.get('INFLUXDB_TOKEN')
    INFLUXDB_READ_TOKEN = secure_dict.get('INFLUXDB_READ_TOKEN')
    INFLUXDB_WRITE_TOKEN = secure_dict.get('INFLUXDB_WRITE_TOKEN')
    INFLUXDB_ORG = secure_dict.get('INFLUXDB_ORG')
    INFLUXDB_BUCKET = secure_dict.get('INFLUXDB_BUCKET')
    INFLUXDB_MEASUREMENT = secure_dict.get('INFLUXDB_MEASUREMENT')
    INFLUXDB_LOCATION = secure_dict.get('INFLUXDB_LOCATION')
    INFLUXDB_SENSOR = secure_dict.get('INFLUXDB_SENSOR')
    INFLUXDB_READ_CLIENT = InfluxDBClient(url='http://localhost:8086',
      token=INFLUXDB_READ_TOKEN, org=INFLUXDB_ORG)
    INFLUXDB_WRITE_CLIENT = InfluxDBClient(url='http://localhost:8086',
      token=INFLUXDB_WRITE_TOKEN, org=INFLUXDB_ORG)
    INFLUXDB_QUERY_API = INFLUXDB_WRITE_CLIENT.query_api()
    OBSCAPE_USER = secure_dict.get('OBSCAPE_USER')
    OBSCAPE_KEY = secure_dict.get('OBSCAPE_KEY')
    SMTP_SERVER = secure_dict.get('SMTP_SERVER')
    BREVO_SMTP_SERVER = secure_dict.get('BREVO_SMTP_SERVER')
    SMTP_PORT = secure_dict.get('SMTP_PORT')
    TWILIO_ACCOUNT_SID = secure_dict.get('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = secure_dict.get('TWILIO_AUTH_TOKEN')
    TWILIO_CLIENT = Client(TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN)
    TWILIO_PHONE_SENDER = secure_dict.get('TWILIO_PHONE_SENDER')
    TWILIO_PHONE_RECIPIENT = secure_dict.get('TWILIO_PHONE_RECIPIENT')
    OPEN_WEATHERMAP_API = secure_dict.get('WXOPENAPI')
    WEATHER_UNDERGROUND_API = secure_dict.get('WXUNDAPI')
    WEATHER_LINK_API = secure_dict.get('WXLINKAPI')
    WEATHER_LINK_API_SECRET = secure_dict.get('WXLINKAPI_SECRET')

#    with open('tide.env', 'r') as infile:
#        lines = infile.readlines()
#    for line in lines:
#        line1 = line.replace(' ','')
#        line1 = line1.replace('\n','')
#        if len(line1) == 0:
#           continue
#        if line1[0] == '#':
#           continue
#        com = line1.find('#')
#        if com != -1:
#            line1 = line1[:com]
#        line2 = line1.split('=')
#        key = line2[0].replace(' ','')
#        value = line2[1]
#        value = value.replace("'","")
#        value = value.strip()
#        tide_dictionary[key] = value
        
    envfile = find_dotenv('tide.env')
    if load_dotenv(envfile):
        LATITUDE = float(os.getenv('STATION_LATITUDE'))
        LONGITUDE = float(os.getenv('STATION_LONGITUDE'))
        SQL_PATH = os.getenv('SQL_PATH')
        SQL_COPY = os.getenv('SQL_COPY')
        EMAIL_SERVICE = os.getenv('EMAIL_SERVICE')
        WX_SERVICE = os.getenv('WX_SERVICE')
        NDBC_STATIONS = os.getenv('NDBC_STATIONS').split(",")
        NOAA_STATION = os.getenv('NOAA_STATION')
        NOAA_STATION_NAME = os.getenv('NOAA_STATION_NAME')
        WX_UND_STATION_ID = os.getenv('WX_UND_STATION_ID')
        WX_LINK_STATION_ID = os.getenv('WX_LINK_STATION_ID')
        LOCAL_TZ = pytz.timezone(os.getenv('TIME_ZONE'))
        STATION_LOCATION = os.getenv('STATION_LOCATION')
        STATION_LATITUDE = os.getenv('STATION_LATITUDE')
        STATION_LONGITUDE = os.getenv('STATION_LONGITUDE')
        STATION_NAME = os.getenv('STATION_NAME')
        NDBC_LOCATION = os.getenv('NDBC_LOCATION')
        NDBC_LATITUDE = os.getenv('NDBC_LATITUDE')
        NDBC_LONGITUDE = os.getenv('NDBC_LONGITUDE')
        NDBC_TITLE = os.getenv('NDBC_TITLE')
        HTML_DIRECTORY = os.getenv('HTML_DIRECTORY')
        CGI_DIRECTORY = os.getenv('CGI_DIRECTORY')
        TIDE_URL = os.getenv('TIDE_URL')
        NWS_LOCAL_GRIDPOINTS = os.getenv('NWS_LOCAL_GRIDPOINTS')
        NWS_MARINE_GRIDPOINTS = os.getenv('NWS_MARINE_GRIDPOINTS')
        INFLUXDB_NAMES = os.getenv('INFLUXDB_NAMES')
        TIME_ZONE = os.getenv('TIME_ZONE')
        NWS_RADAR = os.getenv('NWS_RADAR')
        TK_CANVAS_WIDTH = os.getenv('TK_CANVAS_WIDTH')
        TK_CANVAS_HEIGHT = os.getenv('TK_CANVAS_HEIGHT')
        TK_FULLSCREEN = os.getenv('TK_FULLSCREEN')
        SERIAL_PORTS = os.getenv('SERIAL_PORTS').split(",")

    else:
        print ('Unable to load Environment file')

    with open("/sys/class/graphics/fb0/virtual_size", "r") as f:
        screen_res = f.read().strip().split(',')

    TK_SCREEN_WIDTH = screen_res[0]
    TK_SCREEN_HEIGHT = screen_res[1]

    FULL_TIDE = math.pi
    HALF_TIDE = math.pi/2
    HOSTNAME = socket.gethostname()
    INFLUXDB_COLUMN_NAMES = {
        "S": "sensor_num",
        "C": "message_count",
        "R": "sensor_measurement_mm",
        "M": "correlation_count",
        "V": "battery_milliVolts",
        "P": "signal_strength",
        "s": "solar_milliVolts",
        "t": "temperature"
        }
    with open('sensor_fields.json', 'r') as infile:
        INFLUXDB_NAMES = json.load(infile)
    RADIANS_PER_SECOND = math.pi*2/91080
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    
#    tide_dictionary['FULL_TIDE'] = str(math.pi)
#    tide_dictionary['HALF_TIDE'] = str(math.pi/2)
#    tide_dictionary['HOSTNAME'] = socket.gethostname()
#    tide_dictionary['INFLUXDB_COLUMN_NAMES'] = {
#        "S": "sensor_num",
#        "C": "message_count",
#        "R": "sensor_measurement_mm",
#        "M": "correlation_count",
#        "V": "battery_milliVolts",
#        "P": "signal_strength",
#        "s": "solar_milliVolts"
#        }
#    tide_dictionary['RADIANS_PER_SECOND'] = str(math.pi*2/91080)
#    tide_dictionary['TIME_FORMAT'] = "%Y-%m-%d %H:%M:%S"

class TideState:
    """Store state variables"""
    def __init__(self):

        self.test_mode = 0
        self.last_baro = 0
        self.debug = 0
        self.title_bar = ''

class SunTime:
    """Obtain the current date, sunrise and sunset times"""
    def get_suntimes(self, cons, db):
        try:
            current_time = datetime.now()
            display_date = current_time.strftime("%b %d, %Y")
            sun = Sun(cons.LATITUDE, cons.LONGITUDE)
            sunrise = sun.get_local_sunrise_time(time_zone=cons.LOCAL_TZ)
            sunset = sun.get_local_sunset_time(time_zone=cons.LOCAL_TZ)
            if sunset < sunrise:
                sunset = sunset + timedelta(1)
            display_sunrise = sunrise.strftime("%H:%M")
            display_sunset = sunset.strftime("%H:%M")
            db.update_datetime(display_date, display_sunrise, display_sunset)
            return display_date, display_sunrise, display_sunset, sunrise, sunset
        except Exception as errmsg:
            logging.warning('Error processing sunrise/sunset - '+str(errmsg))
            return -1

class Notify:
    """Send email and SMS message notifictions"""

    def __init__(self, cons):
        self.cons = cons

    def send_SMS(self, twilio_phone_recipient, text_message, debug):
        """Method to send status or alert information via SMS text message"""
        if debug:
            print ('SMS notify to '+ twilio_phone_recipient+'\n'+text_message)
            return
        try:
            message = self.cons.TWILIO_CLIENT.messages.create(
                    to = twilio_phone_recipient,
                    from_= self.cons.TWILIO_PHONE_SENDER,
                    body = text_message)
        except Exception as errmsg:
            logging.warning(str(errmsg))

    def send_email(self, email_recipient, email_headers, email_message, debug):
        """Method to send status or alert information via email message"""
        if debug:
            print ('Email notify to '+email_recipient+'\n'+email_message)
            return
        if self.cons.EMAIL_SERVICE != 'brevo':
            try:
                session = smtplib.SMTP(self.cons.SMTP_SERVER,
                self.cons.SMTP_PORT)
                session.ehlo()
                session.starttls()
                session.ehlo()
                session.login(self.cons.EMAIL_USERNAME,self.cons.EMAIL_PASSWORD)
                session.sendmail(
                    self.cons.EMAIL_USERNAME, email_recipient, \
                    email_headers+"\r\n\r\n"+email_message)
                session.quit()
            except Exception as errmsg:
                logging.warning(str(errmsg))
        else:    
            try:
                sub = None
                fields = email_headers.split('\r\n')
                for ent in fields:
                    ent = ent.strip()
                    if ent[:9] == 'Subject: ':
                        sub = ent[9:]
                        break
                msg = EmailMessage()
                #msg["From"] = "tidealert@bbitide.org"
                msg["From"] = self.cons.BREVO_ADDRESS
                msg["To"] = email_recipient
                msg["Subject"] = sub
                msg.set_content(email_message)
                with smtplib.SMTP(self.cons.BREVO_SMTP_SERVER, self.cons.SMTP_PORT) as server:
                    server.starttls()
                    server.login(self.cons.BREVO_USERNAME, self.cons.BREVO_PASSWORD)
                    server.send_message(msg)
                
            except Exception as errmsg:
                logging.warning(str(errmsg))

class ValType:
    """Validate variable type"""
    # return zero if variable does not match type
    def var_type(self, var, typevar):
        if typevar == float:
            try:
                newvar = float(var)
            except:
                newvar = -99
        elif typevar == int:
            try:
                newvar = int(var)
            except:
                newvar = -99
        return newvar
