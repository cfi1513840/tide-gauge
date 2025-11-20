#!/home/tide/.tidenv/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
import secrets
from cryptography.fernet import Fernet

form = cgi.FieldStorage()
valkey = form["valkey"].value
timeformat = "%Y-%m-%d %H:%M:%S"
curtime = datetime.now()
dbtime = str(curtime)[:-7]
def change_password(valkey):
   print ("Content-type:text/html\r\n\r\n")
   print ('<html>')
   print('<style type="text/css">')
   print('.center-screen {')
   print('      display: flex;')
   print('      flex-direction: column;')
   print('      justify-content: center;')
   print('      align-items: center;')
   print('      text-align: center;')
   print('}')
   print('.dirtab {')
   print('   text-indent: 33%;')
   print('}')
   print('</style>')
   print('<head>')
   print('   <title>Tide Alerts</title>')
   print('<script language = "Javascript">')
   print('   function validit(form) {')
   print('      var confirmit = true;')
   print('      var passwd1 = document.getElementsByName("passwd1")[0].value;')
   print('      var passwd2 = document.getElementsByName("passwd2")[0].value;')
   print('      if (passwd1 != passwd2) {')
   print('         alert("passwords do not match: "+passwd1+" "+passwd2);')
   print('         confirmit = false;')
   print('      }')
   print('      return confirmit;')
   print('   }')
   print('</script>')
   print('</head>')
   print('   <body id="uform"><font size = "5">')
   print('   <div class="center-screen">')
   print('    <span style="border:2px black solid; width: 450px;">')
   print('    <img src="/CoastalMaine.png"')
   print('         width="400" height="300"/>')
   print('      <h1 style="width: 400px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Change Password</h1>')
   print('      <p>')
   print('      <form  action="/cgi-bin/reset-pw-1.cgi" method="post" onsubmit="return validit(this);">')
   print(f'     <input type="hidden" name="valkey" id="valkey" value="{valkey}"><br><br>')
   print('      <label for="passwd1">Enter new password:</label>')
   print('      <input type="password" name="passwd1" id="passwd1" minlength="8" pattern="[A-Za-z0-9]{8-16}" required><br><br>')
   print('      <label for="passwd2">Confirm new password:</label>')
   print('      <input type="password" name="passwd2" id="passwd2" minlength="8" pattern="[A-Za-z0-9]{8-16}" required><br><br>')
   print('      <input type="submit" value="Submit">')
   print('      </form>')
   print('      </p>')
   print('    </span>')
   print('   </div>')
   print('   </body>')
   print('</html>')
change_password(valkey)