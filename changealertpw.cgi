#!/usr/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
from cryptography.fernet import Fernet

form = cgi.FieldStorage()
emailAddress = form.getvalue("eaddr")
oldPassword = form.getvalue("oldpwd")
newPassword = form.getvalue("passwd1")
timeformat = "%Y-%m-%d %H:%M:%S"
curtime = datetime.now()
dbtime = str(curtime)[:-7]
found = False
valid = False
badpass = False
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
   sqlcon = sqlite3.connect('/var/www/html/tides.db')
   sqlcur = sqlcon.cursor()
   with open('/var/www/html/k1','rb') as kfile:
      key1 = kfile.read()
   with open('/var/www/html/k3','rb') as kfile:
      key3 = kfile.read()
   f1 = Fernet(key1)
   f3 = Fernet(key3)
   emailAddressByte = emailAddress.encode()
   encryptedEmailAddressByte = f1.encrypt(emailAddressByte)
   encryptedEmailAddress = encryptedEmailAddressByte.decode()
   oldPasswordByte = oldPassword.encode()
   encryptedOldPasswordByte = f3.encrypt(oldPasswordByte)
   encryptedOldPassword = encryptedOldPasswordByte.decode()
   newPasswordByte = newPassword.encode()
   encryptedNewPasswordByte = f3.encrypt(newPasswordByte)
   encryptedNewPassword = encryptedNewPasswordByte.decode()
   sqlcur.execute(f"select * from userpass")
   users = sqlcur.fetchall()
   for user in users:
      databaseTime = user[0]
      databaseEncryptedEmailAddress = user[1]
      databaseEncryptedEmailAddressByte = databaseEncryptedEmailAddress.encode()
      databaseEmailAddressByte = f1.decrypt(databaseEncryptedEmailAddressByte)
      databaseEmailAddress = databaseEmailAddressByte.decode()
      databaseEncryptedPassword = user[2]
      databaseEncryptedPasswordByte = databaseEncryptedPassword.encode()
      databasePasswordByte = f3.decrypt(databaseEncryptedPasswordByte)
      databasePassword = databasePasswordByte.decode()
      if emailAddress == databaseEmailAddress:
         found = True
         if user[3] == 1:
            valid = True
         if oldPassword != databasePassword:
            badpass = True
         break
   #print (f' {cuser} {cpass}')
   if found and not badpass and valid:
      sqlcur.execute(f"update userpass set passwd = '{encryptedNewPassword}' where emailaddr = '{databaseEncryptedEmailAddress}'")
      sqlcon.commit()
      print ('</head>')
      print ('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
      print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
      print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
      print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid black;">')
      print (f'Password updated for {emailAddress}')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</body>')
      print ('</html>')
   else:
      print ('</head>')
      print ('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
      print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
      print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Tide Alert Password Change</h1>')
      print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">')
      print (f'Error updating password for {emailAddress} {oldPassword} {newPassword}</p>')
      print ('</p>')
      print ('</span>')
      print ('</div>')
      print ('</body>')
      print ('</html>')
except Exception as errmsg:
   print (f'<p>Error: {errmsg}</p>')
   print ('</div>')
   print ('</body>')
   print ('</html>')





