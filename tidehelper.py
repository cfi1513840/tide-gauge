import math
import smtplib
from twilio.rest import Client
import sqlite3
import json
import socket
from datetime import datetime, timedelta
from suntime import Sun, SunTimeException
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from cryptography.fernet import Fernet
import logging

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
    with open('ku', 'r') as file:
        key = file.read()
    enkey = Fernet(key)
    #
    # Read encrypted variables from json file
    #
    with open('tide_constants.json','r') as file:
        dictjson = file.read()
    secure_dict = json.loads(dictjson)
    #
    # Save decrypted attributes in dictionary 'secure_dict'
    #
    for ent in secure_dict:
        clearval = enkey.decrypt(secure_dict[ent].encode())
        secure_dict[ent] = clearval.decode()
        #print (ent, secure_dict[ent])
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

    EMAIL_USERNAME = secure_dict['EMAIL_USERNAME']
    EMAIL_PASSWORD = secure_dict['EMAIL_PASSWORD']
    INFLUXDB_TOKEN = secure_dict['INFLUXDB_TOKEN']
    INFLUXDB_ORG = secure_dict['INFLUXDB_ORG']
    INFLUXDB_BUCKET = secure_dict['INFLUXDB_BUCKET']
    INFLUXDB_CLIENT = InfluxDBClient(url='http://localhost:8086',
      token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    INFLUXDB_QUERY_API = INFLUXDB_CLIENT.query_api()
    SMTP_SERVER = secure_dict['SMTP_SERVER']
    SMTP_PORT = secure_dict['SMTP_PORT']
    TWILIO_ACCOUNT_SID = secure_dict['TWILIO_ACCOUNT_SID']
    TWILIO_AUTH_TOKEN = secure_dict['TWILIO_AUTH_TOKEN']
    TWILIO_CLIENT = Client(TWILIO_ACCOUNT_SID,
            TWILIO_AUTH_TOKEN)
    TWILIO_PHONE_SENDER = secure_dict['TWILIO_PHONE_SENDER']
    TWILIO_PHONE_RECIPIENT = secure_dict['TWILIO_PHONE_RECIPIENT']
    OPEN_WEATHERMAP_API = secure_dict['WXOPENAPI']
    WEATHER_UNDERGROUND_API = secure_dict['WXUNDAPI']

    LATITUDE = 32.4
    LONGITUDE = -80.7

    FULL_TIDE = math.pi
    HALF_TIDE = math.pi/2
    HOSTNAME = socket.gethostname()
    #INFLUXDB_CLIENT = InfluxDBClient(
    #        url='http://localhost:8086',
    #        token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    INFLUXDB_COLUMN_NAMES = {
        "S": "sensor_num",
        "C": "message_count",
        "R": "sensor_measurement_mm",
        "M": "correlation_count",
        "V": "battery_milliVolts",
        "P": "signal_strength",
        }
    LOGFILE_PATH = 'bbitest.log'
    PREDICTED_TIDE_TABLE_NAME = 'predicts'
    RADIANS_PER_SECOND = math.pi*2/91080
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    SQLPATH = 'bbitides.db'
    NDBC_STATIONS = ['41033', '41067']
    NOAA_STATION = '8668686'

class TideState:
    
    def __init__(self):
    
        self.test_mode = 0
        self.last_baro = 0
    
class SunTime:
    
    def get_suntimes(self, cons):
        """Method to obtain the current date, sunrise and sunset times"""
        try:
            current_time = datetime.now()
            display_date = current_time.strftime("%b %d, %Y")
            sun = Sun(cons.LATITUDE, cons.LONGITUDE)
            sunrise = sun.get_local_sunrise_time()
            sunset = sun.get_local_sunset_time()
            if sunset < sunrise:
                sunset = sunset + timedelta(1)
            display_sunrise = sunrise.strftime("%H:%M")
            display_sunset = sunset.strftime("%H:%M")
            return display_date, display_sunrise, display_sunset
        except Exception as errmsg:
            pline = (' Error processing sunrise/sunset - '+str(errmsg))
            return -1, pline
                
class Notify:
    
    import logging
    
    def __init__(self, cons):
        self.cons = cons
    
    def send_SMS(self, twilio_phone_recipient, text_message):
        """Method to send status or other information via SMS text message"""
        try:
            message = self.cons.TWILIO_CLIENT.messages.create(
                    to = twilio_phone_recipient,
                    from_= self.cons.TWILIO_PHONE_SENDER,
                    body = text_message)
        except Exception as errmsg:
            logging.info(errmsg)

    def send_email(self, email_recipient, email_headers, email_message):
        """Method to send status or other information via email message"""
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
            logging.info(errmsg)
