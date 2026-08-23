#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""makekeys.py

One-off setup utility: generates the four Fernet encryption keys a
station needs (k1, k2, k3, ku -- see tidecrypto.py for what each is
used for) and writes each to its own file in the current directory.
Run once per station during initial provisioning; prompts for
confirmation before overwriting an existing ku if one is already
present, since regenerating it would make any already-encrypted
tide_constants.json unreadable.
"""
import os
from cryptography.fernet import Fernet

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
print ('Fernet keys generated')