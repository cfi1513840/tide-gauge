import json
from cryptography.fernet import Fernet

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
    print (ent, secure_dict[ent])
