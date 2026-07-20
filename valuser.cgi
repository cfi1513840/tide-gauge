#!/home/tide/.tidenv/bin/python3
import cgi, cgitb
import os
from datetime import datetime
import sqlite3
import smtplib
from dotenv import load_dotenv, find_dotenv
import tidecrypto

envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    SQL_PATH = os.getenv('SQL_PATH')
    HTML_URL = os.getenv('HTML_URL')
form = cgi.FieldStorage()
valkeyform = form.getvalue("valkey")
sqlcon = sqlite3.connect(f'{SQL_PATH}')
sqlcur = sqlcon.cursor()
f1 = tidecrypto.EMAIL_KEY
sqlcur.execute(f"select * from userpass")
users = sqlcur.fetchall()
found = False
for user in users:
   dbtime = user[0]
   dbuser = user[1]
   valkey = user[4]
   dbuser = dbuser.encode()
   deuser = f1.decrypt(dbuser).decode()
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
   print ('<body bgcolor="black"><font size = "4">')
   print ('<div class="center-screen">')
   print ('<span style="border:8px double #1B3A5C; box-sizing: border-box; width: 560px; padding: 25px; background-color: #E3F1F0;">')
   print ('<img src="/webimage.png" style="width: 480px; height: 300px; object-fit: contain; background-color: #FFFFFF;"/>')
   print ('<h1 style="width: 480px; margin: 0 auto; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
   print ('<p style="width: 480px; margin: 0 auto; box-sizing: border-box; text-align: center; font-size: 25px; padding: 8px; background-color: #FFFFFF; border: 2px solid #1B3A5C; border-radius: 8px;">')
   print (f'Success - your email address has been validated, close this tab and return to the login screen')
   print ('</p>')
   print ('</span>')
   print ('</div>')
   print ('</font></body>')
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
   print ('<body bgcolor="black"><font size = "4">')
   print ('<div class="center-screen">')
   print ('<span style="border:8px double #1B3A5C; box-sizing: border-box; width: 560px; padding: 25px; background-color: #E3F1F0;">')
   print ('<img src="/webimage.png" style="width: 480px; height: 300px; object-fit: contain; background-color: #FFFFFF;"/>')
   print ('<h1 style="width: 480px; margin: 0 auto; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
   print ('<p style="width: 480px; margin: 0 auto; box-sizing: border-box; text-align: center; font-size: 25px; padding: 8px; background-color: #FFFFFF; border: 2px solid #B5502E; border-radius: 8px;">')
   print (f'Error - registration link expired. Please close this tab and return to the login screen to register again')
   print ('</p>')
   print ('</span>')
   print ('</div>')
   print ('</font></body>')
   print ('</html>')
