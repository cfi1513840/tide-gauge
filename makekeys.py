#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from cryptography.fernet import Fernet

if os.path.exists('/var/www/html/kux'):
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