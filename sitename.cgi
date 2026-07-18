#!/home/tide/.tidenv/bin/python3
import os
from dotenv import load_dotenv, find_dotenv

envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    STATION_LOCATION = os.getenv('STATION_LOCATION')
else:
    STATION_LOCATION = ''

print("Content-type:text/plain\r\n\r\n")
if STATION_LOCATION:
    print(STATION_LOCATION.strip())
