import json
from cryptography.fernet import Fernet

with open('ku', 'r') as file:
    key = file.read()
enkey = Fernet(key)
#
# Read clear variables from json file
#
with open('tide_constants_clear.json','r') as file:
    dictjson = file.read()
constants_dict = json.loads(dictjson)
#
# Save encrypted attributes in dictionary 'constants_dict'
#
for ent in constants_dict:
    value = enkey.encrypt(constants_dict[ent].encode())
    constants_dict[ent] = value.decode()
with open('tide_constants.json','w') as outfile:
    json.dump(constants_dict, outfile, indent=4)
print ('Encrypted constants file written to tide_constants.json')