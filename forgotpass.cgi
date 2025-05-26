#!/usr/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
import secrets
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv
import os
import json
global  SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, email_message, \
       EMAIL_RECIP, headers
#
# Function to send confirmation email message
#
def send_email():
   global SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, email_message, headers, EMAIL_RECIP
   session = smtplib.SMTP(SMTP_SERVER,SMTP_PORT)
   session.ehlo()
   session.starttls()
   session.ehlo()
   session.login(EMAIL_USERNAME,EMAIL_PASSWORD)
   session.sendmail(EMAIL_USERNAME,EMAIL_RECIP,headers+"\r\n\r\n"+email_message)
   session.quit()
#
# Read and decrypt secure variable names & values
#
envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    SQL_PATH = os.getenv('SQL_PATH')
    CGI_URL = os.getenv('CGI_URL')
    HTML_DIRECTORY = os.getenv('HTML_DIRECTORY') 
constants_dict = {}
admin_email = []
with open(f'{HTML_DIRECTORY}ku', 'r') as file:
   key = file.read()
enkey = Fernet(key)
with open(f'{HTML_DIRECTORY}tide_constants.json','r') as file:
   dictjson = file.read()
constants_dict = json.loads(dictjson)
for ent in constants_dict:
   clearval = enkey.decrypt(constants_dict[ent].encode())
   constants_dict[ent] = clearval.decode()
if constants_dict['ADMIN1'] != 'None':
   admin_email.append(constants_dict['ADMIN1'])
if constants_dict['ADMIN2'] != 'None':
   admin_email.append(constants_dict['ADMIN2'])
SMTP_SERVER = constants_dict['SMTP_SERVER']
SMTP_PORT = constants_dict['SMTP_PORT']
EMAIL_USERNAME = constants_dict['EMAIL_USERNAME']
EMAIL_PASSWORD = constants_dict['EMAIL_PASSWORD']
form = cgi.FieldStorage()
emailAddress = form.getvalue("eaddr")
timeformat = "%Y-%m-%d %H:%M:%S"
curtime = datetime.now()
dbtime = str(curtime)[:-7]
found = False
valid = False
badpass = False
valkey = secrets.token_urlsafe(16)
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
print ('}')
print ('</style>')
print ('<title>Tide Alert Login Request</title>')

try: 
   sqlcon = sqlite3.connect(f'{SQL_PATH')
   sqlcur = sqlcon.cursor()
   with open(f'{HTML_DIRECTORY}k1','rb') as kfile:
      key1 = kfile.read()
   f1 = Fernet(key1)
   emailAddressByte = emailAddress.encode()
   encryptedEmailAddressByte = f1.encrypt(emailAddressByte)
   encryptedEmailAddress = encryptedEmailAddressByte.decode()
   sqlcur.execute(f"select * from userpass")
   users = sqlcur.fetchall()
   for user in users:
      databaseTime = user[0]
      databaseEncryptedEmailAddress = user[1]
      databaseEncryptedEmailAddressByte = databaseEncryptedEmailAddress.encode()
      databaseEmailAddressByte = f1.decrypt(databaseEncryptedEmailAddressByte)
      databaseEmailAddress = databaseEmailAddressByte.decode()
      if emailAddress == databaseEmailAddress:
         found = True
         break
   if not found:
      print ('</head>')
      print('<body bgcolor="black"><font size = "5">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
      print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
      print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Reset</h1>')
      print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">')
      print (f'No such user: {emailAddress}')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</body>')
      print ('</html>')
   else:
      sqlcur.execute(f'UPDATE userpass set dtime = "{curtime}", valkey = "{valkey}" where dtime = "{databaseTime}"')
      sqlcon.commit()
      EMAIL_RECIP = emailAddress
      headers = ["From: " + EMAIL_USERNAME, "Subject: Tide Alert Request", "To: "+EMAIL_RECIP,"MIME-Versiion:1.0","Content-Type:text/html"]
      headers = "\r\n".join(headers)
      email_message = 'Please select the link to enter a new password for your alert request<br>'+ \
                     f'{CGI_URL}reset-pw.cgi?valkey={valkey}'
      send_email()
      print ('</head>')
      print('<body bgcolor="black"><font size = "5">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
      print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
      print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Reset</h1>')
      print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid black;">')
      print (f'Please check {emailAddress} email for password reset instructions')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</body>')
      print ('</html>')
      print ('</html>')
except Exception as errmsg:
   print (f'<p>Error: {errmsg}</p>')
   print ('</div>')
   print ('</body>')
   print ('</html>')





