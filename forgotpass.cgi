#!/home/tide/.tidenv/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import secrets
import json
import os
from dotenv import load_dotenv, find_dotenv
import tidecrypto
#
# Read non-secret configuration (paths, URL) -- no keys or encrypted
# constants are read here anymore.
#
envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    SQL_PATH = os.getenv('SQL_PATH')
    CGI_URL = os.getenv('CGI_URL')
    HTML_DIRECTORY = os.getenv('HTML_DIRECTORY')
MAILSPOOL_DIR = f'{HTML_DIRECTORY}mailspool/'
#
# Write an outbound email request to the mail spool directory for tide.py
# to send. This CGI no longer holds email credentials or sends mail
# directly -- see process_mailspool() in tidehelper.py. Written to a temp
# name first, then atomically renamed into place, so tide.py's spool scan
# never observes a half-written file.
#
def queue_email(recipient, headers, body):
   filename = f'{datetime.now().strftime("%Y%m%d%H%M%S")}-{secrets.token_hex(8)}.json'
   filepath = os.path.join(MAILSPOOL_DIR, filename)
   tmp_path = filepath + '.tmp'
   request = {'recipient': recipient, 'headers': headers, 'body': body}
   with open(tmp_path, 'w') as f:
      json.dump(request, f)
   os.rename(tmp_path, filepath)

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
print ('.navbar {')
print ('max-width: 560px;')
print ('margin: 0 auto 14px auto;')
print ('text-align: center;')
print ('}')
print ('.navbar button {')
print ('font-family: "Arial", "Helvetica", sans-serif;')
print ('font-size: 1em;')
print ('font-weight: bold;')
print ('color: #FFFFFF;')
print ('background-color: #1B3A5C;')
print ('border: 2px solid #000000;')
print ('border-radius: 6px;')
print ('padding: 8px 18px;')
print ('margin: 0 8px;')
print ('cursor: pointer;')
print ('}')
print ('</style>')
print ('<title>Tide Alert Login Request</title>')

try: 
   sqlcon = sqlite3.connect(f'{SQL_PATH}')
   sqlcur = sqlcon.cursor()
   f1 = tidecrypto.EMAIL_KEY
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
      if emailAddress.lower() == databaseEmailAddress.lower():
         found = True
         break
   if not found:
      print ('</head>')
      print('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<div class="navbar">')
      print ('<a href="/index.html"><button type="button">Home</button></a>')
      print ('<a href="/alertlogin.html"><button type="button">Return to Login</button></a>')
      print ('</div>')
      print ('<span style="border:8px double #1B3A5C; box-sizing: border-box; width: 560px; padding: 25px; background-color: #E3F1F0;">')
      print ('<img src="/webimage.png" style="width: 480px; height: 300px; object-fit: contain; background-color: #FFFFFF;"/>')
      print ('<h1 style="width: 480px; margin: 0 auto; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Reset</h1>')
      print ('<p style="width: 480px; margin: 0 auto; box-sizing: border-box; text-align: center; font-size: 25px; padding: 8px; background-color: #FFFFFF; border: 2px solid #B5502E; border-radius: 8px;">')
      print (f'No such user: {emailAddress}')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</font></body>')
      print ('</html>')
   else:
      sqlcur.execute(f'UPDATE userpass set dtime = "{curtime}", valkey = "{valkey}" where dtime = "{databaseTime}"')
      sqlcon.commit()
      headers = ["Subject: Tide Alert Request", "To: "+emailAddress,"MIME-Versiion:1.0","Content-Type:text/html"]
      headers = "\r\n".join(headers)
      email_message = 'Please select the link to enter a new password for your alert request<br>'+ \
                     f'{CGI_URL}reset-pw.cgi?valkey={valkey}'
      queue_email(emailAddress, headers, email_message)
      print ('</head>')
      print('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<div class="navbar">')
      print ('<a href="/index.html"><button type="button">Home</button></a>')
      print ('<a href="/alertlogin.html"><button type="button">Return to Login</button></a>')
      print ('</div>')
      print ('<span style="border:8px double #1B3A5C; box-sizing: border-box; width: 560px; padding: 25px; background-color: #E3F1F0;">')
      print ('<img src="/webimage.png" style="width: 480px; height: 300px; object-fit: contain; background-color: #FFFFFF;"/>')
      print ('<h1 style="width: 480px; margin: 0 auto; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Reset</h1>')
      print ('<p style="width: 480px; margin: 0 auto; box-sizing: border-box; text-align: center; font-size: 25px; padding: 8px; background-color: #FFFFFF; border: 2px solid #1B3A5C; border-radius: 8px;">')
      print (f'Please check {emailAddress} email for password reset instructions')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</font></body>')
      print ('</html>')
except Exception as errmsg:
   print (f'<p>Error: {errmsg}</p>')
   print ('</div>')
   print ('</body>')
   print ('</html>')
