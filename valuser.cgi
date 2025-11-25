#!/home/tide/.tidenv/bin/python3
import cgi, cgitb
import os
from datetime import datetime
import sqlite3
import smtplib
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv

envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    SQL_PATH = os.getenv('SQL_PATH')
    HTML_URL = os.getenv('HTML_URL')
    HTML_DIRECTORY = os.getenv('HTML_DIRECTORY') 
form = cgi.FieldStorage()
valkeyform = form.getvalue("valkey")
sqlcon = sqlite3.connect(f'{SQL_PATH}')
sqlcur = sqlcon.cursor()
with open(f'{HTML_DIRECTORY}k1','rb') as kfile:
   key1 = kfile.read()
f1 = Fernet(key1)
with open(f'{HTML_DIRECTORY}k3','rb') as kfile:
   key3 = kfile.read()
f3 = Fernet(key3)
sqlcur.execute(f"select * from userpass")
users = sqlcur.fetchall()
found = False
for user in users:
   dbtime = user[0]
   dbuser = user[1]
   dbpass = user[2]
   valkey = user[4]
   dbuser = dbuser.encode()
   dbpass = dbpass.encode()
   deuser = f1.decrypt(dbuser).decode()
   depass = f3.decrypt(dbpass).decode()
   if valkeyform == valkey:
      found = True
      sqlcur.execute(f"update userpass set valstat = 1, valkey='' where dtime = '{dbtime}'")
      sqlcon.commit()
      break
if found:
   print ("Content-type:text/html\r\n\r\n")
   print ('<html>')
   print ('<style type="text/css">')
   print ('.center-screen {')
   print ('      display: flex;')
   print ('      flex-direction: column;')
   print ('      justify-content: center;')
   print ('      align-items: center;')
   print ('      text-align: center;')
   print ('}')
   print ('.dirtab {')
   print ('   text-indent: 33%;')
   print ('}')
   print ('</style>')
   print ('<head>')
   print ('<title>Tide Alert Login Request</title>')
   print ('</head>')
   print ('<body><font size = "4">')
   print ('<div class="center-screen">')
   print ('<span style="border:2px black solid; width: 450px;">')
   print ('<img src="/webimage.png" width="450" height="300"/>')
   print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
   print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid black;">')
   print (f'Success - your email address has been validated, you may now login<br><br>')
   print (f'<a href="/alertlogin.html">Go to Login Screen</a></p>')     
   print ('</span>')
   print ('</div>')
   print ('</body>')
   print ('</html>')
else:
   print ("Content-type:text/html\r\n\r\n")
   print ('<html>')
   print ('<style type="text/css">')
   print ('.center-screen {')
   print ('      display: flex;')
   print ('      flex-direction: column;')
   print ('      justify-content: center;')
   print ('      align-items: center;')
   print ('      text-align: center;')
   print ('}')
   print ('.dirtab {')
   print ('   text-indent: 33%;')
   print ('}')
   print ('</style>')
   print ('<head>')
   print ('<title>Tide Alert Login Request</title>')
   print ('</head>')
   print ('<body><font size = "4">')
   print ('<div class="center-screen">')
   print ('<span style="border:2px black solid; width: 450px;">')
   print ('<img src="/webimage.png" width="450" height="300"/>')
   print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
   print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid black;">')
   print (f'Error - registration link expired, please register again<br><br>')
   print (f'<a href="/alertlogin.html">Go to Login Screen</a></p>')     
   print ('</span>')
   print ('</div>')
   print ('</body>')
   print ('</html>')
   print ('</html>')
