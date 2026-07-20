#!/home/tide/.tidenv/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
import os
from dotenv import load_dotenv, find_dotenv
import tidecrypto

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
   hashedNewPassword = tidecrypto.hash_password(newPassword)
   sqlcur.execute(f'select * from userpass where valkey == "{valkey}"')
   users = sqlcur.fetchall()
   if len(users) != 0:
      databaseEncryptedEmailAddress = users[0][1]
      databaseEncryptedEmailAddressByte = databaseEncryptedEmailAddress.encode()
      databaseEmailAddressByte = f1.decrypt(databaseEncryptedEmailAddressByte)
      databaseEmailAddress = databaseEmailAddressByte.decode()
      sqlcur.execute("update userpass set passwd = ?, valstat = 1, valkey = '' where valkey = ?",
                     (hashedNewPassword, valkey))
      sqlcon.commit()
      print ('</head>')
      print ('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<div class="navbar">')
      print ('<a href="/index.html"><button type="button">Home</button></a>')
      print ('<a href="/alertlogin.html"><button type="button">Return to Login</button></a>')
      print ('</div>')
      print ('<span style="border:8px double #1B3A5C; box-sizing: border-box; width: 560px; padding: 25px; background-color: #E3F1F0;">')
      print ('<img src="/webimage.png" style="width: 480px; height: 300px; object-fit: contain; background-color: #FFFFFF;"/>')
      print ('<h1 style="width: 480px; margin: 0 auto; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
      print ('<p style="width: 480px; margin: 0 auto; box-sizing: border-box; text-align: center; font-size: 25px; padding: 8px; background-color: #FFFFFF; border: 2px solid #1B3A5C; border-radius: 8px;">')
      print (f'Password updated for {databaseEmailAddress}')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</font></body>')
      print ('</html>')
   else:
      print ('</head>')
      print ('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<div class="navbar">')
      print ('<a href="/index.html"><button type="button">Home</button></a>')
      print ('<a href="/alertlogin.html"><button type="button">Return to Login</button></a>')
      print ('</div>')
      print ('<span style="border:8px double #1B3A5C; box-sizing: border-box; width: 560px; padding: 25px; background-color: #E3F1F0;">')
      print ('<img src="/webimage.png" style="width: 480px; height: 300px; object-fit: contain; background-color: #FFFFFF;"/>')
      print ('<h1 style="width: 480px; margin: 0 auto; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
      print ('<p style="width: 480px; margin: 0 auto; box-sizing: border-box; text-align: center; font-size: 25px; padding: 8px; background-color: #FFFFFF; border: 2px solid #B5502E; border-radius: 8px;">')
      print (f'The password update request has expired')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</font></body>')
      print ('</html>')
except Exception as errmsg:
   with open('/var/www/html/reset-pw-1.log', 'a') as logfile:
      logfile.write(dbtime+' '+str(errmsg))       
   #print (f'<p>Error: {errmsg}</p>')
   print ('</div>')
   print ('</body>')
   print ('</html>')
