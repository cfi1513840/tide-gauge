#!/usr/bin/python3
import os
import cgi, cgitb
import time
from datetime import datetime
from datetime import timedelta
import sqlite3
import math
import smtplib
from cryptography.fernet import Fernet
import json

global userclr, userenc, telclr, telenc, email_address,\
  tmsgaddr, tlevel, sensorloc, daylight, dayair,  enalev, atemp, enaair,\
  form, currenttime, daywat, evnotice, evtype, enaevent, evrepeat, evday, \
  SMTP_SERVER, SMTP_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, email_message,\
  evthresh, activate, entryfound, sqlcon, sqlcur,\
  adminreq, displaytable, actdeact, wind, enawind, daywind, windir
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
   
def reportit(parm1,parm2,parm3):
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
    print ('<title>Alert Login Request</title>')
    print ('</head>')
    print ('<body><font size = "4">')
    print ('<div class="center-screen">')
    print (
      f'<p style="width: 300px; text-align: center; font-size: 25px; '+
      f'font-color: red; padding: 4px; border: 2px solid red;">'+
      f'Error: {parm1} {parm2} {parm3}</p>')
    print ('</div>')
    print ('</body>')
    print ('</html>')
    exit()

def suspend_resume():
    global userclr, userenc, telclr, telenc, email_address,\
      tmsgaddr, tlevel, sensorloc, daylight, dayair, enalev, atemp, enaair,\
      wtemp, enawind, form, currenttime, daywat, SMTP_SERVER, SMTP_PORT,\
      EMAIL_USERNAME, EMAIL_PASSWORD, email_message,\
      activate, entryfound, sqlcon, sqlcur, actdeact, evnotice, evtype,\
      enaevent, evrepeat, evday, evthresh

    if activate == '2':
        actval = '0'
        email_message = ('Tide station alerts have been suspended for '+
          userclr)
    elif activate == '1':
        actval = '1'
        email_message = 'Tide station alerts have been resumed for '+userclr
    if activateuser:
        if actdeact == '0':
            sustat = 'deactivated'
        else:
            sustat = 'activated'
        actval = actdeact
        email_message = (f'Tide station alert processing has been {sustat} '+
          'for '+userclr)
        sqlcur.execute(f"UPDATE useralerts set activated = '{actval}' "+
          f"where email_address = '{userenc}'")
    else:
        sqlcur.execute(f"UPDATE useralerts set enalev = '{actval}',"+
          f"enaair = '{actval}', enawind = '{actval}' "+
          f"where email_address = '{userenc}'")
    sqlcon.commit()
    subject = "Tide Station Alert Activation",
    for recipient in admin_email:                 
        send_email(recipient, subject, email_message)

def create_table():
    global sqlcon, sqlcur, userclr, userenc, telclt, telenc, email_address,\
      adminreq, evnotice, evtype, enaevent, evrepeat, evday, evthresh
    sqlcur.execute(
      f"select * from useralerts where email_address = '{userenc}'")
    column_names = [description[0] for description in sqlcur.description]
    rows = sqlcur.fetchall()
    alert_list = []
    for row in rows:
        alert_dict= {}
        for index, column in enumerate(row):
            alert_dict[column_names[index]] = column
        alert_list.append(alert_dict)
    print ("Content-type:text/html\r\n\r\n")
    print ('<html>')
    print ('<head>')
    print ('<title>Tide Station Alerts</title>')
    print ('<style>')    
    print ('<table, th, td {')
    print ('background-color: snow;')
    print ('border-color : #000000;')
    print ('border-style: solid;')
    print ('text-align: center;')
    print ('text-indent: 0px;')
    print ('padding: 0px;')
    print ('margin: 0px;')
    print ('font-size: 12pt;')
    print ('font-family: ''Arial'', ''Helvetica'', sans-serif;')
    print ('font-style: normal;')
    print ('font-weight: bold;')
    print ('color: #000000;')
    print ('background-color: transparent;')
    print ('text-decoration: none;')
    print ('}')
    print ('td.label{')
    print ('text-align:center;')
    print ('font-weight:bold;')
    print ('font-size:1em;')
    print ('}')
    print ('td.titlebar{')
    print ('text-align:center;')
    print ('font-weight:bold;')
    print ('font-size:2em;')
    print ('}')
    print ('td.data{')
    print ('text-align:center;')
    print ('font-weight:bold;')
    print ('font-size:1em;')
    print ('}') 
    print ('div {')
    print ('max-width: 1400px;')
    print ('min-width: 800px;')
    print ('margin-left: auto;')
    print ('margin-right: auto;')
    print ('white-space: nowrap;')
    print ('}')
    print ('</style>')
    print ('</head>')
    print ('<body style="background-color:black;">')
    print ('<div>')
   #print ('<font size = "5">')
    print (
      f'<table width="1400" border="2" cellpadding="2" cellspacing="2" '+
      f'style="border-color: #000000; border-style: solid; '+
      'background-color: #ccffff;">')
    print ('<tr valign="middle">')
    print (
      '<td class="titlebar" colspan="24" style="background-color: #1A53FF; '+
      'border-color : #000000; border-style: solid;">')
    print (f'Alert Database Entries for {userclr}')
    print ('</td>')
    print ('</tr>')
    print ('<tr valign="middle">')    
    print ('<td class="label">Phone Nbr</td>')
    print ('<td class="label">Tide</td>')
   #print ('<td class="label">Sensor</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Air</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Water</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Wind</td>')
    print ('<td class="label">Dir</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Vari</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Notice</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Event</td>')
    print ('<td class="label">Thresh</td>')
    print ('<td class="label">Repeat</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Active</td>')
    print ('</tr>')
    for index, alert_dict in enumerate(alert_list):
        print ('<tr valign="middle">')
        try:
            phonenbr = alert_dict['phone_number']
            if phonenbr != None and phonenbr != '':
                telnbr = (f2.decrypt(phonenbr.encode())).decode()
            else:
                telnbr = ''
            print (f'<td class="data">{telnbr}</td>')
        except Exception as errmsg:
            print (f'<td class="data">{errmsg}</td>')
        print (f'<td class="data">{alert_dict["tide_level"]}</td>')
        if (alert_dict['tide_level_enable'] == 1 and
          alert_dict['tide_level'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tide_level'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['tide_level_day_only'] == 1 and 
          alert_dict['tide_level'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tide_level'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["air_temp"]}</td>')
        if (alert_dict['air_temp_enable'] == 1 and 
          alert_dict['air_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['air_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['air_temp_day_only'] == 1 and 
          alert_dict['air_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['air_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["water_temp"]}</td>')
        if (alert_dict['water_temp_enable'] == 1 and 
          alert_dict['water_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['water_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['water_temp_day_only'] == 1 and 
          alert_dict['water_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['water_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["wind_speed"]}</td>')
        print (f'<td class="data">{alert_dict["wind_direction"]}</td>')
        if (alert_dict['wind_speed_enable'] == 1 and 
          alert_dict['wind_speed'] != ''):
            dispfld = 'Yes'
        elif alert_dict['wind_speed'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['wind_speed_day_only'] == 1 and 
          alert_dict['wind_speed'] != ''):
            dispfld = 'Yes'
        elif alert_dict['wind_speed'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["tidal_variation"]}</td>')
        if (alert_dict['tidal_variation_enable'] == 1 and 
          alert_dict['tidal_variation'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tidal_variation'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['tidal_variation_day_only'] == 1 and 
          alert_dict['tidal_variation'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tidal_variation'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['event_notice'] != None and
          alert_dict['event_notice'] != ''):
            print (f'<td class="data">{alert_dict["event_notice"]} Mins</td>')
            if (alert_dict['event_notice_enable'] == 1 and
              alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'Yes'
            elif (alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'No'
            else:
                dispfld = ''
            print (f'<td class="data">{dispfld}</td>')
            if alert_dict['event_type'] == 1:
                dispfld = 'Low'
            elif alert_dict['event_type'] == 2:
                dispfld = 'High'
            else:
                dispfld = ''
            print (f'<td class="data">{dispfld}</td>')
            if alert_dict['event_thresh'] != None:
                print (f'<td class="data">{alert_dict["event_thresh"]}</td>')
            else:            
                print (f'<td class="data"> </td>')
            if alert_dict['event_repeat'] != None:
                print (f'<td class="data">{alert_dict["event_repeat"]}</td>')
            else:            
                print (f'<td class="data"> </td>')
            if (alert_dict['event_day_only'] == 1 and
              alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'Yes'
            elif (alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'No'
            else:
                dispfld = ''
            print (f'<td class="data">{dispfld}</td>')
        else:
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')


        print (f'<td class="data">{alert_dict["alerts_activated"]}</td>')
        print ('</tr>')
    print ('</table>')
    print ('<tr valign="middle">')
   #print ('</p>')
    print ('</div>')
    print ('</body>')
    print ('</html>')

def create_admin_table():
    global sqlcon, sqlcur, userclr, userenc, telclr, telenc, email_address,\
      evnotice, evtype, enaevent, evrepeat, evday, evthresh

    sqlcur.execute("select * from useralerts")
    column_names = [description[0] for description in sqlcur.description]
    rows = sqlcur.fetchall()
    alert_list = []
    for row in rows:
        alert_dict= {}
        for index, column in enumerate(row):
            alert_dict[column_names[index]] = column
        alert_list.append(alert_dict)
    print ("Content-type:text/html\r\n\r\n")
    print ('<html>')
    print ('<head>')
    print ('<title>Tide Station Alerts</title>')
    print ('<style>')    
    print ('<table, th, td {')
    print ('background-color: snow;')
    print ('border-color : #000000;')
    print ('border-style: solid;')
    print ('text-align: center;')
    print ('text-indent: 0px;')
    print ('padding: 0px;')
    print ('table-layout: fixed;')
    print ('margin: 0px;')
    print ('font-size: 12pt;')
    print ('font-family: ''Arial'', ''Helvetica'', sans-serif;')
    print ('font-style: normal;')
    print ('font-weight: bold;')
    print ('color: #000000;')
    print ('background-color: transparent;')
    print ('text-decoration: none;')
    print ('}')
    print ('td.label{')
    print ('word-wrap: break-word;')
    print ('text-align:center;')
    print ('font-weight:bold;')
    print ('font-size:1em;')
    print ('}')
    print ('td.titlebar{')
    print ('text-align:center;')
    print ('font-weight:bold;')
    print ('font-size:2em;')
    print ('}')
    print ('td.data{')
    print ('text-align:center;')
    print ('font-weight:bold;')
    print ('font-size:1em;')
    print ('word-wrap: break-word;')
    print ('}') 
    print ('div {')
    print ('max-width: 1800px;')
    print ('min-width: 800px;')
    print ('margin-left: auto;')
    print ('margin-right: auto;')
    print ('white-space: nowrap;')
    print ('}')
    print ('</style>')
    print ('</head>')
    print ('<body style="background-color:black;">')
    print ('<div>')
    print (
      f'<table width="1800" border="2" cellpadding="2" cellspacing="2" '+
      f'style="border-color: #000000; border-style: solid; '+
      'background-color: #ccffff;">')
    print ('<tr valign="middle">')
    print (
      '<td class="titlebar" colspan="25" style="background-color: #1A53FF; '+
      'border-color : #000000; border-style: solid;">')
    print (f'Alert Database Entries</span>')
    print ('</td>')
    print ('</tr>')
    print ('<tr valign="middle">')    
    print ('<td class="label">Email</td>')
    print ('<td class="label">Phone Nbr</td>')
    print ('<td class="label">Tide</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Air</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Water</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Wind</td>')
    print ('<td class="label">Dir</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Vari</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Notice</td>')
    print ('<td class="label">Ena</td>')
    print ('<td class="label">Event</td>')
    print ('<td class="label">Thresh</td>')
    print ('<td class="label">Repeat</td>')
    print ('<td class="label">Day</td>')
    print ('<td class="label">Active</td>')  
    print ('</tr>')
    for index, alert_dict in enumerate(alert_list):
        user = (
          (f1.decrypt(alert_dict['email_address'].encode())).decode())
        if (alert_dict['phone_number'] != None and
          alert_dict['phone_number'] != ''):
            telnbr = (
              f2.decrypt(alert_dict['phone_number'].encode())).decode()
        else:
            telnbr = ''
        print ('<tr valign="middle">')
        print (f'<td class="data">{user}</td>')
        print (f'<td class="data">{telnbr}</td>')
        print (f'<td class="data">{alert_dict["tide_level"]}</td>')
        if (alert_dict['tide_level_enable'] == 1 and
          alert_dict['tide_level'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tide_level'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['tide_level_day_only'] == 1 and
          alert_dict['tide_level'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tide_level'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["air_temp"]}</td>')
        if (alert_dict['air_temp_enable'] == 1 and
          alert_dict['air_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['air_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['air_temp_day_only'] == 1 and
          alert_dict['air_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['air_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["water_temp"]}</td>')
        if (alert_dict['water_temp_enable'] == 1 and
          alert_dict['water_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['water_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['water_temp_day_only'] == 1 and
          alert_dict['water_temp'] != ''):
            dispfld = 'Yes'
        elif alert_dict['water_temp'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["wind_speed"]}</td>')
        print (f'<td class="data">{alert_dict["wind_direction"]}</td>')
        if (alert_dict['wind_speed_enable'] == 1 and
          alert_dict['wind_speed'] != ''):
            dispfld = 'Yes'
        elif alert_dict['wind_speed'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['wind_speed_day_only'] == 1 and
          alert_dict['wind_speed'] != ''):
            dispfld = 'Yes'
        elif alert_dict['wind_speed'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        print (f'<td class="data">{alert_dict["tidal_variation"]}</td>')
        if (alert_dict['tidal_variation_enable'] == 1 and
          alert_dict['tidal_variation'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tidal_variation'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['tidal_variation_day_only'] == 1 and
          alert_dict['tidal_variation'] != ''):
            dispfld = 'Yes'
        elif alert_dict['tidal_variation'] != '':
            dispfld = 'No'
        else:
            dispfld = ''
        print (f'<td class="data">{dispfld}</td>')
        if (alert_dict['event_notice'] != None and
          alert_dict['event_notice'] != ''):
            print (
              f'<td class="data">{alert_dict["event_notice"]} Mins</td>')
            if (alert_dict['event_notice_enable'] == 1 and
              alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'Yes'
            elif (alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'No'
            else:
                dispfld = ''
            print (f'<td class="data">{dispfld}</td>')
            if alert_dict['event_type'] == 1:
                dispfld = 'Low'
            elif alert_dict['event_type'] == 2:
                dispfld = 'High'
            else:
                dispfld = ''
            print (f'<td class="data">{dispfld}</td>')
            if alert_dict['event_thresh'] != None:
                print (f'<td class="data">{alert_dict["event_thresh"]}</td>')
            else:            
                print (f'<td class="data"> </td>')
            if alert_dict['event_repeat'] != None:
                print (f'<td class="data">{alert_dict["event_repeat"]}</td>')
            else:            
                print (f'<td class="data"> </td>')
            if (alert_dict['event_day_only'] == 1 and
              alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'Yes'
            elif (alert_dict['event_notice'] != '' and
              alert_dict['event_notice'] != None):
                dispfld = 'No'
            else:
                dispfld = ''
            print (f'<td class="data">{dispfld}</td>')
        else:
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
            print (f'<td class="data"> </td>')
        print (f'<td class="data">{alert_dict["alerts_activated"]}</td>')
        print ('</tr>')
    print ('</table>')
    print ('<tr valign="middle">')
    print ('</p>')
    print ('</div>')
    print ('</body>')
    print ('</html>')
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
SQLPATH = constants_dict['SQLPATH']
displaytable = False
adminreq = False
activateuser = False
form = cgi.FieldStorage()
timeformat = "%Y-%m-%d %H:%M:%S.%f"
currenttime = datetime.now()
currentto = datetime.strptime(str(currenttime), timeformat)
sqlcon = sqlite3.connect(SQLPATH)
sqlcur = sqlcon.cursor()
sqlcur.execute("select * from useralerts")
column_names = [description[0] for description in sqlcur.description]
#print (column_names)
rows = sqlcur.fetchall()
alert_list = []
with open('/var/www/html/processalerts.log', 'a') as logfile:
    logfile.write (str(currenttime)[:-7]+' form contents:\n')
for thisfield in form:
    with open('/var/www/html/processalerts.log', 'a') as logfile:
        logfile.write (str(thisfield)+' '+form.getvalue(thisfield)+' of type '+str(type(form.getvalue(thisfield)))+'\n')
for row in rows:
    alert_dict= {}
    for index, column in enumerate(row):
        alert_dict[column_names[index]] = column
    alert_list.append(alert_dict)
with open('/var/www/html/k1','rb') as kfile:
    key1 = kfile.read()
with open('/var/www/html/k2','rb') as kfile:
    key2 = kfile.read()
with open('/var/www/html/k3','rb') as kfile:
    key3 = kfile.read()
f1 = Fernet(key1)
f2 = Fernet(key2)
f3 = Fernet(key3)
found = False
valid = False
sqlcur.execute("select * from userpass")
dbusers = sqlcur.fetchall()
userclr = form.getvalue('eaddr')
passclr = form.getvalue('passwd')
for user in dbusers:
    dbtime = user[0]
    dbuser = user[1]
    dbpass = user[2]
    dbval = user[3]
    cuser = dbuser.encode()
    cuser = f1.decrypt(cuser).decode()
    cpass = dbpass.encode()
    cpass = f3.decrypt(cpass).decode()  
    if cuser == userclr and cpass == passclr:
        userenc = dbuser
        found = True
        if dbval == 1:
            valid = True
        break
if not found or not valid:
    reportit(userclr,passclr,'invalid')
tmsgaddr = form.getvalue('taddr')
if tmsgaddr == None:
    tmsgaddr = ''
else:
    tmsgaddr = (tmsgaddr[0:3]+'-'+tmsgaddr[3:6]+'-'+tmsgaddr[6:]).encode()
    tmsgaddr = f2.encrypt(tmsgaddr).decode()
#reportit(userclr,userenc,tmsgaddr)
tlevel = form.getvalue('tlevel')
if tlevel == None:
    tlevel = ''
else:
    tlevel = float(tlevel)
daylight = form.getvalue('daylight')
if daylight == None:
    daylight = 0
else:
    daylight = int(daylight)
dayair = form.getvalue('dayair')
if dayair == None:
    dayair = 0
else:
    dayair = int(dayair)
enalev = form.getvalue('enalev')
if enalev == None:
    enalev = '""'
else:
    enalev = int(enalev)
atemp = form.getvalue('atemp')
if atemp == None:
    atemp = ''
else:
    atemp = int(atemp)
enaair = form.getvalue('enaair')
if enaair == None:
    enaair = '""'
else:
    enaair = int(enaair)
wtemp = form.getvalue('wtemp')
if wtemp == None:
    wtemp = ''
else:
    wtemp = int(wtemp)
enawat = form.getvalue('enawat')
if enawat == None:
    enawat = '""'
else:
    enawat = int(enawat)
daywat = form.getvalue('daywat')
if daywat == None:
    daywat = 0
else:
    daywat = int(daywat)
wind = form.getvalue('wind')
if wind == None:
    wind = ''
    windir = ''
else:
    wind = int(wind)
    windir = form.getvalue('windir')
    if windir != None:
       windir = windir.upper()
       if windir == 'ANY':
          windir = ''
    else:
        windir = ''
enawind = form.getvalue('enawind')
if enawind == None:
    enawind = '""'
else:
    enawind = int(enawind)
daywind = form.getvalue('daywind')
if daywind == None:
    daywind = 0
else:
    daywind = int(daywind)
vari = ''
try:
    vari = form.getvalue('vari')
    if vari == None:
        vari = ''
    else:
        varihilo = int(form.getvalue('varihilo'))
        vari = float(vari) * varihilo
except:
    with open('/var/www/html/processalerts.log', 'a') as logfile:
        logfile.write ('vari: '+vari+' setting to null\n')
    vari = ''
enavari = form.getvalue('enavari')
if enavari == None:
    enavari = '""'
else:
    enavari = int(enavari)
dayvari = form.getvalue('dayvari')
if dayvari == None:
    dayvari = 0
else:
    dayvari = int(dayvari)
evnotice = form.getvalue('evnotice')
if evnotice == None:
    evnotice = ''
else:
    evnotice = int(evnotice)
enaevent = form.getvalue('enaevent')
if enaevent == None:
    enaevent = '""'
else:
    enaevent = int(enaevent)
evtype = form.getvalue('evtype')
if evtype == None:
    evtype = '""'
else:
    evtype = int(evtype)
evrepeat = form.getvalue('evrepeat')
if evrepeat == None:
    evrepeat = ''
else:
    evrepeat = int(evrepeat)
evday = form.getvalue('evday')
if evday == None:
    evday = 0
else:
    evday = int(evday)
evthresh = form.getvalue('evthresh')
if evthresh == None:
    evthresh = ''
else:
    evthresh = float(evthresh)
activate = form.getvalue('activate')
if activate == None:
    activate = '0'
admin = form.getvalue('admin')
if admin == None:
    admin = '0'
atypes = [['tide_level', 'tide_level_enable', 'tide_level_day_only', tlevel,
              enalev, daylight, 'air_temp', 'wind_speed', 'tidal_variation',
           'event_notice', 'water_temp'],
         ['air_temp','air_temp_enable','air_temp_day_only',atemp,
              enaair,dayair, 'tide_level', 'wind_speed', 'tidal_variation',
           'event_notice', 'water_temp'],
         ['wind_speed', 'wind_speed_enable', 'wind_speed_day_only', wind,
              enawind, daywind, 'tide_level', 'air_temp', 'tidal_variation',
           'event_notice','water_temp'],
         ['tidal_variation','tidal_variation_enable','tidal_variation_day_only',
              vari, enavari, dayvari, 'tide_level', 'air_temp', 'wind_speed',
           'event_notice','water_temp'],
         ['event_notice', 'event_notice_enable', 'event_day_only',
              evnotice, enaevent, evday, 'tide_level', 'air_temp', 'wind_speed',
           'tidal_variation','water_temp'],
         ['water_temp', 'water_temp_enable', 'water_temp_day_only', wtemp,
              enawat, daywat, 'tide_level', 'air_temp','wind_speed',
           'event_notice','tidal_variation']]
if admin == '3814':
    adminreq = True
elif admin == '3815':
    activateuser = True
    actdeact = '1'
elif admin == '3816':
    actdeact = '0'
    activateuser = True
entryfound = False
for index, alert_dict in enumerate(alert_list):
    if alert_dict['email_address'] == userenc:
      #reportit(userclr,activate,enalev)
        activated = alert_dict['alerts_activated']
        dbtextadr = alert_dict['phone_number']
        entryfound = True
        break
if adminreq:
    create_admin_table()
elif (activate == '1' or activate == '2') and entryfound:
    suspend_resume()
    displaytable = True
elif activateuser and entryfound:
    suspend_resume()
    displaytable = True
else:
#
# If an entry for this email address is present, determine action to be taken.
#
    if entryfound:
        for atype in atypes:
            dbvals = ()
            sqlcommand = ""
#
# if the value field is not blank and and the action is delete, delete the
# entry for this user only if the entry contains no other type alerts,
# otherwise, remove this entry type only by setting the value to null.
#
            if atype[4] == 2 and atype[3] != '':
                sqlcommand = (
                  f'select * from useralerts where '+
                  f'email_address = "{userenc}" and '+
                  f'{atype[0]} = "{atype[3]}" and '+
                  f'{atype[6]} = "" and '+
                  f'{atype[7]} = "" and '+
                  f'{atype[8]} = "" and '+
                  f'{atype[9]} = "" and '+
                  f'{atype[10]} = ""')
                with open('/var/www/html/processalerts.log', 'a') \
                  as logfile:
                    logfile.write (str(currenttime)[:-7]+' '+sqlcommand+'\n')
                sqlcur.execute(sqlcommand)
                rep = sqlcur.fetchall()
                if len(rep) != 0:
                    sqlcommand = (
                      f'delete from useralerts where '+
                      f'email_address = "{userenc}" and '+
                      f'{atype[0]} = "{atype[3]}" and '+
                      f'{atype[6]} = "" and '+
                      f'{atype[7]} = "" and '+
                      f'{atype[8]} = "" and '+
                      f'{atype[9]} = "" and '+
                      f'{atype[10]} = ""')
                    with open('/var/www/html/processalerts.log', 'a') \
                      as logfile:
                        logfile.write (str(currenttime)[:-7]+' '+sqlcommand+'\n')
                    sqlcur.execute(sqlcommand)
                    sqlcon.commit()
#
# if the user was previously activated, save at least one (empty) entry with the 'activated' flag
#
                    if activated == 1:
                        sqlcur.execute(
                          f'select * from useralerts where '+
                          f'email_address = "{userenc}"')
                        rep = sqlcur.fetchall()
                        if len(rep) == 0:
                            dbvals = (str(currenttime),
                              userenc,
                              dbtextadr,
                              activated,
                      '','','','',
                      '','','','',
                      '','','','','',
                      '','','','',
                      '','','','',
                      '','','','','','')
                            sqlcur.execute(
                              f"INSERT INTO useralerts VALUES "+
                              "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,"+
                              "?,?,?,?,?,?,?,?,?,?,?)", dbvals)
                            sqlcon.commit()
#
# If there are other alert types in this database entry row, set the requested type field only to null and disable.
#
                else:
                    if atype[0] != 'wind_speed':
                        sqlcommand = (f'update useralerts set '+
                          f'{atype[0]} = "", '+
                          f'{atype[1]} = 0, '+
                          f'{atype[2]} = "", '+
                          'event_type = "", '+
                          'event_repeat = "", '+
                          'event_thresh = "" where '+
                          f'email_address = "{userenc}" and '+
                          f'{atype[0]} = {atype[3]}')
                    else:
                        sqlcommand = (f'update useralerts set '+
                          f'{atype[0]} = "", '+
                          f'{atype[1]} = 0, '+
                          f'{atype[2]} = "", '+
                          'event_type = "", '+
                          'event_repeat = "", '+
                          'event_thresh = "", '+
                          f'wind_direction = "{windir}" where '+
                          f'email_address = "{userenc}" and '+
                          f'{atype[0]} = {atype[3]}')
                    with open('/var/www/html/processalerts.log', 'a') \
                      as logfile:
                        logfile.write (str(currenttime)[:-7]+' '+sqlcommand+'\n')
                    sqlcur.execute(sqlcommand)
                    sqlcon.commit()
#
# Process enable and disable actions.
# If an entry already exists for this type and level, set enable/disable as appropriate,
# otherwise if no entry exists and action is enable, create a new entry.
#
            else:
                if atype[3] != '':
                    sqlcur.execute(f'select * from useralerts '+
                      f'where email_address = "{userenc}" and '+
                      f'{atype[0]} = {atype[3]}')
                    rep = sqlcur.fetchall()
                    with open('/var/www/html/processalerts.log', 'a') as logfile:
                        logfile.write (str(currenttime)[:-7]+' '+'sql reply '+str(rep)+'\n')
                    if len(rep) != 0:
                        if evthresh == '':
                            evthresh = '""'
                        sqlcommand = (f'update useralerts set '+
                          f'{atype[1]} = {atype[4]}, '+
                          f'{atype[2]} = {atype[5]}, '+
                          f'wind_direction = "{windir}", '+
                          f'event_type = {evtype}, '+
                          f'event_repeat = {evrepeat}, '+
                          f'event_thresh = {evthresh} where '+
                          f'email_address = "{userenc}" and '+
                          f'{atype[0]} = {atype[3]}')
                        with open('/var/www/html/processalerts.log', 'a') \
                          as logfile:
                            logfile.write (str(currenttime)[:-7]+' '+sqlcommand+'\n')
                        sqlcur.execute(sqlcommand)
                        sqlcon.commit()
                    elif atype[4] == 1:
#
# Use an existing empty entry for the type if available, otherwise create a new entry
#
                        sqlcur.execute(f'select * from useralerts where email_address = "{userenc}" and {atype[0]} = ""')
                        rep = sqlcur.fetchall()
                        if len(rep) != 0:
                            if atype[0] == 'wind_speed':
                                sqlcommand = (
                                  f'update useralerts set '+
                                  f'{atype[0]} = {atype[3]},'+
                                  f'{atype[1]} = {atype[4]}, '+
                                  f'{atype[2]} = {atype[5]},'+
                                  f'wind_direction = "{windir}" where '+
                                  f'dtime = "{rep[0][0]}"')
                            elif atype[0] == 'event_notice':
                                if evthresh == '':
                                    evthresh = '""'
                                sqlcommand = (
                                  f'update useralerts set '+
                                  f'{atype[0]} = {atype[3]},'+
                                  f'{atype[1]} = {atype[4]}, '+
                                  f'{atype[2]} = {atype[5]},'+
                                  f'event_type = {evtype}, '+
                                  f'event_repeat = {evrepeat},'+
                                  f'event_thresh = {evthresh} where '+
                                  f'dtime = "{rep[0][0]}"')
                            else:                    
                                sqlcommand = (
                                  f'update useralerts set '+
                                  f'{atype[0]} = {atype[3]},'+
                                  f'{atype[1]} = {atype[4]}, '+
                                  f'{atype[2]} = {atype[5]} '+
                                  f'where dtime = "{rep[0][0]}"')
                            with open('/var/www/html/processalerts.log', 'a') \
                              as logfile:
                                logfile.write (str(currenttime)[:-7]+' '+sqlcommand+'\n')
                            sqlcur.execute(sqlcommand)
                            sqlcon.commit()
                        else:               
                            dbvals = (
                              (str(currenttime),
                              userenc,
                              tmsgaddr,
                              activated,
                              tlevel,
                              enalev,
                              daylight,0,
                              atemp,
                              enaair,0,
                              dayair,
                              wind,
                              enawind,0,
                              daywind,
                              windir,
                              vari,
                              enavari,0,
                              dayvari,
                              wtemp,
                              enawat,0,
                              daywat,
                              evnotice,
                              enaevent,
                              evtype,
                              evrepeat,
                              evday,
                              evthresh))
                            sqlcur.execute(
                              f"INSERT INTO useralerts VALUES "+
                              "(?,?,?,?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?,?,?,"+
                              "?,?,?,?,?,?,?,?,?,?,?)", dbvals)
                            sqlcon.commit()
            if sqlcommand != "":
                subject = 'Tide Station Alert Message'
                email_message = (
                  'Tide station alerts have been updated for '+
                  f'{userclr}, please review')
                for recipient in admin_email:                 
                    send_email(recipient, subject, email_message)
        displaytable = True
    else:
        if ((tlevel != '' and enalev == 1)
          or (atemp != '' and enaair == 1)
          or (wind != '' and enawind == 1)
          or (evnotice != '' and enaevent == 1)
          or (wtemp != '' and enawat == 1)
          or (vari != '' and enavari == 1)):
            dbvals = (
              str(currenttime),
              userenc,
              tmsgaddr,1,
              tlevel,
              enalev,
              daylight,0,
              atemp,
              enaair,0,
              dayair,
              wind,
              enawind,0,
              daywind,
              windir,
              vari,
              enavari,0,
              dayvari,
              wtemp,
              enawat,0,
              daywat,
              evnotice,
              enaevent,
              evtype,
              evrepeat,
              evday,
              evthresh)
            sqlcur.execute(
              f"INSERT INTO useralerts VALUES "+
              "(?,?,?,?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?,?,?, "+
              "?,?,?,?,?,?,?,?,?,?,?)", dbvals)
            sqlcon.commit()
            displaytable = True
            
    if dbvals:
        subject = 'Tide Station Alert Message'
        email_message = ('Tide station alerts have been updated for '+
          f'{userclr}, please review')
        for recipient in admin_email:                 
           send_email(recipient, subject, email_message)

if displaytable or (entryfound and admin == '0'):
    create_table()

elif not entryfound and admin != '1':
    print ("Content-type:text/html\r\n\r\n")
    print ('<html>')
    print ('<head>')
    print ('<title>Tide Station Alerts</title>')
    print ('<style type="text/css">')
    print ('.center-screen {')
    print ('display: flex;')
    print ('flex-direction: column;')
    print ('justify-content: center;')
    print ('align-items: center;')
    print ('text-align: center;')
    print ('}')
    print ('</style>')
    print ('</head>')
    print ('<body><font size = "4">')
    print ('<div class="center-screen">')
    print ('<span style="border:2px black solid; width: 450px;">')
    print ('<img src="/CoastalMaine.png" width="450" height="300"/>')
    print ('<h1 style="width: 430px; text-align: center; font-size: '+
      '25px; font-color: black; padding: 4px;">Alert Request</h1>')
    print (f'<p style="width: 438px; text-align: center; font-size: '+
      '25px; padding: 4px; border: 2px solid red;">')
    print (f'There are currently no alert requests for {userclr}')
    print ('</p>')
    print ('</span>')
    print ('</div>')
    print ('</body>')
    print ('</html>')

