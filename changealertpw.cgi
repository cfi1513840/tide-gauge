#!/home/tide/.tidenv/bin/python3
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
import tidecrypto

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
      storedPassword = user[2]
      if emailAddress == databaseEmailAddress:
         found = True
         if user[3] == 1:
            valid = True
         if not tidecrypto.verify_password(oldPassword, storedPassword):
            badpass = True
         break
   #print (f' {cuser} {cpass}')
   if found and not badpass and valid:
      hashedNewPassword = tidecrypto.hash_password(newPassword)
      sqlcur.execute("update userpass set passwd = ? where emailaddr = ?",
                     (hashedNewPassword, databaseEncryptedEmailAddress))
      sqlcon.commit()
      print ('</head>')
      print ('<body bgcolor="black"><font size = "4">')
      print ('<div class="center-screen">')
      print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
      print ('<img src="/webimage.png" width="450" height="300"/>')
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
      print ('<img src="/webimage.png" width="450" height="300"/>')
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





