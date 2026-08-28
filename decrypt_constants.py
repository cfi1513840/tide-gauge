#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""decrypt_constants.py

Companion to encrypt_constants.py: decrypts every value in an
encrypted tide_constants.json (or a backup copy of one) with the
Fernet key at /home/tide/bin/tidegauge/ku, and writes the clear-text
result to tide_constants_decrypted.tmp for review or editing. Used
when adding a parameter to an existing station's constants file
without losing the values already encrypted there -- decrypt, edit
the clear-text copy, then re-encrypt with encrypt_constants.py.

No clear-text version is left behind beyond the one .tmp file this
produces -- delete it once encrypt_constants.py has been run against
the edited copy.

Usage: python3 decrypt_constants.py <encrypted_json_file>

Requires ku to already exist -- see makekeys.py.
"""
import json
import sys
import os
from cryptography.fernet import Fernet

if len(sys.argv) == 1:
    print('input file not specified')
    exit()
infile = sys.argv[1]
if os.path.exists(infile):
    print(f'Using input file {infile}')
else:
    print('Non-existent input file specified')
    exit()
with open('/home/tide/bin/tidegauge/ku', 'r') as file:
    key = file.read()
enkey = Fernet(key)
#
# Read encrypted variables from json file
#
with open(infile, 'r') as file:
    dictjson = file.read()
secure_dict = json.loads(dictjson)
#
# Save decrypted attributes in dictionary 'secure_dict'
#
for ent in secure_dict:
    clearval = enkey.decrypt(secure_dict[ent].encode())
    secure_dict[ent] = clearval.decode()
    print(ent, secure_dict[ent])
with open('tide_constants_decrypted.tmp', 'w') as outfile:
    json.dump(secure_dict, outfile, indent=4)
print('Decrypted constants file written to tide_constants_decrypted.tmp')
