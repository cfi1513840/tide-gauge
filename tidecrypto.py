#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: tidecrypto.py
Author: K. Howell
Version: 1.1
Date: 2026-07-13
Description:
Centralized loading of the Fernet keys used to encrypt subscriber
attributes at rest (email address, phone number) for the
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

Passwords are no longer encrypted with k3/Fernet -- as of 2026-07-13
they are hashed with argon2id (see hash_password/verify_password
below), since password storage only ever needs to answer "does this
match", never "what was the original value" -- unlike email/phone,
which tidealerts.py and processalerts.cgi genuinely need to recover
in order to send mail/SMS. k3/PASSWORD_KEY is retained here ONLY to
verify (and opportunistically migrate) passwords stored under the
old scheme; see is_legacy_password().
"""
from cryptography.fernet import Fernet
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

KEY_DIR = '/home/tide/bin/tidegauge/'


def _load_key(filename):
    with open(f'{KEY_DIR}{filename}', 'rb') as kfile:
        return Fernet(kfile.read())


EMAIL_KEY = _load_key('k1')
PHONE_KEY = _load_key('k2')
PASSWORD_KEY = _load_key('k3')   # legacy-verification/migration use only -- see module docstring

_hasher = PasswordHasher()

# argon2-cffi's encoded hash strings always begin with this prefix (it
# encodes the algorithm variant, version, and parameters). Fernet's
# output is urlsafe-base64 (alphabet: A-Z a-z 0-9 - _) and can never
# contain '$', so this prefix check unambiguously distinguishes a
# migrated (hashed) password from a legacy (Fernet-encrypted) one.
_ARGON2_PREFIX = '$argon2id$'


def hash_password(plaintext):
    """Return a new argon2id hash for storage. Use for both new
    passwords and completing an opportunistic migration."""
    return _hasher.hash(plaintext)


def is_legacy_password(stored):
    """True if `stored` is an old Fernet-encrypted password rather
    than an argon2id hash."""
    return not stored.startswith(_ARGON2_PREFIX)


def verify_password(plaintext, stored):
    """Check plaintext against a stored password value, whether it's
    a new argon2id hash or a legacy Fernet-encrypted value.

    Returns True/False. Does NOT perform migration itself -- callers
    that get a True result back where is_legacy_password(stored) is
    also True should immediately call hash_password(plaintext) and
    overwrite the stored value, to complete the opportunistic
    migration on that user's next successful login."""
    if is_legacy_password(stored):
        try:
            decrypted = PASSWORD_KEY.decrypt(stored.encode()).decode()
        except Exception:
            return False
        return plaintext == decrypted
    else:
        try:
            _hasher.verify(stored, plaintext)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False
