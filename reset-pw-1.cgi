#!/usr/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv, find_dotenv

form = cgi.FieldStorage()
valkey = form.getvalue("valkey")
newPassword = form.getvalue("passwd1")
timeformat = "%Y-%m-%d %H:%M:%S"
curtime = datetime.now()
dbtime = str(curtime)[:-7]
found = False
valid = False
badpass = False
envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    SQL_PATH = os.getenv('SQL_PATH')
    HTML_URL = os.getenv('HTML_URL')
    HTML_DIRECTORY = os.getenv('HTML_DIRECTORY') 
print ("Content-type:text/html\r\n\r\n")
print ('<html>')
print ('<head>')
print ('<style type="text/css">')
print ('.center-screen {')
print ('display: flex;')
print ('flex-direction: column;')
print ('justify-content: center;')
print ('align-items: center;')
print ('text-align: center;')
print ('</style>')
print ('<title>Tide Alert Login Request</title>')
try: 
   sqlcon = sqlite3.connect(f'{SQL_PATH')
   sqlcur = sqlcon.cursor()
   with open(f'{HTML_DIRECTORY}k1','rb') as kfile:
      key1 = kfile.read()
   with open(f'{HTML_DIRECTORY}k3','rb') as kfile:
      key3 = kfile.read()
   f1 = Fernet(key1)
   f3 = Fernet(key3)
   newPasswordByte = newPassword.encode()
   encryptedNewPasswordByte = f3.encrypt(newPasswordByte)
   encryptedNewPassword = encryptedNewPasswordByte.decode()
   sqlcur.execute(f'select * from userpass where valkey == "{valkey}"')
   users = sqlcur.fetchall()
   if len(users) != 0:
      databaseEncryptedEmailAddress = users[0][1]
      databaseEncryptedEmailAddressByte = databaseEncryptedEmailAddress.encode()
      databaseEmailAddressByte = f1.decrypt(databaseEncryptedEmailAddressByte)
      databaseEmailAddress = databaseEmailAddressByte.decode()
      sqlcur.execute(f"update userpass set passwd = '{encryptedNewPassword}', valstat = 1, valkey = '' where valkey = '{valkey}'")
      sqlcon.commit()
      print ('</head>')
      print ('<body><font size = "4">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px;">')
      print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
      print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
      print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid black;">')
      print (f'Password updated for {databaseEmailAddress}<br><br>')
      print (f'<a href="/alertlogin.html">Go to Login Screen</a></p>')     
      print ('</span>')
      print ('</div>')
      print ('</body>')
      print ('</html>')
   else:
      print ('</head>')
      print ('<body><font size = "4">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px;">')
      print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
      print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
      print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">')
      print (f'The password update request has expired<br><br>')
      print (f'<a href="/alertlogin.html">Go to Login Screen</a></p>')     
      print ('</span>')
      print ('</div>')
      print ('</body>')
      print ('</html>')
except Exception as errmsg:
   print (f'<p>Error: {errmsg}</p>')
   print ('</div>')
   print ('</body>')
   print ('</html>')





