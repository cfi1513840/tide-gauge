#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""makekeys.py

One-off setup utility: generates the four Fernet encryption keys a
station needs (k1, k2, k3, ku -- see tidecrypto.py for what each is
used for) and writes each to its own file in the current directory.
Run once per station during initial provisioning; prompts for
confirmation before overwriting an existing ku if one is already
present, since regenerating it would make any already-encrypted
tide_constants.json unreadable. Sets k1-k3 to 640 (group-readable,
for the CGI scripts running as www-data) and ku to 600 (owner only).
"""
import os
from cryptography.fernet import Fernet

# Create the key files readable by their owner only from the start,
# then open k1-k3 up to group read (640): the CGI scripts read those
# three through tidecrypto.py as www-data, a member of the tide group.
# ku stays owner-only (600) -- only tide.py and the install-time
# scripts, running as tide, ever read it.
os.umask(0o077)

if os.path.exists('ku'):
    answ = input ('Encryption keys already exist, overwrite? Y/N: ')
    if answ != 'y' and answ != 'Y':
        exit()
key = Fernet.generate_key()
with open('k1', 'w') as file:
    file.write(key.decode())
key = Fernet.generate_key()
with open('k2', 'w') as file:
    file.write(key.decode())
key = Fernet.generate_key()
with open('k3', 'w') as file:
    file.write(key.decode())
key = Fernet.generate_key()
with open('ku', 'w') as file:
    file.write(key.decode())
for kfile in ('k1', 'k2', 'k3'):
    os.chmod(kfile, 0o640)
os.chmod('ku', 0o600)
print ('Fernet keys generated')