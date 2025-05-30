#!/usr/bin/python3
import os
import cgi, cgitb
from datetime import datetime
import sqlite3
import smtplib
import secrets
from cryptography.fernet import Fernet
import json
from dotenv import load_dotenv, find_dotenv

global  SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD
  
#
# Function to send confirmation email message
#
def send_email(recipient, subject, message):
    global SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD
    headers = [f"From: {EMAIL_USERNAME}",
      f"Subject: {subject}",
      f"To: {recipient}",
      "MIME-Versiion:1.0","Content-Type:text/html"]
    headers = "\r\n".join(headers)
    session = smtplib.SMTP(SMTP_SERVER,SMTP_PORT)
    session.ehlo()
    session.starttls()
    session.ehlo()
    session.login(EMAIL_USERNAME,EMAIL_PASSWORD)
    session.sendmail(
      EMAIL_USERNAME,recipient,headers+"\r\n\r\n"+message)
    session.quit()
#
# Read and decrypt secure variable names & values
#
constants_dict = {}
admin_email = []
with open('/var/www/html/ku', 'r') as file:
    key = file.read()
enkey = Fernet(key)
with open('/var/www/html/tide_constants.json','r') as file:
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
envfile = find_dotenv('/var/www/html/tide.env')
if load_dotenv(envfile):
    SQL_PATH = os.getenv('SQL_PATH')
    CGI_URL = os.getenv('CGI_URL')
    HTML_DIRECTORY = os.getenv('HTML_DIRECTORY') 
form = cgi.FieldStorage()
email_address = form["eaddr"].value
password = form["passwd"].value
actype = form["actype"].value
actype = str(actype)
timeformat = "%Y-%m-%d %H:%M:%S"
curtime = datetime.now()
dbtime = str(curtime)[:-7]
found = False
valid = False
badpass = False
valkey = secrets.token_urlsafe(16)

def display_userform(email_address,password):
    print ("Content-type:text/html\r\n\r\n")
    print ('<html>')
    print('<style type="text/css">')
    print('.center-screen {')
    print('  display: flex;')
    print('  flex-direction: column;')
    print('  justify-content: center;')
    print('  align-items: center;')
    print('  text-align: center;')
    print('}')
    print('.dirtab {')
    print('  text-indent: 33%;')
    print('}')
    print('</style>')
    print('<head>')
    print('  <title>Tide Alerts</title>')
    print('<script language = "Javascript">')
    print('  document.getElementById("user-form").reset();')
    print('</script>')
    print('<script language = "Javascript">')
    print('  function validit(form) {')
    print('    var confirmit = true;')
    print('    var conmessage = "";')
    print('    var dellev = "9";')
    print('    var delair = "9";')
    print('    var delwind = "9";')
    print('    var delvari = "9"')
    print('    var delwater = "9"')
    print('    var delevent = "9"')
    print('    var setsensor = "1"')
    print('    var enalev = document.getElementsByName("enalev");')
    print('    var tlevel = document.getElementsByName("tlevel")[0].value;')
    print('    var enaair = document.getElementsByName("enaair");')
    print('    var atemp = document.getElementsByName("atemp")[0].value;')
    print('    var enawat = document.getElementsByName("enawat");')
    print('    var wtemp = document.getElementsByName("wtemp")[0].value;')
    print('    var wind = document.getElementsByName("wind")[0].value;')
    print('    var enawind = document.getElementsByName("enawind");')
    print('    var vari = document.getElementsByName("vari")[0].value;')
    print('    var enavari = document.getElementsByName("enavari");')
    print('    var evnotice = document.getElementsByName("evnotice")[0].value;')
    print('    var enaevent = document.getElementsByName("enaevent");')
    print('    for (i=0; i < enalev.length; i++) {')
    print('      if (enalev[i].checked) {')
    print('        dellev = enalev[i].value;')
    print('        break;')
    print('      }')
    print('    }')
    print('    for (i=0; i < enaair.length; i++) {')
    print('      if (enaair[i].checked) {')
    print('        delair = enaair[i].value;')
    print('        break;')
    print('      }')
    print('    }')
    print('    for (i=0; i < enawat.length; i++) {')
    print('      if (enawat[i].checked) {')
    print('        delwat = enawat[i].value;')
    print('        break;')
    print('      }')
    print('    }')
    print('    for (i=0; i < enawind.length; i++) {')
    print('      if (enawind[i].checked) {')
    print('        delwind = enawind[i].value;')
    print('        break;')
    print('      }')
    print('    }')
    print('    for (i=0; i < enavari.length; i++) {')
    print('      if (enavari[i].checked) {')
    print('        delvari = enavari[i].value;')
    print('        break;')
    print('      }')
    print('    }')
    print('    for (i=0; i < enaevent.length; i++) {')
    print('      if (enaevent[i].checked) {')
    print('        delevent = enaevent[i].value;')
    print('        break;')
    print('      }')
    print('    }')
    print('    if (dellev == "2" || dellev == "0") {')
    print('      if (tlevel.length != 0) {')
    print('        if (confirm("Disable or Delete Entry for Tide Level "+tlevel) == false)')
    print('          confirmit = false;')
    print('      }')
    print('    }')
    print('    if ((delair == "2" || delair == "0") && confirmit) {')
    print('      if (atemp.length != 0) {')
    print('        if (confirm("Disable or Delete Entry for Air Temperature "+atemp) == false)')
    print('          confirmit = false;')
    print('      }')
    print('    }')
    print('    if ((delwat == "2" || delwat == "0") && confirmit) {')
    print('      if (wtemp.length != 0) {')
    print('        if (confirm("Disable or Delete Entry for Water Temperature "+wtemp) == false)')
    print('          confirmit = false;')
    print('      }')
    print('    }')
    print('    if ((delwind == "2" || delwind == "0") && confirmit) {')
    print('      if (wind.length != 0) {')
    print('        if (confirm("Disable or Delete Entry for Wind "+wind) == false)')
    print('          confirmit = false;')
    print('      }')
    print('    }')
    print('    if ((delvari == "2" || delvari == "0") && confirmit) {')
    print('      if (vari.length != 0) {')
    print('        if (confirm("Disable or Delete Entry for Variance "+vari) == false)')
    print('          confirmit = false;')
    print('      }')
    print('    }')
    print('    if ((delevent == "2" || delevent == "0") && confirmit) {')
    print('      if (evnotice.length != 0) {')
    print('        if (confirm("Disable or Delete Entry for "+evnotice+" minute tide notification") == false)')
    print('          confirmit = false;')
    print('      }')
    print('    }')
    print('    return confirmit;')
    print('    }')
    print('</script>')
    print('</head>')
    print('  <body bgcolor="black"><font size = "4">')
    print('  <div class="center-screen">')
    print('  <div style="width: 1000px; background-color: #FFE4C4; text-align: center; font-size: 25px; font-color: black; padding: 4px; border: 2px solid blue;">')
    print('    Enter details to request, enable or disable Tide Station Alerts,<br>')
    print('    or hit Submit with empty fields to view current alerts.<br><hr>')
    print('  <form id="user-form" autocomplete="off" action="/cgi-bin/processalerts.cgi" method="post" onsubmit="return validit(this);">')
    print('    <label for="eaddr">Email address:</label>')
    print(f'   <input type="email" name="eaddr" id="eaddr" required value="{email_address}">')
    print(f'   <input type="hidden" name="passwd" id="passwd" value="{password}">')
    print('    <label for="taddr">Phone number:</label>')
    print('    <input type="tel" name="taddr" id="taddr" pattern="[0-9]{10}">')
    print('    <small class="tab">(Numbers Only: 8435555555)</small><br><hr>')
    print('    <label for="tlevel">Tide level in Feet:</label>')
    print('    <input type="number" name="tlevel" id="tlevel" step=0.1 min="-2.0" max="16.0">')
    print('    <label for="daylight"> Daylight Only</label>')
    print('    <input type="checkbox" id="daylight" name="daylight" value="1">')
    print('    <input type="radio" name="enalev" id="enablelev" value=1 checked>')
    print('    <label for="enablelev">Enable</label>')
    print('    <input type="radio" name="enalev" id="dislev" value="0">')
    print('    <label for="dislev">Disable</label>')
    print('    <input type="radio" name="enalev" id="dellev" value="2">')
    print('    <label for="dellev">Delete</label><br><hr>')
    print('    <label for="varihilo">Tide</label>')
    print('    <select name="varihilo" id="varihilo">')
    print('      <option value="1">Greater Than</option>')
    print('      <option value="-1">Less Than</option>')
    print('    </select>')
    print('    <label for="vari">predicted by more than:</label>')
    print('    <input type="number" name="vari", id="vari" step=0.1 min="0.1" max="5.0">')
    print('    <label for="dayvari"> Daylight Only</label>')
    print('    <input type="checkbox" id="dayvari" name="dayvari" value="1">')
    print('    <input type="radio" name="enavari" id="enablevari" value="1" checked>')
    print('    <label for="enablevari">Enable</label>')
    print('    <input type="radio" name="enavari" id="disvari" value="0">')
    print('    <label for="disvari">Disable</label>')
    print('    <input type="radio" name="enavari" id="delvari" value="2">')
    print('    <label for="delvari">Delete</label><br><hr>')
    print('    <label for="evnotice">Notify me:</label>')
    print('    <input type="number" name="evnotice", id="evnotice" step=1 min="1" max="180">')
    print('    <label for="evhigh"> minutes prior to the next</label>')
    print('    <input type="radio" name="evtype" id="evhigh" value="2" checked>')
    print('    <label for="evhigh">High</label>')
    print('    <input type="radio" name="evtype" id="evlow" value="1">')
    print('    <label for="evlow">Low</label>')
    print('    <label for="evthresh">tide in excess of:</label>')
    print('    <input type="number" name="evthresh", id="evthresh" value = "" step=.1 min="-3" max="18">')
    print('    <label for="evrepeat">Feet<br>Repeat:</label>')
    print('    <input type="number" name="evrepeat", id="evrepeat" value="-1" step=1 min="-1" max="1000">')
    print('    <label for="evday">Times in Daylight Only</label>')
    print('    <input type="checkbox" id="evday" name="evday" value="1">')
    print('    <input type="radio" name="enaevent" id="enablevent" value="1" checked>')
    print('    <label for="enablevent">Enable</label>')
    print('    <input type="radio" name="enaevent" id="disevent" value="0">')
    print('    <label for="disevent">Disable</label>')
    print('    <input type="radio" name="enaevent" id="delevent" value="2">')
    print('    <label for="delevent">Delete</label><br><hr>')
    print('    <label for="atemp">Air temperature in Deg F:</label>')
    print('    <input type="number" name="atemp", id="atemp" step=0.1 min="0" max="99">')
    print('    <label for="dayair"> Daylight Only</label>')
    print('    <input type="checkbox" id="dayair" name="dayair" value="1">')
    print('    <input type="radio" name="enaair" id="enableair" value="1" checked>')
    print('    <label for="enableair">Enable</label>')
    print('    <input type="radio" name="enaair" id="disair" value="0">')
    print('    <label for="disair">Disable</label>')
    print('    <input type="radio" name="enaair" id="delair" value="2">')
    print('    <label for="delair">Delete</label><br><hr>')
    print('    <label for="wtemp">Coastal water temperature in Deg F:</label>')
    print('    <input type="number" name="wtemp", id="wtemp" step=0.1 min="0" max="99">')
    print('    <label for="daywat"> Daylight Only</label>')
    print('    <input type="checkbox" id="daywat" name="daywat" value="1">')
    print('    <input type="radio" name="enawat" id="enablewat" value="1" checked>')
    print('    <label for="enablewat">Enable</label>')
    print('    <input type="radio" name="enawat" id="diswat" value="0">')
    print('    <label for="diswat">Disable</label>')
    print('    <input type="radio" name="enawat" id="delwat" value="2">')
    print('    <label for="delwat">Delete</label><br><hr>')
    print('    <label for="wind">Wind speed:</label>')
    print('    <input type="number" name="wind", id="wind" step=1 min="0" max="99">')
    print('    <label for="windir">Wind Direction:</label>')
    print('    <select name="windir" id="windir">')
    print('      <option value="any">Any</option>')
    print('      <option value="N">North</option>')
    print('      <option value="NE">Northeast</option>')
    print('      <option value="E">East</option>')
    print('      <option value="SE">Southeast</option>')
    print('      <option value="S">South</option>')
    print('      <option value="SW">Southwest</option>')
    print('      <option value="W">West</option>')
    print('      <option value="NW">Northwest</option>')
    print('    </select>')
    print('    <label for="daywind"> Daylight Only</label>')
    print('    <input type="checkbox" id="daywind" name="daywind" value="1">')
    print('    <input type="radio" name="enawind" id="enablewind" value="1" checked>')
    print('    <label for="enablewind">Enable</label>')
    print('    <input type="radio" name="enawind" id="diswind" value="0">')
    print('    <label for="diswind">Disable</label>')
    print('    <input type="radio" name="enawind" id="delwind" value="2">')
    print('    <label for="delwind">Delete</label><br><hr>')
    print('    <input type="radio" name="activate" id="suspend" value=2>')
    print('    <label for="suspend">Suspend All Alerts</label>')
    print('    <input type="radio" name="activate" id="resume" value=1>')
    print('    <label for="resume">Resume All Alerts</label>')
    print('    <input type="radio" name="activate" id="reset" value=0>')
    print('    <label for="reset">Clear Resume/Suspend</label><br><hr>')
    print('    <input type="submit" value="Submit">&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp&nbsp')
    print('    <input type="button" id="refresh" onclick="location.reload()" value = "Refresh Form"><br><br>')
    print('    <label for="admin">Admin use only:</label>')
    print('    <input type="number" name="admin" id="admin" step=1 min="0000" max="9999"><br><br>')
    print('  </form></div>')
    print('    </div>')
    print('    </body>')
    print('</html>')
   
def change_password(email_address,password):
    print ("Content-type:text/html\r\n\r\n")
    print ('<html>')
    print('<style type="text/css">')
    print('.center-screen {')
    print('        display: flex;')
    print('        flex-direction: column;')
    print('        justify-content: center;')
    print('        align-items: center;')
    print('        text-align: center;')
    print('}')
    print('.dirtab {')
    print('    text-indent: 33%;')
    print('}')
    print('</style>')
    print('<head>')
    print('    <title>Tide Alerts</title>')
    print('<script language = "Javascript">')
    print('  function validit(form) {')
    print('    var confirmit = true;')
    print('    var oldpwd = document.getElementsByName("oldpwd")[0].value;')
    print('    var passwd1 = document.getElementsByName("passwd1")[0].value;')
    print('    var passwd2 = document.getElementsByName("passwd2")[0].value;')
    print('    if (passwd1 != passwd2) {')
    print('      alert("passwords do not match: "+passwd1+" "+passwd2);')
    print('      confirmit = false;')
    print('    }')
    print('    return confirmit;')
    print('  }')
    print('</script>')
    print('</head>')
    print('  <body bgcolor="black"><font size = "4">')
    print('  <div class="center-screen">')
    print('  <span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
    print('    <img src="/CoastalMaine.png"')
    print('       width="400" height="300"/>')
    print('    <h1 style="width: 400px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Change Password</h1>')
    print('    <p>')
    print('    <form  action="/cgi-bin/changealertpw.cgi" method="post" onsubmit="return validit(this);">')
    print('      <label for="eaddr">Email address:</label>')
    print(f'     <input type="email" name="eaddr" id="eaddr" required value="{email_address}"><br>')
    print(f'     <input type="hidden" name="oldpwd" id="oldpwd" minlength="8" pattern="[A-Za-z0-9]{8-16}" value="{password}"><br><br>')
    print('      <label for="passwd1">Enter new password:</label>')
    print('      <input type="password" name="passwd1" id="passwd1" minlength="8" pattern="[A-Za-z0-9]{8-16}" required><br><br>')
    print('      <label for="passwd2">Confirm new password:</label>')
    print('      <input type="password" name="passwd2" id="passwd2" minlength="8" pattern="[A-Za-z0-9]{8-16}" required><br><br>')
    print('      <input type="submit" value="Submit">')
    print('      </form>')
    print('      </p>')
    print('   </span>')
    print('   </div>')
    print('   </body>')
    print('</html>')
    
try:
#if True:
    sqlcon = sqlite3.connect(SQL_PATH)
    sqlcur = sqlcon.cursor()
    with open('/var/www/html/k1','rb') as kfile:
        key1 = kfile.read()
    with open('/var/www/html/k3','rb') as kfile:
        key3 = kfile.read()
    f1 = Fernet(key1)
    f3 = Fernet(key3)
    email_addressByte = email_address.encode()
    encryptedemail_addressByte = f1.encrypt(email_addressByte)
    encryptedemail_address = encryptedemail_addressByte.decode()
    passwordByte = password.encode()
    encryptedPasswordByte = f3.encrypt(passwordByte)
    encryptedPassword = encryptedPasswordByte.decode()
    sqlcur.execute(f"select * from userpass")
    users = sqlcur.fetchall()
    for user in users:
        databaseTime = user[0]
        databaseEncryptedemail_address = user[1]
        databaseEncryptedemail_addressByte = databaseEncryptedemail_address.encode()
        databaseemail_addressByte = f1.decrypt(databaseEncryptedemail_addressByte)
        databaseemail_address = databaseemail_addressByte.decode()
        databaseEncryptedPassword = user[2]
        databaseEncryptedPasswordByte = databaseEncryptedPassword.encode()
        databasePasswordByte = f3.decrypt(databaseEncryptedPasswordByte)
        databasePassword = databasePasswordByte.decode()
        dbvalkey = user[4]
        if email_address == databaseemail_address:
            found = True
            if user[3] == 1:
                valid = True
            if password != databasePassword:
                badpass = True
            break
    if actype != '2':
        if not found:
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
            print ('<title>Alert Login Request</title>')
            print ('</head>')
            print ('<body bgcolor="black"><font size = "4">')
            print ('<div class="center-screen">')
            print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
            print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
            print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Login Failure</h1>')
            print (f'<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px;">{email_address} is not in the database<br><br>')
            print ('<button onclick="history.back()">Back to Login Screen</button></p>')
            print ('</span>')
            print ('</div>')
            print ('</body>')
            print ('</html>')
        elif badpass:
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
            print ('<title>Alert Login Request</title>')
            print ('</head>')
            print ('<body bgcolor="black"><font size = "4">')
            print ('<div class="center-screen">')
            print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
            print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
            print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Login Failure</h1>')
            print (f'<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">Incorrect password for {email_address}<br>')
            print ('<button onclick="history.back()">Go Back</button></p>')
            print ('</span>')
            print ('</div>')
            print ('</body>')
            print ('</html>')
        elif not valid:
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
            print ('<title>Alert Login Request</title>')
            print ('</head>')
            print ('<body bgcolor="black"><font size = "4">')
            print ('<div class="center-screen">')
            print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
            print ('<img src="/Coastal_Maine.png" width="450" height="300"/>')
            print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Login Request</h1>')
            print (f'<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid black;">{email_address} requires validation.')
            print (f'An email message has been sent to {email_address}<br>')
            print (f'Please select the link contained in the message to validate your email address')
            print ('</p></span></div>')
            print ('</body>')
            print ('</html>')
            subject = 'Tide Alert Request'
            email_message = 'You have requested access to Tide Station Alerts, please select the following link to validate your email address<br>'+ \
                                f'{CGI_URL}valuser.cgi?valkey={dbvalkey}'
            send_email(email_address, subject, email_message)     
        elif actype == '0':
            display_userform(email_address,password)
        elif actype == '1':
            change_password(email_address,password)
    elif not found:
        dbvals = (curtime, encryptedemail_address, encryptedPassword, 0, valkey)
        sqlcur.execute(f"INSERT INTO userpass VALUES (?,?,?,?,?)", dbvals)
        sqlcon.commit()
        subject = 'Tide Alert Request'
        email_message = 'You have requested access to Tide Station Alerts, please select the following link to validate your email address<br>'+ \
                            f'{CGI_URL}valuser.cgi?valkey={valkey}'
        send_email(email_address, subject, email_message)     
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
        print ('<title>Alert Login Request</title>')
        print ('</head>')
        print ('<body bgcolor="black"><font size = "4">')
        print ('<div class="center-screen">')
        print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
        print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
        print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Login Request</h1>')
        print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">')
        print (f'An email message has been sent to {email_address}<br>')
        print (f'Please select the link contained in the message to validate your email address')
        print ('</p>')
        print ('</span>')
        print ('</div>')
        print ('</body>')
        print ('</html>')
    elif not valid:
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
        print ('<title>Alert Login Request</title>')
        print ('</head>')
        print ('<body bgcolor="black"><font size = "4">')
        print ('<div class="center-screen">')
        print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
        print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
        print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Login Request</h1>')
        print ('<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">')
        print (f'An email message has been sent to {email_address}<br>')
        print (f'Please select the link contained in the message to validate your email address')
        print ('</p>')
        print ('</span>')
        print ('</div>')
        print ('</body>')
        print ('</html>')
        subject = 'Tide Alert Request'
        email_message = 'You have requested access to Tide Station Alerts, please select the following link to validate your email address<br>'+ \
                            f'{CGI_URL}valuser.cgi?valkey={dbvalkey}'
        send_email(email_address, subject, email_message)     
     
    else:
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
        print ('<title>Alert Login Request</title>')
        print ('</head>')
        print ('<body bgcolor="black"><font size = "4">')
        print ('<div class="center-screen">')
        print ('<span style="border:2px black solid; width: 450px; background-color: #FFE4C4;">')
        print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
        print ('<h1 style="width: 430px; text-align: center; font-size: 25px; font-color: black; padding: 4px;">Alert Login Request</h1>')
        print (f'<p style="width: 438px; text-align: center; font-size: 25px; padding: 4px; border: 2px solid red;">{email_address} is already registered')
        print ('</p>')
        print ('</span>')
        print ('</div>')
        print ('</body>')
        print ('</html>')
#else:
except Exception as errmsg:
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
    print ('<title>Alert Login Request</title>')
    print (f'<p>Error: {errmsg}</p>')
    print ('</div>')
    print ('</body>')
    print ('</html>')





