#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
import time
import sys
import os
from datetime import datetime, date, timedelta, timezone
import sqlite3
import math
import cgi, cgitb
from dotenv import load_dotenv, find_dotenv
from suntimes import SunTimes

global tide, tk, log, prout, selectedtide, logfile, radinc, curtime, windlist, \
       halftide, fulltide, sam_int, sqlcon, sqlcur, predlist, predicts, turntime2, \
       prestate, prestate2, sqltimeformat, turntime, tagbutt, vari_height, plotdays, \
       formdate, tags, endplotime, canvas_height, plot_height, canvas_width, points, \
       plot_width, windbutt, wind, form, rain, wxlength, left_scale_x, outfile, \
       title_start_y, title_end_y, title_height, mintmeformat, temp, right_scale_x, \
       tide_start_y, tide_end_y, tide_height, station1, station2, station1chk, station2chk, \
       vari_start_y, vari_end_y, vari_height, msgtime, grid_height, \
       vari2_start_y, vari2_end_y, vari2_height, station1cal, station2cal, \
       wind_start_y, wind_end_y, wind_height, s1enable, s2enable, \
       rain_start_y, rain_end_y, rain_height, maxpred, minpred, predave, \
       temp_start_y, temp_end_y, temp_height, tag_y, wxsup, tideave, \
       batv, batv_start_y, batv_end_y, batv_height, debugit, \
       batv_grid_nbr, batv_grid_y, batvinit, batv_y_fact, tide_station_url, \
       batv2, batv2_start_y, batv2_end_y, batv2_height, station_location, \
       batv2_grid_nbr, batv2_grid_y, batv2init, batv2_y_fact, \
       dtime_start_y, dtime_end_y, dtime_height, banflag, banner, \
       tide_grid_nbr, vari_grid_nbr, wind_grid_nbr, rain_grid_nbr, \
       tide_grid_y, vari_grid_y, wind_grid_y, rain_grid_y, tidesup, \
       temp_grid_nbr, temp_grid_y, windarrow, tidelist, dbquerytime, \
       listDate, localsunrise, localsunset, sun, mintide, minbatv, \
       maxbatv, minbatv2, maxbatv2, batvlist, batv2list, sun, localsunrise, localsunset
#
# Function to generate the predicted tide at one minute intervals. The predicted tide
# levels are saved in [predlist] for the requested plot duration based on the NOAA tide tables.
#
def tide_predict():
   global curtime, halftide, fulltide, sam_int, sqlcon, log, prout, sqlcur, tidelevel, \
          predlist, predicts, selectedtide, plotdays, maxpred, minpred, predave
          
   startproc = False
   tidesecs = 0
   predlist = []
   predicts = []
   maxpred = -99
   minpred = 99
#
# The start time for the tide prediction is the current time minus 24 hours.
#
   #curtime = datetime.now()
   maketime = curtime - timedelta(days=plotdays)
   then = maketime - timedelta(hours=8)
   currentday = datetime.strftime(curtime, "%d")
#
# Select the entries from the appropriate noaa tides table with
# time tags that are greater than the start time - 8 hours
#
   trytide = 0
   while len(predicts) == 0:
      sqlcur.execute(f"select * from {selectedtide} where dtime >= ? order by dtime", (str(then),))
      predicts = sqlcur.fetchall()
      if len(predicts) == 0:
         trytide += 1
         if trytide >= 3:
            exit()
   lastime = ''
   for line in predicts:
      thistime = line[0]
      thisto = datetime.strptime(thistime,"%Y-%m-%d %H:%M:%S")
      delta = round(thisto.timestamp()-maketime.timestamp(),2)
      thistide = float(line[1])
      thistate = line[2]
#
# for the first entry, initialize last values and continue
# with the next entry in the list
#
      if lastime == '':
         lastime = thisto
         lasttide = thistide
         lastdelta = delta
         continue
#
# When the delta changes sign, it means that the current time
# is within the current and previous table entries, so perform
# parameter initialization and processing.
#

      if delta >= 0 and lastdelta < 0:
         simtime = maketime
         tidesecs = 0
         startproc = True
         restart = True

      if startproc:
#
# Calculate and set the value corresponding to the change
# in radians per second.
#
         deltadiff = abs(thisto.timestamp()-lastime.timestamp())
         radinc = fulltide/deltadiff
#
# On restart, the starting radians are set depending on whether
# this iteration is from low to high tide or vice versa.
#
         if restart:
            if lasttide < thistide:
               radians = halftide*3
            else:
               radians = halftide      
            restart = False
            tidestart = lastime
#
# The tideoff value (tide offset) is always set to low tide.
# The tide difference is used to calculate tide level.
#
         if lasttide < thistide:
            tideoff = lasttide
         else:
            tideoff = thistide      
         tidediff = abs(thistide - lasttide)
#
# Radian seconds are the difference between the time of peak high
# or low tide and the current or simulated time.
#
         radsecs = round(simtime.timestamp()-tidestart.timestamp(),2)
         radians = radians+radsecs*radinc
         radians = radians % (math.pi*2)
         tidelevel = math.sin(radians)*tidediff/2+(tidediff/2)+tideoff
#
# The first entry in the predlist is for the current time - 24 hours.
# The remainder of the list contains predictions for the next 48 hours.
#
         while simtime < thisto and tidesecs < 86400*plotdays:
            predlist.append([simtime,tidesecs,tidelevel,thistate])
            simtime = simtime+timedelta(seconds=sam_int)
            radians = radians+sam_int*radinc
            radians = radians % (math.pi*2)   
            tidelevel = math.sin(radians)*tidediff/2+(tidediff/2)+tideoff
            tidesecs += sam_int
      if tidesecs >= 86400*plotdays:
         break
      restart = True
      lastime = thisto
      lasttide = thistide
      lastdelta = delta
   predsum = 0
   predave = 3.5
   if len(predlist) != 0:
      for chkent in predlist:
         if chkent[2] > maxpred:
            maxpred = chkent[2]
         if chkent[2] < minpred:
            minpred = chkent[2]
   return

date = date.today()
curtime = datetime.now()
msgtime = str(curtime)[:-10]
filetag = "tide"+datetime.strftime(curtime, "%y%m%d%H%M%S")+".html"
outfile = open(filetag, "w")   

log = False
prout = False
tags = False
station1 = False
station2 = False
wind = False
rain = False
temp = False
debugit = 30
#
# Get station name for webpage title
#
envfile = find_dotenv('tide.env')
if load_dotenv(envfile):
   station_location = os.getenv('STATION_LOCATION')
   station_latitude = os.getenv('STATION_LATITUDE')
   station_longitude = os.getenv('STATION_LONGITUDE')
   tide_station_url = os.getenv('TIDE_STATION_URL')
#
# Establish SQLite3 connection to the tides.db database
#

try:
   sqlcon = sqlite3.connect(f'/home/tide/Uploads/tides.db')
   sqlcur = sqlcon.cursor()
except:
   with open('/var/www/html/tideplot.log', 'a') as logfile:
      logfile.write (msgtime+ 'tideplot.py sqlite3 connection failed\n')                  
   exit()
#
# Read initialization data from iparams table
#
#try:
if True:
   sqlcur.execute("select * from iparams")
   iparams = sqlcur.fetchall()
   banflag = 0
   banner  = ''
   #banflag = iparams[0][2]
   #banner = iparams[0][3]
   station1cal = iparams[0][5]
   station2cal = iparams[0][6]
   s1enable = iparams[0][7]
   s2enable = iparams[0][8]
   #
   # Get the lastest time entry in the tides.db database
   # 
   sqltimeformat = "%Y-%m-%d %H:%M:%S"
   mintimeformat = "%Y-%m-%d %H:%M"
   formdate = curtime.strftime("%Y-%m-%d")
   #
   # Initialization parameters
   #
   init = True
   if init:
      plotdays = 3
      tags =  True
      tagchk = 'checked'
      station1 =  True
      station1chk = 'checked'
      station2 =  True
      station2chk = 'checked'
      wind = True
      windchk = 'checked'
      rain = True
      rainchk = 'checked'
      temp = True
      tempchk = 'checked'
      batv = True
      batvchk = 'checked'
      batv2 = False
      batv2chk = ''
   plotdays = 3
   canvas_width = 1200
   default_height = 750
   selectedtide = 'predicts'
   radinc = math.pi*2/91080
   prestate = ''
   prestate2 = ''
   halftide = math.pi/2
   fulltide = math.pi
   sam_int = 60
   predicts = []
   turntime = ''
   turntime2 = ''
   tide_predict()
   tidelist = []
   batvlist= []
   batv2list = []
   windlist = []
   localsunrise = 0
   localsunset = 0
   listDate = 0

   dbquerytime = curtime - timedelta(days=plotdays)
   sqlcur.execute("select dtime, stationid, distance from sensors where dtime "+ \
                    "between ? and ? order by dtime", (str(dbquerytime),str(curtime)))
   tidelist = sqlcur.fetchall()  
   if s1enable:
      sqlcur.execute("select dtime, batv from sensors where stationid = 1 and dtime "+ \
                    "between ? and ? order by dtime", (str(dbquerytime),str(curtime)))
      batvlist = sqlcur.fetchall()
   if s2enable:   
      sqlcur.execute("select dtime, batv from sensors where stationid = 2 and dtime "+ \
                    "between ? and ? order by dtime", (str(dbquerytime),str(curtime)))
      batv2list = sqlcur.fetchall()
   
   sqlcur.execute("select * from wxdata where dtime "+ \
                 "between ? and ? order by dtime", (str(dbquerytime),str(curtime)))
   sun = SunTimes(float(station_longitude),float(station_latitude))
   wxlist = sqlcur.fetchall()
   wxlength = len(wxlist)
   if wxlength != 0:
      wxsup = True
   else:
      wxsup = False
   tidesup = False
   tidesum = 0
   tidesum2 = 0
   tideave = 0
   tideave2 = 0
   maxtide = -99
   mintide = 99
   tidents = 0
   tidents2 = 0
   minbatv = 99
   maxbatv = -99
   minbatv2 = 99
   maxbatv2 = -99
   tide_grid_nbr = 0
   vari_grid_nbr = 0
   wind_grid_nbr = 0
   rain_grid_nbr = 0
   temp_grid_nbr = 0
   batv_grid_nbr = 0
   batv_grid_span = 0
   batv2_grid_nbr = 0
   batv2_grid_span = 0
   wind_height = 0
   rain_height = 0
   temp_height = 0
   batv_height = 0
   batv2_height = 0
   tide_grid_y = 0
   vari_grid_y = 0
   wind_grid_y = 0
   rain_grid_y = 0
   temp_grid_y = 0
   batv_grid_y = 0
   batv2_grid_y = 0
   grid_height = 30
   if len(tidelist) != 0:
      tidesup = True
      s2cnt = 0
      for chkent in tidelist:
         tidents += 1
         if station1 and chkent[1] == 1 and s1enable and chkent[2] != None:
            if chkent[2] > maxtide:
               maxtide = station1cal - chkent[2]/12 
            if chkent[2] < mintide:
               mintide = station1cal - chkent[2]/12
         elif station2 and chkent[1] == 2 and s2enable and chkent[2] != None:
            s2cnt += 1
            if chkent[2] > maxtide:
               maxtide = station2cal - chkent[2]/12
            if chkent[2] < mintide:
               mintide = station2cal - chkent[2]/12 
   print ('station2 entries: '+str(s2cnt))
   if len(batvlist) != 0 and s1enable:
      for chkent in batvlist:
         if chkent[1] != None and chkent[1] < 4.3 and chkent[1] > 3.3:
            if chkent[1] > maxbatv:
               maxbatv = chkent[1]
            if chkent[1] < minbatv:
               minbatv = chkent[1]
      #print ('minbatv: '+str(minbatv)+' maxbatv: '+str(maxbatv))
      if minbatv == 99 or maxbatv == -99:
         batv = False
      else:
         minbatv1 = int(minbatv/0.01)
         minbatv = round(minbatv1*0.01,2)
         maxbatv1 = int(maxbatv/0.01)
         maxbatv = round(maxbatv1*0.01+0.01,2)
   else:
      batv = False
   if len(batv2list) != 0 and s2enable:
      for chkent in batv2list:
         if chkent[1] != None and chkent[1] < 4.3 and chkent[1] > 3.3:
            if chkent[1] > maxbatv2:
               maxbatv2 = chkent[1]
            if chkent[1] < minbatv2:
               minbatv2 = chkent[1]
      if minbatv2 == 99 or maxbatv2 == -99:
         batv2 = False
      else:
         minbatv1 = int(minbatv2/0.01)
         minbatv2 = round(minbatv1*0.01,2)
         maxbatv1 = int(maxbatv2/0.01)
         maxbatv2 = round(maxbatv1*0.01+0.01,2)
   else:
      batv2 = False
   if maxpred > maxtide:
      maxtide = maxpred
   if minpred < mintide:
      mintide = minpred
   tideave = round((maxtide-mintide)/2+math.floor(mintide),1)
   tide_grid_nbr = round(maxtide+0.5)-math.floor(mintide)
   vari_grid_nbr = 4
   total_grids = tide_grid_nbr
   nbr_gaps = 0
   if station1 and s1enable:
      total_grids += vari_grid_nbr
      nbr_gaps += 1
   if station2 and s2enable:
      total_grids += vari_grid_nbr
      nbr_gaps += 1
   if wind:
      wind_grid_nbr = 8
      total_grids += wind_grid_nbr
      nbr_gaps += 1
      wind_height = wind_grid_nbr*grid_height
      wind_grid_y = round(wind_height/wind_grid_nbr/10,3)
   if rain:
      rain_grid_nbr = 4
      total_grids += rain_grid_nbr
      nbr_gaps += 1
      rain_height = rain_grid_nbr*grid_height
      rain_grid_y = round(rain_height/rain_grid_nbr,3)
   if temp:
      temp_grid_nbr = 9
      total_grids += temp_grid_nbr
      nbr_gaps += 1
      temp_height = temp_grid_nbr*grid_height
      temp_grid_y = round(temp_height/temp_grid_nbr,3)
   if batv and s1enable:
      batv_grid_nbr = round((maxbatv-minbatv)/0.01)
      total_grids += batv_grid_nbr  
      nbr_gaps += 1
      batv_grid_span = round(maxbatv-minbatv,2)
      batv_height = batv_grid_nbr*grid_height
      batv_grid_y = round(batv_height/batv_grid_nbr,3)
      batv_y_fact = batv_height/batv_grid_span
   if batv2 and s2enable:
      batv2_grid_nbr = round((maxbatv2-minbatv2)/0.01)
      total_grids += batv2_grid_nbr  
      nbr_gaps += 1
      batv2_grid_span = round(maxbatv2-minbatv2,2)
      batv2_height = batv2_grid_nbr*grid_height
      batv2_grid_y = round(batv2_height/batv2_grid_nbr,3)
      batv2_y_fact = batv2_height/batv2_grid_span

   title_height = 10
   dtime_height = 10
   gap_size = 30
   dtime_height = 30
   footer_height = 12
   tide_height = tide_grid_nbr*grid_height
   vari_height = vari_grid_nbr*grid_height
   tide_grid_y = round(tide_height/tide_grid_nbr,3)
   vari_grid_y = round(vari_height/vari_grid_nbr,3)
   wind_start_y = 0
   wind_end_y = 0
   rain_start_y = 0
   rain_end_y = 0
   temp_start_y =0
   temp_end_y = 0
   vari_start_y = 0
   vari_end_y =0
   vari2_start_y = 0
   vari2_end_y =0
   total_grid_height = total_grids*grid_height
   total_gaps = gap_size*nbr_gaps
   canvas_height = dtime_height+title_height+total_gaps+footer_height+total_grid_height
   plot_width = canvas_width-30
   windarrow = [[0,8],[0,-8],[-3,3],[3,3]]
   right_scale_x = plot_width+15
   left_scale_x = 15
   dtime_start_y = 0
   dtime_end_y = dtime_start_y + dtime_height
   tide_start_y = dtime_end_y
   tide_end_y = int(tide_height+tide_start_y)
   tag_y = int(tide_end_y-(tide_grid_nbr/2*grid_height))
   next_y = tide_end_y
   if station1 and s1enable:
      vari_start_y = next_y+gap_size
      vari_end_y = int(vari_height+vari_start_y)
      next_y = vari_end_y
   if station2 and s2enable:
      vari2_start_y = next_y+gap_size
      vari2_end_y = int(vari_height+vari2_start_y)
      next_y = vari2_end_y
   if wind:
      wind_start_y = next_y+gap_size
      wind_end_y = int(wind_height+wind_start_y)
      next_y = wind_end_y
   if rain:
      rain_start_y = next_y+gap_size
      rain_end_y = int(rain_height+rain_start_y)
      next_y = rain_end_y
   if temp:
      temp_start_y = next_y+gap_size
      temp_end_y = int(temp_height+temp_start_y)
      next_y = temp_end_y
   if batv and s1enable:
      batv_start_y = next_y+gap_size
      batv_end_y = int(batv_height+batv_start_y)
      next_y = batv_end_y
   if batv2 and s2enable:
      batv2_start_y = next_y+gap_size
      batv2_end_y = int(batv2_height+batv2_start_y)
else:
#except Exception as errmsg:
   pline = msgtime+' Error - '+str(errmsg)
   with open('/var/www/html/tideplot.log', 'a') as logfile:
      logfile.write (pline+'\n')
#
#  Function to obtain and process plot parameters.
#
def proc_data():
   global tide, tk, logfile, log, predlist, prestate2, prestate, prout, sqltimeformat, turntime, \
          formdate, plotdays, sqltimeformat, vari_height, curtime, sqlcon, sqlcur, turntime2, \
          canvas_height, plot_height, canvas_width, plot_width, points, wind, rain, wxlength, \
          title_start_y, title_end_y, title_height, mintimeformat, temp, windlist, outfile, \
          tide_start_y, tide_end_y, tide_height, station1, station2, station1chk, station2chk, \
          vari_start_y, vari_end_y, vari_height, msgtime, grid_height, \
          vari2_start_y, vari2_end_y, vari2_height, left_scale_x, right_scale_x, \
          wind_start_y, wind_end_y, wind_height, s1enable, s2enable, \
          rain_start_y, rain_end_y, rain_height, tideave, station1cal, station2cal, \
          temp_start_y, temp_end_y, temp_height, tag_y, wxsup, station_location, \
          batv, batv_start_y, batv_end_y, batv_height, debugit, \
          batv_grid_nbr, batv_grid_y, batvinit, batv_y_fact, \
          dtime_start_y, dtime_end_y, dtime_height, banflag, banner, \
          tide_grid_nbr, vari_grid_nbr, wind_grid_nbr, rain_grid_nbr, \
          tide_grid_y, vari_grid_y, wind_grid_y, rain_grid_y, tidesup, \
          temp_grid_nbr, temp_grid_y, windarrow, tidelist, dbquerytime, \
          listDate, localsunrise, localsunset, sun, mintide, minpred
   canw_str = str(canvas_width)
   bored = 25
   currenttime = datetime.now()
   hrtime = datetime.strftime(currenttime, "%H:%M")
   outfile.write ("Content-type:text/html\r\n\r\n\r\n")
   outfile.write ('<html>\n')
   outfile.write ('<head>\n')
   outfile.write (f'<title>{station_location} Tide and Weather</title>\n')
   outfile.write ('<style type="text/css" media="screen">\n')
   outfile.write ('*{\n')
   outfile.write ('margin: 0px 0px 0px 0px;\n')
   outfile.write ('padding: 0px 0px 0px 0px;\n')
   outfile.write ('}\n') 
   outfile.write ('canvas {\n')
   outfile.write ('padding-left: 0;\n')
   outfile.write ('padding-right: 0;\n')
   outfile.write ('margin-left: auto;\n')
   outfile.write ('margin-right: auto;\n')
   outfile.write ('display: block;\n')
   outfile.write (f'width: {canw_str}px;\n')
   outfile.write ('}\n')
   outfile.write ('div {\n')
   outfile.write ('padding-left: 0;\n')
   outfile.write ('padding-right: 0;\n')
   outfile.write ('margin-left: auto;\n')
   outfile.write ('margin-right: auto;\n')
   outfile.write ('display: block;\n')
   outfile.write (f'width: {canw_str}px;\n')
   outfile.write ('}\n')
   outfile.write ('body, html {\n')
   outfile.write ('padding: 3px 3px 3px 3px;\n')
   outfile.write ('background-color: black;\n')
   outfile.write ('font-family: Verdana, sans-serif;\n')
   outfile.write ('font-size: 12pt;\n')
   outfile.write ('text-align: center;\n')
   outfile.write ('}\n')
   outfile.write ('</style>\n')
   outfile.write ('</head>\n')
   outfile.write ('<body style="background-color:black;">\n')
   outfile.write (f'<div style="background-color: #E0F8F1; width: {canvas_width}px; text-align: center; margin-left: auto; margin-right: auto;">\n') 
   outfile.write (f'{station_location}<br>')  
   outfile.write (f'<form style="background-color: #E0F8F1; width: {canvas_width}px; text-align: center; margin-left: auto; margin-right: auto;" id="myForm" action="/cgi-bin/tideplot.cgi" method="post">\n') 
   outfile.write ('<label for="endate">End date:</label>\n')
   outfile.write (f'<input type="date" name="endate" id="endate" value="{formdate}">&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<label for="dayspan">Plot span in days:</label>\n')
   outfile.write (f'<input type="number" name="dayspan" id="dayspan" value="{str(plotdays)}" step=1 min="1" max="30" required>&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<input type="hidden" name="screenwidth" id="screenwidth" value=''/>\n')
   outfile.write ('<input type="hidden" name="screenheight" id="screenheight" value=''/>\n')
   if s1enable:
      outfile.write ('<label for="station1">Station 1</label>\n')
      outfile.write (f'<input type="checkbox" id="station1" name="station1" value="1" {station1chk}>&nbsp&nbsp&nbsp&nbsp\n')
   if s2enable:
      outfile.write ('<label for="station2">Station 2</label>\n')
      outfile.write (f'<input type="checkbox" id="station2" name="station2" value="0" {station2chk}>&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<label for="tags">Tide Markers</label>\n')
   outfile.write (f'<input type="checkbox" id="tags" name="tags" value="1" {tagchk}>&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<label for="wind"> Wind</label>\n')
   outfile.write (f'<input type="checkbox" id="wind" name="wind" value="1" {windchk}>&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<label for="rain">Rain</label>\n')
   outfile.write (f'<input type="checkbox" id="rain" name="rain" value="1" {rainchk}>&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<label for="temp">Temperature</label>\n')
   outfile.write (f'<input type="checkbox" id="temp" name="temp" value="1" {tempchk}>&nbsp&nbsp&nbsp&nbsp\n')
   if s1enable:
      outfile.write ('<label for="batv">BatV 1</label>\n')
      outfile.write (f'<input type="checkbox" id="batv" name="batv" value="1" {batvchk}>&nbsp&nbsp&nbsp&nbsp\n')
   if s2enable:
      outfile.write ('<label for="batv2">BatV 2</label>\n')
      outfile.write (f'<input type="checkbox" id="batv2" name="batv2" value="0" {batv2chk}>&nbsp&nbsp&nbsp&nbsp\n')
   outfile.write ('<input type="submit" value="Refresh"/>\n')
   outfile.write ('</form>\n')
   outfile.write ('</div>')
   outfile.write ('<script>\n')
   outfile.write ('var w = window.innerWidth;\n')
   outfile.write ('var h = window.innerHeight;\n')
   outfile.write ('document.getElementById("screenwidth").value=w;\n')
   outfile.write ('document.getElementById("screenheight").value=h;\n')
   outfile.write ('</script>\n')     
   outfile.write ('<div>\n')
   #outfile.write (f'<canvas id="tideplot" width={canvas_width} height={canvas_height}\n')
   outfile.write (f'<canvas id="tideplot" width={canvas_width} height={canvas_height}\n')
   outfile.write ('style="text-align: center; border:2px solid white; background-color: #E0F8F1">\n')
   outfile.write ('</canvas>\n')
   outfile.write ('<script>\n')
   outfile.write ('var canvas = document.getElementById("tideplot");\n')
   outfile.write ('var ctx = canvas.getContext("2d");\n')
   outfile.write ('ctx.fillStyle = "#1932E1";\n')
   outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
   outfile.write ('ctx.textAlign = "left";\n')  
   outfile.write ('ctx.strokeStyle = "black";\n')
   wxlist = []
   msgtime = str(curtime)[:-10]
   curhour = datetime.now().hour
   curminute = datetime.now().minute
   curhrmin = datetime.strftime(curtime, "%H:%M")
   sqlcur.execute("select * from wxdata where dtime "+ \
                  "between ? and ? order by dtime", (str(dbquerytime),str(curtime)))
   wxlist = sqlcur.fetchall()
   wxlength = len(wxlist)
   #if debugit >= 0:
   #   pline = msgtime+' '+str(wxlist)
   #   with open('/var/www/html/tideplot.log', 'a') as logfile:
   #      logfile.write (pline+'\n')   
   #   debugit -= 1
   if tidesup:
      starttime = datetime.strptime(tidelist[0][0], sqltimeformat)
   else:
      starttime = dbquerytime
   offtime = starttime.timestamp() - dbquerytime.timestamp()
   aidx = 0
   bidx = 0
   b2idx = 0
   widx = 0
   saidx = -10
   swidx = -10
   pstart = 30
   windcount = 0
   windex = 0
   tideinit = False
   variinit = False
   vari2init = False
   wxinit = False
   rxinit = False
   txinit = False
   varistart_x = -99
   varistart_y = -99
   vari2start_x = -99
   vari2start_y = -99
   tidestart_x = -99
   tidestart_y = -99
   maxwind = 0
   maxwdir = 0
#
# Draw plot borders, horizontal grid lines and legend
#
   outfile.write ('ctx.lineWidth = 1;\n')
   outfile.write ('ctx.fillStyle = "black";\n')
   outfile.write ('ctx.font = "12px Arial";\n')
   outfile.write ('ctx.globalCompositeOperation = "source-over";\n')
   x_start = 30
   gridx = plot_width
   gridy = tide_end_y
   for x in range(0,tide_grid_nbr+1):
      if x == 0 or x == tide_grid_nbr:
         outfile.write ('ctx.strokeStyle = "black";\n')
      else:
         outfile.write ('ctx.strokeStyle = "gray";\n')
      linbr = str(x+int(mintide))
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{int(gridy)});\n')
      outfile.write (f'ctx.lineTo({gridx},{int(gridy)});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write (f'ctx.fillText("{linbr}", {left_scale_x}, {int(gridy)});\n')
      outfile.write (f'ctx.fillText("{linbr}", {right_scale_x}, {int(gridy)});\n')
      gridy = gridy-grid_height
   if station1 and s1enable:
      outfile.write ('ctx.strokeStyle = "black";\n')   
      outfile.write ('ctx.textAlign = "center";\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{vari_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{vari_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width-1},{vari_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width-1},{vari_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      gridy = 0
      for x in range(0,vari_grid_nbr+1):
         if x == 0 or x == 2 or x == vari_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(vari_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(vari_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write ('ctx.fillStyle = "black";\n')
         outfile.write (f'ctx.fillText("{str(2-x)}", {left_scale_x}, {int(vari_start_y+gridy)});\n')                          
         outfile.write (f'ctx.fillText("{str(2-x)}", {right_scale_x}, {int(vari_start_y+gridy)});\n')                          
         gridy += grid_height
   if station2 and s2enable:
      outfile.write ('ctx.strokeStyle = "black";\n')   
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{vari2_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{vari2_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width-1},{vari2_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width-1},{vari2_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      gridy = 0   
      for x in range(0,vari_grid_nbr+1):
         if x == 0 or x == 2 or x == vari_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(vari2_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(vari2_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write ('ctx.fillStyle = "black";\n')
         outfile.write (f'ctx.fillText("{str(2-x)}", {left_scale_x}, {int(vari2_start_y+gridy+3)});\n')                          
         outfile.write (f'ctx.fillText("{str(2-x)}", {right_scale_x}, {int(vari2_start_y+gridy+3)});\n')                          
         gridy += grid_height
   if wind:
      gridy = 0
      for x in range(0,wind_grid_nbr+1):
         if x == 0 or x == wind_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(wind_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(wind_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write (f'ctx.fillText("{str((wind_grid_nbr-x)*10)}", {left_scale_x}, {int(wind_start_y+gridy+6)});\n')                          
         outfile.write (f'ctx.fillText("{str((wind_grid_nbr-x)*10)}", {right_scale_x}, {int(wind_start_y+gridy+6)});\n')                          
         gridy += wind_grid_y*10
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{wind_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{wind_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width},{wind_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width},{wind_end_y});\n')
      outfile.write ('ctx.stroke();\n')                           
   if rain:
      gridy = 0
      for x in range(0,rain_grid_nbr+1):
         if x == 0 or x == rain_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(rain_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(rain_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write ('ctx.fillStyle = "black";\n')
         outfile.write (f'ctx.fillText("{str((rain_grid_nbr-x)/2)}", {left_scale_x}, {int(rain_start_y+gridy)});\n')                          
         outfile.write (f'ctx.fillText("{str((rain_grid_nbr-x)/2)}", {right_scale_x}, {int(rain_start_y+gridy)});\n')                          
         gridy += rain_grid_y         
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{rain_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{rain_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width},{rain_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width},{rain_end_y});\n')
      outfile.write ('ctx.stroke();\n') 
   if temp:
      gridy = 0
      for x in range(0,temp_grid_nbr+1):
         if x == 0 or x == temp_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(temp_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(temp_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write ('ctx.fillStyle = "black";\n')
         outfile.write (f'ctx.fillText("{str((temp_grid_nbr-x)*10)}", {left_scale_x}, {int(temp_start_y+gridy+5)});\n')                          
         outfile.write (f'ctx.fillText("{str((temp_grid_nbr-x)*10)}", {right_scale_x}, {int(temp_start_y+gridy+5)});\n')                          
         gridy += temp_grid_y         
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{temp_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{temp_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width},{temp_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width},{temp_end_y});\n')
      outfile.write ('ctx.stroke();\n')
   if batv and s1enable:
      gridy = 0
      for x in range(0,batv_grid_nbr+1):
         if x == 0 or x == batv_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(batv_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(batv_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write ('ctx.fillStyle = "black";\n')
         outfile.write (f'ctx.fillText({format(maxbatv-x*0.01,".2f")}, {left_scale_x}, {int(batv_start_y+gridy+5)});\n')                          
         outfile.write (f'ctx.fillText({format(maxbatv-x*0.01,".2f")}, {right_scale_x}, {int(batv_start_y+gridy+5)});\n')                          
         gridy += batv_grid_y        
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{batv_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{batv_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width},{batv_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width},{batv_end_y});\n')
      outfile.write ('ctx.stroke();\n')       
   if batv2 and s2enable:
      gridy = 0
      for x in range(0,batv2_grid_nbr+1):
         if x == 0 or x == batv2_grid_nbr:
            outfile.write ('ctx.strokeStyle = "black";\n')
         else:
            outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write ('ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({x_start},{int(batv2_start_y+gridy)});\n')
         outfile.write (f'ctx.lineTo({plot_width},{int(batv2_start_y+gridy)});\n')
         outfile.write ('ctx.stroke();\n')
         outfile.write ('ctx.fillStyle = "black";\n')
         outfile.write (f'ctx.fillText({format(maxbatv2-x*0.01,".2f")}, {left_scale_x}, {int(batv2_start_y+gridy+5)});\n')                          
         outfile.write (f'ctx.fillText({format(maxbatv2-x*0.01,".2f")}, {right_scale_x}, {int(batv2_start_y+gridy+5)});\n')                          
         gridy += batv2_grid_y         
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({x_start},{batv2_start_y});\n')
      outfile.write (f'ctx.lineTo({x_start},{batv2_end_y});\n')
      outfile.write ('ctx.stroke();\n')
      outfile.write ('ctx.beginPath();\n')
      outfile.write (f'ctx.moveTo({plot_width},{batv2_start_y});\n')
      outfile.write (f'ctx.lineTo({plot_width},{batv2_end_y});\n')
      outfile.write ('ctx.stroke();\n')             
   tidelen = len(tidelist)
   batvlen = len(batvlist)
   batv2len = len(batv2list)
   tidetimenext = 0
   batvtimenext = 0
   batv2timenext = 0
   savetime = 0
   savex = 0
   savey = 0
   savetime2 = 0
   savex2 = 0
   savey2 = 0
   savebatvtime = 0
   savebatvx = 0
   savebatvy = 0
   savebatv2time = 0
   savebatv2x = 0
   savebatv2y = 0

   for pidx, ent in enumerate(predlist):
      try:
         predtime = ent[0]
         predtime_hm = datetime.strptime(str(ent[0])[:16], mintimeformat)
         if pidx < len(predlist)-1:
            predtimenext = datetime.strptime(str(predlist[pidx+1][0])[:16], mintimeformat)
         thisDate = predtime.date()
         if thisDate != listDate:
            listDate = thisDate
            localsunrise = datetime.strftime(sun.riselocal(listDate),'%Y-%m-%d %H:%M')+':00'
            localsunset = datetime.strftime(sun.setlocal(listDate),'%Y-%m-%d %H:%M')+':00'
         predstate = ent[3]
         plottime = predtime.timestamp() - starttime.timestamp()
         tide_x = round((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
         hrmin = datetime.strftime(predtime, "%H:%M")
         linedate = datetime.strftime(predtime, "%d %b")
         if pidx == 0:
            predstartx = int(pstart+ent[1]*(plot_width-30)/86400/plotdays)
            predstarty = tide_end_y-int((ent[2]-math.floor(mintide))*tide_grid_y)
            predstarthx = predstartx
            predstarthy = predstarty
            predstartft = ent[2]
         predendx = int(pstart+ent[1]*(plot_width-30)/86400/plotdays)
         predendy = tide_end_y-int((ent[2]-math.floor(mintide))*tide_grid_y)
         predendft = ent[2]      
         if aidx < tidelen-1:
            tidetime = datetime.strptime(tidelist[aidx][0][:16], mintimeformat)
         if aidx+1 < tidelen-1:
            tidetimenext = datetime.strptime(tidelist[aidx+1][0][:16], mintimeformat)
         if bidx < batvlen-1:
            batvtime = datetime.strptime(batvlist[bidx][0][:16], mintimeformat)
         if bidx+1 < batvlen-1:
            batvtimenext = datetime.strptime(batvlist[bidx+1][0][:16], mintimeformat)
         if b2idx < batv2len-1:
            batv2time = datetime.strptime(batv2list[b2idx][0][:16], mintimeformat)
         if b2idx+1 < batv2len-1:
            batv2timenext = datetime.strptime(batv2list[b2idx+1][0][:16], mintimeformat)
         if tidesup:
            if tidetime == predtime_hm:
               if station1 and s1enable and tidelist[aidx][1] == 1 and tidelist[aidx][2] != None:
                  tide_y = tide_end_y-int(((station1cal-tidelist[aidx][2]/12) -math.floor(mintide))*tide_grid_y)
                  tideft = station1cal-tidelist[aidx][2]/12
                  varift = tideft-predendft
                  vari_y = vari_end_y-int((varift+2)*grid_height)
                  if savetime == 0 or tidetime > savetime + timedelta(minutes=15):               
                     #outfile.write ('ctx.fillStyle = "blue";\n')
                     #outfile.write (f'ctx.fillRect({tide_x},{tide_y},1,2);\n')
                     pass
                  else:
                     outfile.write (f'ctx.strokeStyle = "blue";\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({savex},{savey});\n')
                     outfile.write (f'ctx.lineTo({tide_x},{tide_y});\n')
                     outfile.write (f'ctx.stroke();\n')                                    
                  savetime = tidetime
                  savex = tide_x
                  savey = tide_y
                  if predstate == 'L' or predstate == 'H':
                     if prestate == '':
                        prestate = predstate
                     elif prestate != predstate:
                        prestate = predstate
                        if variinit:
                           outfile.write (f'ctx.strokeStyle = "blue";\n')
                           outfile.write (f'ctx.beginPath();\n')
                           outfile.write (f'ctx.moveTo({varistart_x},{varistart_y});\n')
                           outfile.write (f'ctx.lineTo({tide_x},{vari_y});\n')
                           outfile.write (f'ctx.stroke();\n')                                    
                           varistart_x = tide_x
                           varistart_y = vari_y
                        variinit = True
                        if varistart_x == -99: varistart_x = tide_x
                        if varistart_y == -99: varistart_y = vari_y
               if debugit:
                  print ('stationid: '+str(tidelist[aidx][1])
                  debugit -= 1                  
               if station2 and s2enable and tidelist[aidx][1] == 2 and tidelist[aidx][2] != None:
                  tide_y = tide_end_y-int(((station2cal-tidelist[aidx][2]/12)-math.floor(mintide))*tide_grid_y)
                  tideft = station2cal-tidelist[aidx][2]/12
                  varift = tideft-predendft
                  vari_y = vari2_end_y-int((varift+2)*grid_height)
                  if debugit > 0:
                     print ('savetime2: '+str(savtime2)+' tidetime: '+str(tidetime))
                     debugit -= 1
                  if savetime2 == 0 or tidetime > savetime2 + timedelta(minutes=15):               
                     outfile.write ('ctx.fillStyle = "darkgreen";\n')
                     outfile.write (f'ctx.fillRect({tide_x},{tide_y},1,2);\n')
                  else:
                     outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({savex2},{savey2});\n')
                     outfile.write (f'ctx.lineTo({tide_x},{tide_y});\n')
                     outfile.write (f'ctx.stroke();\n')                                    
                  savetime2 = tidetime
                  savex2 = tide_x
                  savey2 = tide_y
                  if predstate == 'L' or predstate == 'H':
                     if prestate2 == '':
                        prestate2 = predstate
                     elif prestate2 != predstate:
                        prestate2 = predstate
                        if vari2init:
                           outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
                           outfile.write (f'ctx.beginPath();\n')
                           outfile.write (f'ctx.moveTo({vari2start_x},{vari2start_y});\n')
                           outfile.write (f'ctx.lineTo({tide_x},{vari_y});\n')
                           outfile.write (f'ctx.stroke();\n')                                    
                           vari2start_x = tide_x
                           vari2start_y = vari_y
                        vari2init = True
                        if vari2start_x == -99: vari2start_x = tide_x
                        if vari2start_y == -99: vari2start_y = vari_y                                            
               aidx += 1
            else:
               while tidetimenext < predtimenext and aidx < tidelen-1:
                  aidx += 1
                  if aidx < tidelen-1:
                     tidetimenext = datetime.strptime(tidelist[aidx][0][:16], mintimeformat)

         if s1enable and batv and len(batvlist) != 0:
            if batvtime == predtime_hm:
               batv_y = batv_end_y-int((batvlist[bidx][1]-minbatv)*batv_y_fact)
               if savebatvtime == 0 or predtime_hm > savebatvtime + timedelta(minutes=15):               
                  #outfile.write ('ctx.fillStyle = "black";\n')
                  #outfile.write (f'ctx.fillRect({tide_x},{batv_y},1,2);\n')
                  pass
               else:
                  outfile.write (f'ctx.strokeStyle = "black";\n')
                  outfile.write (f'ctx.beginPath();\n')
                  outfile.write (f'ctx.moveTo({savebatvx},{savebatvy});\n')
                  outfile.write (f'ctx.lineTo({tide_x},{batv_y});\n')
                  outfile.write (f'ctx.stroke();\n')                                    
                  if str(predtime_hm) == localsunrise:
                     outfile.write (f'ctx.strokeStyle = "orange";\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx},{batv_end_y});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx-10},{batv_start_y+10});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx+10},{batv_start_y+10});\n')
                     outfile.write (f'ctx.stroke();\n')
                  elif str(predtime_hm) == localsunset:
                     outfile.write (f'ctx.strokeStyle = "orange";\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx},{batv_end_y});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv_end_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx-10},{batv_end_y-10});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv_end_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx+10},{batv_end_y-10});\n')
                     outfile.write (f'ctx.stroke();\n')
               savebatvtime = batvtime
               savebatvx = tide_x
               savebatvy = batv_y                  
               bidx += 1
            else:
               while batvtimenext < predtimenext and bidx < batvlen-1:
                  bidx += 1
                  if bidx < batvlen-1:
                     batvtimenext = datetime.strptime(batvlist[bidx][0][:16], mintimeformat)

         if s2enable and batv2 and len(batv2list) != 0:
            if batv2time == predtime_hm:
               batv2_y = batv2_end_y-int((batv2list[b2idx][1]-minbatv2)*batv2_y_fact)
               if savebatv2time == 0 or predtime_hm > savebatv2time + timedelta(minutes=15):               
                  #outfile.write ('ctx.fillStyle = "black";\n')
                  #outfile.write (f'ctx.fillRect({tide_x},{batv2_y},1,2);\n')
                  pass
               else:
                  outfile.write (f'ctx.strokeStyle = "black";\n')
                  outfile.write (f'ctx.beginPath();\n')
                  outfile.write (f'ctx.moveTo({savebatv2x},{savebatv2y});\n')
                  outfile.write (f'ctx.lineTo({tide_x},{batv2_y});\n')
                  outfile.write (f'ctx.stroke();\n')                                    
                  if str(predtime_hm) == localsunrise:
                     outfile.write (f'ctx.strokeStyle = "orange";\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv2_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx},{batv2_end_y});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv2_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx-10},{batv2_start_y+10});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv2_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx+10},{batv2_start_y+10});\n')
                     outfile.write (f'ctx.stroke();\n')
                  elif str(predtime_hm) == localsunset:
                     outfile.write (f'ctx.strokeStyle = "orange";\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv2_start_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx},{batv2_end_y});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv2_end_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx-10},{batv2_end_y-10});\n')
                     outfile.write (f'ctx.stroke();\n')
                     outfile.write (f'ctx.beginPath();\n')
                     outfile.write (f'ctx.moveTo({predstartx},{batv2_end_y});\n')
                     outfile.write (f'ctx.lineTo({predstartx+10},{batv2_end_y-10});\n')
                     outfile.write (f'ctx.stroke();\n')
               savebatv2time = batv2time
               savebatv2x = tide_x
               savebatv2y = batv2_y                  
               b2idx += 1
            else:
               while batv2timenext < predtimenext and b2idx < batv2len-1:
                  b2idx += 1
                  if b2idx < batv2len-1:
                     batv2timenext = datetime.strptime(batv2list[b2idx][0][:16], mintimeformat)

      except Exception as errmsg:
         pline = msgtime+' Error - '+str(errmsg)
         with open('/var/www/html/tideplot.log', 'a') as logfile:
            logfile.write (pline+'\n')
         continue            
      outfile.write ('ctx.fillStyle = "black";\n')
      if predtime.minute == 0 and predtime.hour  == 0:
         outfile.write ('ctx.strokeStyle = "gray";\n')
         outfile.write (f'ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({predstartx},{tide_start_y});\n')
         outfile.write (f'ctx.lineTo({predstartx},{tide_end_y});\n')
         outfile.write (f'ctx.stroke();\n')                                                                     
         outfile.write (f'ctx.beginPath();\n')
         if station1:
            outfile.write (f'ctx.moveTo({predstartx},{vari_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{vari_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
         if station2:
            outfile.write (f'ctx.moveTo({predstartx},{vari2_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{vari2_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
         if wind:
            outfile.write (f'ctx.beginPath();\n')
            outfile.write (f'ctx.moveTo({predstartx},{wind_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{wind_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
         if rain:
            outfile.write (f'ctx.beginPath();\n')
            outfile.write (f'ctx.moveTo({predstartx},{rain_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{rain_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
         if temp:
            outfile.write (f'ctx.beginPath();\n')
            outfile.write (f'ctx.moveTo({predstartx},{temp_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{temp_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
         if s1enable and batv:
            outfile.write (f'ctx.beginPath();\n')
            outfile.write (f'ctx.moveTo({predstartx},{batv_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{batv_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
         if s2enable and batv2:
            outfile.write (f'ctx.beginPath();\n')
            outfile.write (f'ctx.moveTo({predstartx},{batv2_start_y});\n')
            outfile.write (f'ctx.lineTo({predstartx},{batv2_end_y});\n')
            outfile.write (f'ctx.stroke();\n')
      if predtime.minute == 0 and predtime.hour == 12:
         outfile.write (f'ctx.fillText("{linedate}", {predstartx}, {dtime_start_y+17});\n')                          
         outfile.write (f'ctx.fillText("{linedate}", {predstartx}, {canvas_height-5});\n')                          
      if pidx % 10 == 0:
         outfile.write (f'ctx.strokeStyle = "gray";\n')
         outfile.write (f'ctx.beginPath();\n')
         outfile.write (f'ctx.moveTo({predstarthx},{predstarthy});\n')
         outfile.write (f'ctx.lineTo({predendx},{predendy});\n')
         outfile.write (f'ctx.stroke();\n')
         predstarthx = predendx
         predstarthy = predendy         
      predstartx = predendx
      predstarty = predendy
      predstartft = predendft                  
      if (wind or rain or temp) and wxsup and widx < wxlength-1:
         try:
         #if True:
            wxtime = datetime.strptime(wxlist[widx][0][:16], mintimeformat)
            nextwxtime = datetime.strptime(wxlist[widx+1][0][:16], mintimeformat)
            while widx < wxlength-1 and wxtime < predtime_hm:
               widx += 1
               wxtime = datetime.strptime(wxlist[widx][0][:16], mintimeformat)
               nextwxtime = datetime.strptime(wxlist[widx+1][0][:16], mintimeformat)
            if wxtime == predtime_hm:
               if wind and wxinit:
                  if wxlist[widx][4] != '' and wxlist[widx][4] is not None:
                     wxendx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
                     wxendy = wind_end_y-int(wxlist[widx][4]*grid_height/10)
                     windlist.append(wxendy)
                     if wxlist[widx][4] > maxwind:
                        maxwind = wxlist[widx][4]
                        maxwdir = wxlist[widx][5]
                     windcount += 1
                     if windcount == 5:
                        wxendy = sum(windlist)/len(windlist)
                        outfile.write (f'ctx.strokeStyle = "purple";\n')
                        outfile.write (f'ctx.beginPath();\n')
                        outfile.write (f'ctx.moveTo({wxstartx},{wxstarty});\n')
                        outfile.write (f'ctx.lineTo({wxendx},{wxendy});\n')
                        outfile.write (f'ctx.stroke();\n')
                        wxstartx = wxendx
                        wxstarty = wxendy
                        windcount = 0
                        windlist = []
                        if wxendx > windex+10 and maxwind > 2:
                           windex = wxendx
                           winddir = maxwdir
                           windrad = winddir * (math.pi/180)
                           windcos = math.cos(windrad)
                           windsin = math.sin(windrad)
                           newarrow = []
                           for point in windarrow:
                              x = point[0]
                              y = point[1]
                              newarrow.append([int(x*windcos-y*windsin+wxendx),int(x*windsin+y*windcos+wxendy-75)])
                           outfile.write (f'ctx.strokeStyle = "purple";\n')
                           outfile.write (f'ctx.beginPath();\n')
                           outfile.write (f'ctx.moveTo({newarrow[0][0]},{newarrow[0][1]});\n')
                           outfile.write (f'ctx.lineTo({newarrow[1][0]},{newarrow[1][1]});\n')
                           outfile.write (f'ctx.stroke();\n')
                           outfile.write (f'ctx.beginPath();\n')
                           outfile.write (f'ctx.moveTo({newarrow[0][0]},{newarrow[0][1]});\n')
                           outfile.write (f'ctx.lineTo({newarrow[2][0]},{newarrow[2][1]});\n')
                           outfile.write (f'ctx.stroke();\n')
                           outfile.write (f'ctx.beginPath();\n')
                           outfile.write (f'ctx.moveTo({newarrow[0][0]},{newarrow[0][1]});\n')
                           outfile.write (f'ctx.lineTo({newarrow[3][0]},{newarrow[3][1]});\n')
                           outfile.write (f'ctx.stroke();\n')
                        maxwdir = 0
                        maxwind = 0
               elif wind:
                  if wxlist[widx][4] != '' and wxlist[widx][4] is not None:
                     wxstartx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
                     wxstarty = wind_end_y-int(wxlist[widx][4]*grid_height/10)
                     windlist.append(wxstarty)
                     windcount += 1
                     if windcount == 5:
                        wxstarty = sum(windlist)/len(windlist)
                        windlist = []
                        windcount = 0
                        wxinit = True
               if rain and rxinit:
                  if wxlist[widx][10] != '' and wxlist[widx][10] is not None:
                     rxendx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
                     rxendy = rain_end_y-int(wxlist[widx][10]*2*grid_height)
                     if widx % 10 == 0:
                        outfile.write (f'ctx.strokeStyle = "black";\n')
                        outfile.write (f'ctx.beginPath();\n')
                        outfile.write (f'ctx.moveTo({rxstarthx},{rxstarthy});\n')
                        outfile.write (f'ctx.lineTo({rxendx},{rxendy});\n')
                        outfile.write (f'ctx.stroke();\n')
                        rxstarthx = rxendx
                        rxstarthy = rxendy
                     rxstartx = rxendx
                     rxstarty = rxendy          
               elif rain:
                  if wxlist[widx][10] != '' and wxlist[widx][10] is not None:
                     rxstartx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
                     rxstarty = rain_end_y-int(wxlist[widx][10]*2*grid_height)
                     rxstarthx = rxstartx
                     rxstarthy = rxstarty
                     rxinit = True
               if temp and txinit:
                  if wxlist[widx][1] != '' and wxlist[widx][1] is not None:
                     txendx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
                     txendy = temp_end_y-int((wxlist[widx][1])*grid_height/10)
                     if widx % 10 == 0:
                        outfile.write (f'ctx.strokeStyle = "red";\n')
                        outfile.write (f'ctx.beginPath();\n')
                        outfile.write (f'ctx.moveTo({txstarthx},{txstarthy});\n')
                        outfile.write (f'ctx.lineTo({txendx},{txendy});\n')
                        outfile.write (f'ctx.stroke();\n')
                        txstarthx = txendx
                        txstarthy = txendy
                     txstartx = txendx
                     txstarty = txendy          
               elif temp:
                  if wxlist[widx][1] != '' and wxlist[widx][1] is not None:
                     txstartx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
                     txstarty = temp_end_y-int((wxlist[widx][1])*grid_height/10)
                     txstarthx = txstartx
                     txstarthy = txstarty
                     txinit = True
               widx += 1
            checktime = wxtime+timedelta(minutes=10)
            if nextwxtime > checktime:
               wxinit = False
               rxinit = False
               txinit = False
         #else:               
         except Exception as errmsg:
            pline = '\n'+msgtime+' Error: '+str(errmsg)
            with open('/var/www/html/tideplot.log', 'a') as logfile:
               logfile.write (pline+'\n')   
            
   outfile.write (f'ctx.strokeStyle = "black";\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({x_start},{tide_start_y});\n')
   outfile.write (f'ctx.lineTo({x_start},{tide_end_y});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write (f'ctx.moveTo({plot_width-1},{tide_start_y});\n')
   outfile.write (f'ctx.lineTo({plot_width-1},{tide_end_y});\n')
   outfile.write (f'ctx.stroke();\n')
#
#   Create Actual High and Low tide annotation
#
   midcanvas = tide_start_y+tide_height/2
   if tags and tidesup:
      outfile.write (f'ctx.textAlign = "center";\n')
      outfile.write (f'ctx.strokeStyle = "blue";\n')
      for pidx, ent in enumerate(tidelist):
         try:
            tidetime = datetime.strptime(ent[0], sqltimeformat)
            hrmin = datetime.strftime(tidetime, "%H:%M")
            linedate = datetime.strftime(tidetime, "%d %b")
            plottime = tidetime.timestamp() - starttime.timestamp()
            startx = int((plottime+offtime)*(plot_width-30)/86400/plotdays+30)
            hourtime = tidetime.hour
            if s1enable and station1 and ent[1] == 1 and ent[2] != None:
               tidestate = str(ent[1]) # temporary until front end processing implemented
               if tidestate == 'low' or tidestate == 'high':
                  if turntime == '' or abs(hourtime-turntime) >= 3:
                     turntime = hourtime
                     peak = format(ent[2],'.1f')
                     peaks = peak+' '+hrmin
                     outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                     outfile.write (f'ctx.strokeRect({startx-21}, {tag_y-19}, 42, 30);\n')
                     outfile.write (f'ctx.fillRect({startx-21}, {tag_y-19}, 42, 30);\n')
                     outfile.write (f'ctx.fillStyle = "blue";\n')
                     outfile.write (f'ctx.fillText("{hrmin}", {startx}, {tag_y+9});\n')
                     outfile.write (f'ctx.fillText("{peak}", {startx}, {tag_y-6});\n')
            if s2enable and station2 and ent[1] == 2 and ent[2] != None:
               tidestate = str(ent[1]) # temporary until front end processing implemented
               if tidestate == 'low' or tidestate == 'high':
                  if turntime2 == '' or abs(hourtime-turntime2) >= 3:
                     turntime2 = hourtime
                     peak = format(ent[3],'.1f')
                     peaks = peak+' '+hrmin
                     outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                     outfile.write (f'ctx.strokeRect({startx-21}, {tag_y-51}, 42, 30);\n')
                     outfile.write (f'ctx.fillRect({startx-21}, {tag_y-51}, 42, 30);\n')
                     outfile.write (f'ctx.fillStyle = "green";\n')
                     outfile.write (f'ctx.fillText("{hrmin}", {startx}, {tag_y-23});\n')
                     outfile.write (f'ctx.fillText("{peak}", {startx}, {tag_y-38});\n')
         except Exception as errmsg:
            pline = msgtime+' Error - '+str(errmsg)
            with open('/var/www/html/tideplot.log', 'a') as logfile:
               logfile.write (pline+'\n')
#
# Create Dashed vertical lines and if tags also create Predicted High and Low Tide Annotation
#
   prestate = ''
   for pidx, ent in enumerate(predlist):
      if pidx == 0:
         startx = pstart+ent[1]*(plot_width-30)/86400/plotdays
         #starty = tide_end_y-int((ent[2]+2)*grid_height)
         prestate = ent[3]
         continue
      predstate = ent[3]
      predtime = ent[0]
      hrmin = datetime.strftime(predtime, "%H:%M")
      linedate = datetime.strftime(predtime, "%d %b")

      endx = int(pstart+ent[1]*(plot_width-30)/86400/plotdays)
      #endy = tide_end_y-int((ent[2]-mintide)*grid_height)
      if predstate == 'L' or predstate == 'H':
         peak = format(ent[2],'.1f')
         peaks = peak+' '+hrmin
         if prestate == '':
            prestate = predstate
         elif prestate != predstate:
            dash_size = 7
            dash_end_y = tide_start_y
            outfile.write (f'ctx.strokeStyle = "gray";\n')
            while dash_end_y < tide_end_y:
               outfile.write (f'ctx.beginPath();\n')
               outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
               if dash_end_y+dash_size > tide_end_y:
                  outfile.write (f'ctx.lineTo({endx},{tide_end_y});\n')
               else:
                  outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
               outfile.write (f'ctx.stroke();\n')
               dash_end_y += dash_size*2
            if s1enable and station1:
               dash_end_y = vari_start_y
               while dash_end_y < vari_end_y:
                  outfile.write (f'ctx.beginPath();\n')
                  outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                  if dash_end_y+dash_size > vari_end_y:
                     outfile.write (f'ctx.lineTo({endx},{vari_end_y});\n')
                  else:
                     outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
                  outfile.write (f'ctx.stroke();\n')
                  dash_end_y += dash_size*2
            if s2enable and station2:
               dash_end_y = vari2_start_y
               while dash_end_y < vari2_end_y:
                  outfile.write (f'ctx.beginPath();\n')
                  outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                  if dash_end_y+dash_size > vari2_end_y:
                     outfile.write (f'ctx.lineTo({endx},{vari2_end_y});\n')
                  else:
                     outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
                  outfile.write (f'ctx.stroke();\n')
                  dash_end_y += dash_size*2
            prestate = predstate
            if tags:                  
               outfile.write (f'ctx.fillStyle = "#ffffff";\n')
               outfile.write (f'ctx.strokeRect({startx-21}, {tag_y+13}, 42, 30);\n')
               outfile.write (f'ctx.fillRect({startx-21}, {tag_y+13}, 42, 30);\n')
               outfile.write (f'ctx.fillStyle = "gray";\n')
               outfile.write (f'ctx.fillText("{peak}", {startx}, {tag_y+27});\n')
               outfile.write (f'ctx.fillText("{hrmin}", {startx}, {tag_y+42});\n')
         startx = endx
         #starty = endy
   outfile.write (f'ctx.strokeStyle = "blue";\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({plot_width/4-60},{tide_start_y-10});\n')
   outfile.write (f'ctx.lineTo({plot_width/4-30},{tide_start_y-10});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({plot_width/4+30},{tide_start_y-10});\n')
   outfile.write (f'ctx.lineTo({plot_width/4+60},{tide_start_y-10});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({plot_width/4*2-60},{tide_start_y-10});\n')
   outfile.write (f'ctx.lineTo({plot_width/4*2-30},{tide_start_y-10});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({plot_width/4*2+30},{tide_start_y-10});\n')
   outfile.write (f'ctx.lineTo({plot_width/4*2+60},{tide_start_y-10});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write (f'ctx.strokeStyle = "gray";\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({plot_width/4*3-70},{tide_start_y-10});\n')
   outfile.write (f'ctx.lineTo({plot_width/4*3-40},{tide_start_y-10});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write (f'ctx.beginPath();\n')
   outfile.write (f'ctx.moveTo({plot_width/4*3+40},{tide_start_y-10});\n')
   outfile.write (f'ctx.lineTo({plot_width/4*3+70},{tide_start_y-10});\n')
   outfile.write (f'ctx.stroke();\n')
   outfile.write ('ctx.textAlign = "center";\n')
   outfile.write ('ctx.font = "14px Arial";\n')
   outfile.write ('ctx.fillStyle = "blue";\n')
   outfile.write (f'ctx.fillText("Station 1", {plot_width/4}, {tide_start_y-4});\n')
   outfile.write ('ctx.fillStyle = "darkgreen";\n')
   outfile.write (f'ctx.fillText("Station 2", {plot_width/4*2}, {tide_start_y-4});\n')
   if not tidesup and banflag == '1':
      outfile.write ('ctx.fillStyle = "black";\n')
      outfile.write (f'ctx.fillText("{banner}", {plot_width/2}, {tide_end_y-10});\n')      
   outfile.write ('ctx.fillStyle = "gray";\n')
   outfile.write (f'ctx.fillText("Predicted", {plot_width/4*3}, {tide_start_y-4});\n')
   if s1enable and station1:
      outfile.write ('ctx.fillStyle = "blue";\n')
      outfile.write (f'ctx.fillText("Variance between Station 1 and predicted high and low tide in feet", {plot_width/2}, {vari_start_y-4});\n')
   if s2enable and station2:
      outfile.write ('ctx.fillStyle = "darkgreen";\n')
      outfile.write (f'ctx.fillText("Variance between Station 2 and predicted high and low tide in feet", {plot_width/2}, {vari2_start_y-4});\n')
   if wind:   
      outfile.write ('ctx.fillStyle = "purple";\n')
      outfile.write (f'ctx.fillText("Wind speed and direction (mph)", {plot_width/2}, {wind_start_y-4});\n')
   if rain:      
      outfile.write ('ctx.fillStyle = "black";\n')
      outfile.write (f'ctx.fillText("Daily rainfall in inches", {plot_width/2}, {rain_start_y-4});\n')                          
   if temp:      
      outfile.write ('ctx.fillStyle = "red";\n')
      outfile.write (f'ctx.fillText("Temperature in degrees F", {plot_width/2}, {temp_start_y-4});\n')                          
   if s1enable and batv:      
      outfile.write ('ctx.fillStyle = "black";\n')
      outfile.write (f'ctx.fillText("Station 1 Sensor Battery Voltage", {plot_width/2}, {batv_start_y-4});\n')                          
   if s2enable and batv2:      
      outfile.write (f'ctx.fillText("Station 2 Sensor Battery Voltage", {plot_width/2}, {batv2_start_y-4});\n')                          
   outfile.write ('</script>\n')
   outfile.write ('</div>\n')
   outfile.write ('</body>\n')
   outfile.write ('</html>\n')
   outfile.close()
   os.system(f'mv {filetag} /var/www/html/tideplot.html')
proc_data()
