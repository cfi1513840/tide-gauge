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
    with open('/home/tide/bin/tidegauge/ku', 'r') as file:
        key = file.read()
    enkey = Fernet(key)
    #
    # Read encrypted variables from json file
    #
    with open('/home/tide/bin/tidegauge/tide_constants.json','r') as file:
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
    NOTEHUB_SECRET = secure_dict.get('NOTEHUB_SECRET')
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
        #INFLUXDB_NAMES = os.getenv('INFLUXDB_NAMES')
        TIME_ZONE = os.getenv('TIME_ZONE')
        NWS_RADAR = os.getenv('NWS_RADAR')
        TK_CANVAS_WIDTH = os.getenv('TK_CANVAS_WIDTH')
        TK_CANVAS_HEIGHT = os.getenv('TK_CANVAS_HEIGHT')
        TK_FULLSCREEN = os.getenv('TK_FULLSCREEN')
        SERIAL_PORTS = os.getenv('SERIAL_PORTS').split(",")
        WX_OPEN_URL = os.getenv('WX_OPEN_URL')
        USB0_BAUDRATE = os.getenv('USB0_BAUDRATE')
        USB1_BAUDRATE = os.getenv('USB1_BAUDRATE')
        SENSOR_SOURCE = os.getenv('SENSOR_SOURCE')

    else:
        print ('Unable to load Environment file')

    with open("/sys/class/graphics/fb0/virtual_size", "r") as f:
        screen_res = f.read().strip().split(',')

    TK_SCREEN_WIDTH = screen_res[0]
    TK_SCREEN_HEIGHT = screen_res[1]

    FULL_TIDE = math.pi
    HALF_TIDE = math.pi/2
    HOSTNAME = socket.gethostname()
#    INFLUXDB_COLUMN_NAMES = {
#        "S": "sensor_num",
#        "C": "message_count",
#        "R": "sensor_measurement_mm",
#        "M": "correlation_count",
#        "V": "battery_milliVolts",
#        "P": "signal_strength",
#        "s": "solar_milliVolts",
#        "t": "temperature"
#        }
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
        """Method to send status or alert information via email message.
        Returns (success: bool, error: str or None) so callers can track
        delivery outcome; existing call sites that ignore the return value
        are unaffected."""
        if debug:
            print ('Email notify to '+email_recipient+'\n'+email_message)
            return True, None
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
                return True, None
            except Exception as errmsg:
                logging.warning(str(errmsg))
                return False, str(errmsg)
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
                return True, None
            except Exception as errmsg:
                logging.warning(str(errmsg))
                return False, str(errmsg)

    MAILSPOOL_DIR = '/var/www/html/mailspool/'
    MAILSPOOL_FAILED_DIR = '/var/www/html/mailspool/failed/'
    MAX_MAIL_ATTEMPTS = 3

    def process_mailspool(self, debug):
        """Check the mail spool directory for pending outbound email
        requests written by the alert-portal CGI scripts (which no longer
        hold email credentials or send mail themselves), and attempt to
        send each one. Requests that fail are retried on subsequent calls
        -- one per minute, via the main scheduling loop -- up to
        MAX_MAIL_ATTEMPTS times, after which they are moved to the
        'failed' subdirectory and logged. Successfully sent requests are
        simply removed; no persistent record of successful sends is kept,
        matching this system's existing fire-and-forget logging model."""
        try:
            filenames = [f for f in os.listdir(self.MAILSPOOL_DIR) if f.endswith('.json')]
        except FileNotFoundError:
            return
        for filename in filenames:
            filepath = os.path.join(self.MAILSPOOL_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    request = json.load(f)
            except Exception as errmsg:
                logging.warning(f'mailspool: could not read {filename}: {errmsg}')
                continue
            full_headers = f"From: {self.cons.EMAIL_USERNAME}\r\n" + request['headers']
            if request['recipient'] == 'ADMIN':
                # CGI scripts write 'ADMIN' rather than a real address, since
                # they no longer have access to ADMIN1/ADMIN2 (part of the
                # encrypted constants they no longer decrypt). Resolved to
                # the real admin address list here, at send-time, using
                # self.cons -- the one place that still holds it.
                targets = self.cons.ADMIN_EMAIL
            else:
                targets = [request['recipient']]
            success, error = True, None
            for target in targets:
                this_success, this_error = self.send_email(
                    target, full_headers, request['body'], debug)
                if not this_success:
                    success = False
                    error = this_error
            if success:
                os.remove(filepath)
                continue
            request['attempts'] = request.get('attempts', 0) + 1
            request['last_error'] = error
            # Write the updated attempts/error back to the original file
            # first (temp-then-rename, same pattern the CGI scripts use to
            # create these files), so what happens next -- staying pending,
            # or moving to failed/ -- always acts on current, not stale,
            # content.
            tmp_path = filepath + '.tmp'
            with open(tmp_path, 'w') as f:
                json.dump(request, f)
            os.rename(tmp_path, filepath)
            if request['attempts'] >= self.MAX_MAIL_ATTEMPTS:
                logging.warning(
                    f"mailspool: permanent failure for {filename} after "
                    f"{request['attempts']} attempts: {error}")
                failed_path = os.path.join(self.MAILSPOOL_FAILED_DIR, filename)
                os.rename(filepath, failed_path)

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
        
import re
from collections import defaultdict
from urllib.parse import urlsplit


class Visitors:

    EVENTS = {
        "Home page": (
            "Home",
            {"/", "/index.html"},
            {"GET"},
        ),
        "Tide & Weather": (
            "Tide",
            {"/tide.html"},
            {"GET", "POST"},
        ),
        "Alert Login": (
            "Login",
            {"/alertlogin.html"},
            {"GET"},
        ),
        "Alert Form Displayed": (
            "Form",
            {"/cgi-bin/alertform.cgi"},
            {"GET", "POST"},
        ),
        "Alert Request Processed": (
            "Alerts",
            {"/cgi-bin/processalerts.cgi"},
            {"POST"},
        ),
        "Historical Analysis": (
            "History",
            {"/tideplot.html"},
            {"GET", "POST"},
        ),
        "Historical Plot Generated": (
            "Plots",
            {"/cgi-bin/tideplot.cgi"},
            {"GET", "POST"},
        ),
    }

    BOT_PATTERN = re.compile(
        r"bot|spider|crawler|crawl|slurp|scan|scrapy|"
        r"wget|curl|python-requests|go-http-client|"
        r"headless|phantom|selenium|claude|bytespider|"
        r"applebot|oai-searchbot|mj12bot|domainscores|"
        r"petalbot|wp-safe-scanner",
        re.IGNORECASE,
    )

    LOG_PATTERN = re.compile(
        r'^(?P<ip>\S+) \S+ \S+ '
        r'\[(?P<time>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<url>\S+) [^"]*" '
        r'(?P<status>\d{3}) \S+ '
        r'"[^"]*" "(?P<agent>[^"]*)"'
    )

    def __init__(self, log_file):
        self.log_file = log_file
        self.report_date = None

        self.uses = defaultdict(int)
        self.visitors = defaultdict(set)

        self.bot_requests = 0
        self.unparsed_lines = 0

        self._path_lookup = self._create_path_lookup()
        self._analyze()

    def _create_path_lookup(self):
        """Create a lookup from a URL path to its report category."""

        path_lookup = {}

        for event_name, event_data in self.EVENTS.items():
            short_name, paths, methods = event_data

            for path in paths:
                path_lookup[path] = (event_name, methods)

        return path_lookup

    def _read_log(self):
        """Read and parse valid entries from the Apache log."""

        records = []

        with open(
            self.log_file,
            encoding="utf-8",
            errors="replace",
        ) as logfile:

            for line in logfile:
                match = self.LOG_PATTERN.match(line)

                if not match:
                    self.unparsed_lines += 1
                    continue

                request_time = datetime.strptime(
                    match.group("time"),
                    "%d/%b/%Y:%H:%M:%S %z",
                )

                records.append({
                    "date": request_time.date(),
                    "ip": match.group("ip"),
                    "method": match.group("method"),
                    "path": urlsplit(
                        match.group("url")
                    ).path,
                    "status": int(match.group("status")),
                    "agent": match.group("agent"),
                })

        return records

    def _analyze(self):
        """Analyze the most recent date contained in the log."""

        records = self._read_log()

        if not records:
            raise ValueError(
                f"No valid Apache entries found in {self.log_file}"
            )

        self.report_date = max(
            record["date"] for record in records
        )

        for record in records:

            # Ignore entries from earlier dates
            if record["date"] != self.report_date:
                continue

            event = self._path_lookup.get(record["path"])

            if event is None:
                continue

            event_name, allowed_methods = event

            if record["method"] not in allowed_methods:
                continue

            # Count successful and cached responses
            if not 200 <= record["status"] < 400:
                continue

            agent = record["agent"]

            if (
                not agent
                or agent == "-"
                or self.BOT_PATTERN.search(agent)
            ):
                self.bot_requests += 1
                continue

            self.uses[event_name] += 1

            # Each IP/browser combination counts once per category
            visitor_id = (
                record["ip"],
                agent,
            )

            self.visitors[event_name].add(visitor_id)
       
     def email_report(self):
    """Return a plain-text report suitable for email."""

    date_text = self.report_date.strftime("%B %d, %Y")

    lines = [
        f"Website Activity Report — {date_text}",
        "",
    ]

    for event_name in self.EVENTS:
        use_count = self.uses[event_name]
        visitor_count = len(self.visitors[event_name])

        lines.append(
            f"{event_name}: "
            f"{use_count} uses, "
            f"{visitor_count} visitors"
        )

    lines.extend([
        "",
        f"Recognizable bot requests excluded: "
        f"{self.bot_requests}",
        "",
        "Uses: Total successful requests.",
        "Visitors: Distinct IP address/browser combinations.",
    ])

    if self.unparsed_lines:
        lines.append(
            f"Unrecognized log lines: {self.unparsed_lines}"
        )

    return "\n".join(lines)   
        

    def sms_report(self):
        """Return a compact report suitable for SMS."""

        date_text = self.report_date.strftime("%m/%d/%Y")
        parts = [f"Web {date_text}"]

        for event_name, event_data in self.EVENTS.items():
            short_name, paths, methods = event_data

            parts.append(
                f"{short_name} "
                f"{self.uses[event_name]}/"
                f"{len(self.visitors[event_name])}"
            )

        return "; ".join(parts) + ". Uses/visitors."

    def reports(self):
        """Return both email and SMS reports."""

        return self.email_report(), self.sms_report()
