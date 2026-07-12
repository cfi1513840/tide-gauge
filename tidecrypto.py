#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: tidecrypto.py
Author: K. Howell
Version: 1.0
Date: 2026-07-12
Description:
Centralized loading of the Fernet keys used to encrypt subscriber
attributes at rest (email address, phone number, password) for the
alert-management CGI scripts (alertform.cgi, changealertpw.cgi,
forgotpass.cgi, processalerts.cgi, reset-pw-1.cgi, valuser.cgi).

k1/k2/k3 live outside the web-served document root, at the same
non-web location as ku/tide_constants.json (see tidehelper.py,
Constants class, and makekeys.py). Previously each CGI script opened
these key files and constructed its own Fernet objects independently,
with paths that had drifted between a hardcoded '/var/www/html/...'
form and an HTML_DIRECTORY-derived form -- the same class of drift
that caused the missing-CGI_URL issue found during mail-spool testing.
This module is intentionally minimal (no InfluxDB/Twilio/suntime
dependencies like tidehelper.py's Constants class) since it is
imported fresh by lightweight, per-request CGI scripts.
"""
from cryptography.fernet import Fernet

KEY_DIR = '/home/tide/bin/tidegauge/'


def _load_key(filename):
    with open(f'{KEY_DIR}{filename}', 'rb') as kfile:
        return Fernet(kfile.read())


EMAIL_KEY = _load_key('k1')
PHONE_KEY = _load_key('k2')
PASSWORD_KEY = _load_key('k3')
