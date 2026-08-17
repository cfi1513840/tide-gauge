#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: tidehelper.py
Author: K. Howell
Version: 1.1
Date: 2026-07-30
Description:
Provides the following utility functions: sending email and sms messages,
acquiring sunrise and sunset times and declaring system constants,
checking variable field types, and formatting website visit reports.
"""
from __future__ import annotations

import os
import subprocess
import math
import smtplib
import json
import re
import socket
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import logging
from suntime import Sun
import pytz
from cryptography.fernet import Fernet
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client_3 import InfluxDBClient3
from dotenv import load_dotenv, find_dotenv
from twilio.rest import Client
from email.message import EmailMessage
from urllib.parse import urlparse


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
    # Load tide.env early so INFLUXDB_CLOUD_ORG/BUCKET are available before
    # constructing INFLUXDB_CLOUD_WRITE_CLIENT below (load_dotenv is safe to
    # call again later, in the main tide.env block further down that loads
    # everything else -- see 'envfile = find_dotenv(...)' below).
    load_dotenv(find_dotenv('tide.env'))
    # --- Local InfluxDB 3 Core (primary write target; every node has its own) ---
    # URL/DATABASE moved to tide.env -- not secrets, just endpoints/identifiers.
    # Only the token itself is a real credential.
    INFLUXDB_LOCAL_URL = os.getenv('INFLUXDB_LOCAL_URL')
    INFLUXDB_LOCAL_TOKEN = secure_dict.get('INFLUXDB_LOCAL_TOKEN')
    INFLUXDB_LOCAL_DATABASE = os.getenv('INFLUXDB_LOCAL_DATABASE')
    # --- InfluxDB Cloud Serverless (sync target; shared org/bucket across nodes) ---
    # URL moved to tide.env for the same reason.
    INFLUXDB_CLOUD_URL = os.getenv('INFLUXDB_CLOUD_URL')
    INFLUXDB_CLOUD_TOKEN = secure_dict.get('INFLUXDB_CLOUD_TOKEN')
    # INFLUXDB_CLOUD_ORG/BUCKET moved to tide.env -- not secrets, just the
    # standard TideGauge/TideData names shared across all nodes.
    INFLUXDB_CLOUD_ORG = os.getenv('INFLUXDB_CLOUD_ORG')
    INFLUXDB_CLOUD_BUCKET = os.getenv('INFLUXDB_CLOUD_BUCKET')
    # --- Point tag/field values shared by both local and cloud writes ---
    # (INFLUXDB_MEASUREMENT/LOCATION/SENSOR moved to tide.env -- not
    # secrets, see the tide.env-derived block below)
    # NOTE: InfluxDB 3 Core has no "org" concept -- org is a v2/Cloud-only
    # construct. The v2-compatible write endpoint (/api/v2/write) that
    # InfluxDBClient targets accepts a blank org string against local
    # InfluxDB 3 Core; ORG_FOR_LOCAL_WRITES exists only to make that
    # explicit rather than passing '' inline at each call site.
    ORG_FOR_LOCAL_WRITES = ''
    # Writes (cloud only, still v2-compatible) -- local writes now go
    # through INFLUXDB_LOCAL_QUERY_CLIENT below via the native v3
    # write_lp API, which measured roughly 2x faster than the v2
    # compatibility endpoint on TestBelfastTide.
    INFLUXDB_CLOUD_WRITE_CLIENT = InfluxDBClient(url=INFLUXDB_CLOUD_URL,
      token=INFLUXDB_CLOUD_TOKEN, org=INFLUXDB_CLOUD_ORG)
    # Queries AND local writes -- InfluxDB 3 native client. Queries are
    # required to go this way since InfluxDB 3 does not support Flux/v2
    # queries; write_use_v2_api=False routes local writes through the
    # native /api/v3/write_lp endpoint instead of the v2-compatible
    # /api/v2/write endpoint, which was found to be roughly 2x slower
    # for local (same-host) writes. write_accept_partial=False is
    # important: the client's own default (True) lets a write "succeed"
    # from Python's point of view even when InfluxDB rejects some or all
    # of the data server-side, with no exception raised -- this caused a
    # real, silent multi-hour data gap on TestBelfastTide. With it False,
    # any rejected write raises InfluxDBPartialWriteError (with per-line
    # detail) instead, which insert_tide()'s existing except block logs.
    INFLUXDB_LOCAL_QUERY_CLIENT = InfluxDBClient3(host=INFLUXDB_LOCAL_URL,
      token=INFLUXDB_LOCAL_TOKEN, database=INFLUXDB_LOCAL_DATABASE,
      write_use_v2_api=False, write_accept_partial=False)
    OBSCAPE_USER = secure_dict.get('OBSCAPE_USER')
    OBSCAPE_KEY = secure_dict.get('OBSCAPE_KEY')
    NOTEHUB_SECRET = secure_dict.get('NOTEHUB_SECRET')
    # (SMTP_SERVER/SMTP_PORT moved to tide.env -- not secrets, see the
    # tide.env-derived block below)
    BREVO_SMTP_SERVER = secure_dict.get('BREVO_SMTP_SERVER')
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
        # HOME_DIRECTORY was documented in tide.env but never actually loaded
        # into Constants before -- needed now by sync_influxdb_cloud()'s
        # watermark file path (tidedatabase.py).
        HOME_DIRECTORY = os.getenv('HOME_DIRECTORY')
        # Moved from tide_constants.json -- not secrets, and moving them
        # here means site-specific edits no longer require the
        # decrypt-edit-encrypt cycle.
        INFLUXDB_MEASUREMENT = os.getenv('INFLUXDB_MEASUREMENT')
        INFLUXDB_LOCATION = os.getenv('INFLUXDB_LOCATION')
        INFLUXDB_SENSOR = os.getenv('INFLUXDB_SENSOR')
        SMTP_SERVER = os.getenv('SMTP_SERVER')
        SMTP_PORT = os.getenv('SMTP_PORT')
        NWS_RADAR = os.getenv('NWS_RADAR')
        TK_CANVAS_WIDTH = os.getenv('TK_CANVAS_WIDTH')
        TK_CANVAS_HEIGHT = os.getenv('TK_CANVAS_HEIGHT')
        TK_FULLSCREEN = os.getenv('TK_FULLSCREEN')
        SERIAL_PORTS = os.getenv('SERIAL_PORTS').split(",")
        WX_OPEN_URL = os.getenv('WX_OPEN_URL')
        USB0_BAUDRATE = os.getenv('USB0_BAUDRATE')
        USB1_BAUDRATE = os.getenv('USB1_BAUDRATE')
        SENSOR_SOURCE = os.getenv('SENSOR_SOURCE')

        # Station number -> Sensor ID lookup, built from the indexed
        # STATIONn_NUM/SENSOR_ID/LOCATION groups in tide.env (up to 3
        # stations). Used by tideget.py's read_sensor() to tag LoRa
        # packets with a Sensor ID, since LoRa hardware doesn't transmit
        # one natively the way Notecard sensors do. Blank/missing slots
        # are skipped.
        STATION_SENSOR_IDS = {}
        STATION_LOCATIONS = {}
        for _n in (1, 2, 3):
            _num = os.getenv(f'STATION{_n}_NUM')
            _sid = os.getenv(f'STATION{_n}_SENSOR_ID')
            _loc = os.getenv(f'STATION{_n}_LOCATION')
            if _num and _sid:
                STATION_SENSOR_IDS[int(_num)] = _sid
                STATION_LOCATIONS[int(_num)] = _loc or ''

    else:
        print ('Unable to load Environment file')

    with open("/sys/class/graphics/fb0/virtual_size", "r") as f:
        screen_res = f.read().strip().split(',')

    TK_SCREEN_WIDTH = screen_res[0]
    TK_SCREEN_HEIGHT = screen_res[1]

    FULL_TIDE = math.pi
    HALF_TIDE = math.pi/2
    HOSTNAME = socket.gethostname()
    with open('sensor_fields.json', 'r') as infile:
        INFLUXDB_NAMES = json.load(infile)
    RADIANS_PER_SECOND = math.pi*2/91080
    TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    
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
            logging.warning('Error processing sunrise/sunset - '+str(errmsg), exc_info=True)
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
            logging.warning(str(errmsg), exc_info=True)

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
                self.cons.SMTP_PORT, timeout=10)
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
                logging.warning(str(errmsg), exc_info=True)
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
                with smtplib.SMTP(self.cons.BREVO_SMTP_SERVER, self.cons.SMTP_PORT, timeout=10) as server:
                    server.starttls()
                    server.login(self.cons.BREVO_USERNAME, self.cons.BREVO_PASSWORD)
                    server.send_message(msg)
                return True, None
            except Exception as errmsg:
                logging.warning(str(errmsg), exc_info=True)
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
                logging.warning(f'mailspool: could not read {filename}: {errmsg}', exc_info=True)
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

class DailyVisitReport:
    """
    Parses an Apache2 "combined" format access log and produces a plain-text
    summary of visits to a fixed set of tracked pages.

    Counting rule: a line counts as a "visit" to a tracked page if the
    request path (query string ignored) matches one of the tracked paths
    AND the response status is < 400 (i.e. it was actually served, not a
    404/403/5xx). This filters out the constant background noise of bots
    probing for pages that don't exist, while still counting real page
    loads regardless of HTTP method (GET, POST, HEAD) -- which matters for
    pages like the alert form CGI that are visited via POST.
    """

    # Ordered so the report always lists categories in this sequence,
    # even when a category had zero visits.
    CATEGORIES: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
        [
            ("Tide & Weather", ("/tide.html",)),
            ("Alert Login", ("/alertlogin.html",)),
            ("Alert Form", ("/cgi-bin/alertform.cgi",)),
            ("Alert Request", ("/cgi-bin/processalerts.cgi",)),
            ("Historical Analysis", ("/tideplot.html", "/cgi-bin/tideplot.cgi")),
        ]
    )

    # Apache "combined" log format:
    # %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"
    LOG_LINE_RE = re.compile(
        r'^(?P<host>\S+) (?P<ident>\S+) (?P<user>\S+) '
        r'\[(?P<time>[^\]]+)\] '
        r'"(?P<request>[^"]*)" '
        r'(?P<status>\d{3}) (?P<size>\S+) '
        r'"(?P<referer>[^"]*)" "(?P<agent>[^"]*)"'
    )

    # First token of the quoted request line, e.g. GET /tide.html HTTP/1.1
    REQUEST_LINE_RE = re.compile(r'^(?P<method>\S+) (?P<path>\S+) (?P<protocol>\S+)$')

    APACHE_TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"
    REPORT_DATE_FORMAT = "%B %d, %Y"

    # tide.html auto-refreshes itself every 5 minutes. A repeat hit from the
    # same host is treated as an auto refresh (rather than a fresh page load)
    # only if BOTH hold: its Referer is the tide page itself, AND it lands
    # within +/- AUTO_REFRESH_TOLERANCE_SECONDS of exactly
    # AUTO_REFRESH_INTERVAL_SECONDS after that host's last tide.html hit.
    # A manual reload landing by chance in that narrow window is considered
    # negligibly unlikely.
    AUTO_REFRESH_CATEGORY = "Tide & Weather"
    AUTO_REFRESH_SOURCE_PATH = "/tide.html"
    AUTO_REFRESH_INTERVAL_SECONDS = 300
    AUTO_REFRESH_TOLERANCE_SECONDS = 5

    def __init__(self, log_path: str = "/var/log/apache2/access.log.1"):
        self.log_path = Path(log_path)

        # Build a flat lookup of tracked path -> category label, so
        # categorizing a single request is an O(1) dict lookup.
        self._path_to_category: dict[str, str] = {}
        for label, paths in self.CATEGORIES.items():
            for path in paths:
                self._path_to_category[path] = label

    def get_daily_report(self) -> str:
        """
        Read the access log and return a plain-text visit summary.

        This is the method meant to be called once a day (e.g. by a 07:00
        cron job) to retrieve the previous day's visit counts.
        """
        try:
            lines = self.log_path.read_text(errors="replace").splitlines()
        except FileNotFoundError:
            return f"Website Activity: log file not found at {self.log_path}"
        except OSError as exc:
            return f"Website Activity: unable to read log ({exc})"

        counts = OrderedDict((label, 0) for label in self.CATEGORIES)
        visitors: "OrderedDict[str, set[str]]" = OrderedDict(
            (label, set()) for label in self.CATEGORIES
        )
        auto_refresh_counts = OrderedDict((label, 0) for label in self.CATEGORIES)
        report_date: Optional[datetime] = None

        # Last-seen timestamp per host, for auto-refresh interval detection
        # on the tide.html category only.
        last_seen: dict[str, datetime] = {}

        for line in lines:
            if not line.strip():
                continue

            match = self.LOG_LINE_RE.match(line)
            if not match:
                continue

            line_time = self._parse_apache_time(match.group("time"))
            if report_date is None:
                report_date = line_time

            status = int(match.group("status"))
            if status >= 400:
                continue

            path = self._extract_path(match.group("request"))
            if path is None:
                continue

            label = self._path_to_category.get(path)
            if label is None:
                continue

            host = match.group("host")
            counts[label] += 1
            visitors[label].add(host)

            if label == self.AUTO_REFRESH_CATEGORY:
                if self._is_auto_refresh(host, line_time, match.group("referer"), last_seen):
                    auto_refresh_counts[label] += 1
                if line_time is not None:
                    last_seen[host] = line_time

        return self._format_report(report_date, counts, visitors, auto_refresh_counts)

    def _is_auto_refresh(
        self,
        host: str,
        line_time: Optional[datetime],
        referer: str,
        last_seen: "dict[str, datetime]",
    ) -> bool:
        """
        True if this hit looks like tide.html's self-triggered 5-minute
        refresh rather than a fresh page load: the Referer must be the tide
        page itself, and the gap since this host's last tide.html hit must
        fall within AUTO_REFRESH_TOLERANCE_SECONDS of exactly
        AUTO_REFRESH_INTERVAL_SECONDS.
        """
        if line_time is None or host not in last_seen:
            return False

        if urlparse(referer).path != self.AUTO_REFRESH_SOURCE_PATH:
            return False

        gap = (line_time - last_seen[host]).total_seconds()
        return abs(gap - self.AUTO_REFRESH_INTERVAL_SECONDS) <= self.AUTO_REFRESH_TOLERANCE_SECONDS

    def _extract_path(self, request_line: str) -> Optional[str]:
        """
        Pull the path (no query string) out of a request line such as
        'GET /tide.html?screenwidth=980 HTTP/1.1'. Returns None for
        malformed request lines (e.g. '-' from a timed-out connection).
        """
        match = self.REQUEST_LINE_RE.match(request_line)
        if not match:
            return None
        return match.group("path").split("?", 1)[0]

    def _parse_apache_time(self, time_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(time_str, self.APACHE_TIME_FORMAT)
        except ValueError:
            return None

    def _format_report(
        self,
        report_date: Optional[datetime],
        counts: "OrderedDict[str, int]",
        visitors: "OrderedDict[str, set[str]]",
        auto_refresh_counts: "OrderedDict[str, int]",
    ) -> str:
        if report_date is not None:
            date_str = report_date.strftime(self.REPORT_DATE_FORMAT)
        else:
            date_str = "Unknown Date"

        lines = [f"Website Activity for {date_str}"]
        for label, count in counts.items():
            unique = len(visitors[label])
            line = f"{label}: {unique} Visitor{'s' if unique != 1 else ''} requesting {count} page load{'s' if count != 1 else ''}"

            refreshes = auto_refresh_counts[label]
            if label == self.AUTO_REFRESH_CATEGORY:
                line += f" ({refreshes} auto refresh{'es' if refreshes != 1 else ''})"

            lines.append(line)

        total_hits = sum(counts.values())
        total_unique = len(set().union(*visitors.values())) if visitors else 0
        lines.append(
            f"Total: {total_unique} Visitor{'s' if total_unique != 1 else ''} "
            f"requesting {total_hits} page load{'s' if total_hits != 1 else ''}"
        )

        return "\n".join(lines)
