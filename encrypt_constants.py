#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""encrypt_constants.py

One-off setup utility: encrypts every value in a plaintext JSON file
of station secrets (API tokens, credentials, etc.) with the Fernet
key at /home/tide/bin/tidegauge/ku, and writes the result to
tide_constants.tmp for review before it replaces the real
tide_constants.json. Run once per station when initially provisioning
secrets, or after rotating a value by hand.

Usage: python3 encrypt_constants.py <plaintext_json_file>

Requires ku to already exist -- see makekeys.py.
"""
import json
import sys
import os
from cryptography.fernet import Fernet

if len(sys.argv) == 1:
    print ('input file not specified')
    exit()
infile = sys.argv[1]
if os.path.exists(infile):
    print (f'Using input file {infile}')
else:    
    print ('Non-existent input file specified')
    exit()
with open('/home/tide/bin/tidegauge/ku', 'r') as file:
    key = file.read()
enkey = Fernet(key)
#
# Read clear variables from json file
#
with open(infile,'r') as file:
    dictjson = file.read()
constants_dict = json.loads(dictjson)
#
# Save encrypted attributes in dictionary 'constants_dict'
#
for ent in constants_dict:
    value = enkey.encrypt(constants_dict[ent].encode())
    constants_dict[ent] = value.decode()
with open('tide_constants.tmp','w') as outfile:
    json.dump(constants_dict, outfile, indent=4)
