#!/home/tide/.tidenv/bin/python3
# -*- coding: utf-8 -*-
#
# Renders the historical tide/weather/wind/battery plot page.
#
# Runs in two contexts from this single file:
#  - As a CGI script (invoked by Apache, REQUEST_METHOD set in the environment):
#    reads request parameters via cgi.FieldStorage() and writes the response
#    directly to stdout. Reached both for the initial default view and for
#    every custom redraw submitted via the page's own form.
#  - As a cron job (no REQUEST_METHOD; currently scheduled at :01/:21/:41,
#    one minute after tide.py refreshes the database copy): always renders
#    the default (DEFAULT_STATION_ID-driven) view and publishes it to
#    /var/www/html/tideplot.html as a static page.
#
# This replaces the former separate tideplot.py / tideplot.cgi files, which
# had drifted into two independently-maintained copies of the same logic.
import time
import sys
import os
from datetime import datetime, date, timedelta, timezone
import sqlite3
import math
import cgi, cgitb
from dotenv import load_dotenv, find_dotenv
from suntimes import SunTimes

#
# Function to generate the predicted tide at one minute intervals. The predicted tide
# levels are saved in [predlist] for the requested plot duration based on the NOAA tide tables.
#


class TidePlotRenderer:
    """Renders the historical tide/weather/wind/battery plot page, either
    as a CGI response (stdout) or a published static page (cron/file mode).
    See run() for the overall sequence."""

    # True constants: the same value on every render, for every site,
    # regardless of request parameters or configuration. Promoted out of
    # per-instance state (where they originally lived only because the
    # blanket global->self conversion couldn't tell them apart from
    # genuinely per-render state -- see banflag/banner note below).
    halftide = math.pi / 2
    fulltide = math.pi
    grid_height = 30
    left_scale_x = 15
    mintimeformat = "%Y-%m-%d %H:%M"
    sqltimeformat = "%Y-%m-%d %H:%M:%S"
    sam_int = 60
    selectedtide = 'predicts'
    title_height = 10
    dtime_start_y = 0
    windarrow = [[0, 8], [0, -8], [-3, 3], [3, 3]]  # read-only (iterated, never mutated)
    # banflag/banner: originally sourced from the sqlite3 iparams table
    # elsewhere in the site, but hardcoded disabled here -- the banner
    # feature was judged not applicable to the plot display. Fixed values,
    # not per-render state.
    banflag = 0
    banner = ''

    def __init__(self, is_cgi_request):
        self.is_cgi_request = is_cgi_request

    def tide_predict(self):

           startproc = False
           tidesecs = 0
           self.predlist = []
           self.predicts = []
           self.maxpred = -99
           self.minpred = 99
        #
        # The start time for the tide prediction is the current time minus 24 hours.
        #
           #curtime = datetime.now()
           maketime = self.curtime - timedelta(days=self.plotdays)
           then = maketime - timedelta(hours=8)
           currentday = datetime.strftime(self.curtime, "%d")
        #
        # Select the entries from the appropriate noaa tides table with
        # time tags that are greater than the start time - 8 hours
        #
           trytide = 0
           while len(self.predicts) == 0:
              self.sqlcur.execute(f"select * from {self.selectedtide} where dtime >= ? order by dtime", (str(then),))
              self.predicts = self.sqlcur.fetchall()
              if len(self.predicts) == 0:
                 trytide += 1
                 if trytide >= 3:
                    with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                       self.logfile.write (self.msgtime+' tideplot: predicted tide unavailable\n')
                    return self.predicts
           lastime = ''
           for line in self.predicts:
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
                 radinc = self.fulltide/deltadiff
        #
        # On restart, the starting radians are set depending on whether
        # this iteration is from low to high tide or vice versa.
        #
                 if restart:
                    if lasttide < thistide:
                       radians = self.halftide*3
                    else:
                       radians = self.halftide      
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
                 self.tidelevel = math.sin(radians)*tidediff/2+(tidediff/2)+tideoff
        #
        # The first entry in the predlist is for the current time - 24 hours.
        # The remainder of the list contains predictions for the next 48 hours.
        #
                 while simtime < thisto and tidesecs < 86400*self.plotdays:
                    self.predlist.append([simtime,tidesecs,self.tidelevel,thistate])
                    simtime = simtime+timedelta(seconds=self.sam_int)
                    radians = radians+self.sam_int*radinc
                    radians = radians % (math.pi*2)   
                    self.tidelevel = math.sin(radians)*tidediff/2+(tidediff/2)+tideoff
                    tidesecs += self.sam_int
              if tidesecs >= 86400*self.plotdays:
                 break
              restart = True
              lastime = thisto
              lasttide = thistide
              lastdelta = delta
           predsum = 0
           if len(self.predlist) != 0:
              for chkent in self.predlist:
                 if chkent[2] > self.maxpred:
                    self.maxpred = chkent[2]
                 if chkent[2] < self.minpred:
                    self.minpred = chkent[2]
           return


    def _get_epochs(self, tide_list):
           trend1 = ''
           trend2 = ''
           epochs = []
           tide_average1 = [0 for x in range(0,15)]
           last_average1 = 0
           max_tide1 = -99
           min_tide1 = 99
           tide_average2 = [0 for x in range(0,15)]
           last_average2 = 0
           max_tide2 = -99
           min_tide2 = 99
           new_tide_list = []
           index1 = 0
           index2 = 0
           min_tide_time1 = ''
           min_tide_time2 = ''
           max_tide_time1 = ''
           max_tide_time2 = ''

           for entry in tide_list:
              new_tide_list.append([entry[0], entry[1], entry[2], ''])
              if entry[1] == 1:
                 if entry[2] > max_tide1:
                    max_tide1 = entry[2]
                    max_tide_time1 = entry[0]
                 if entry[2] < min_tide1:
                    min_tide1 = entry[2]
                    min_tide_time1 = entry[0]
                 tide_average1 = tide_average1[1:]+[entry[2]]
                 index1 += 1
              elif entry[1] == 2:
                 if entry[2] > max_tide2:
                    max_tide2 = entry[2]
                    max_tide_time2 = entry[0]
                 if entry[2] < min_tide2:
                    min_tide2 = entry[2]
                    min_tide_time2 = entry[0]
                 tide_average2 = tide_average2[1:]+[entry[2]]
                 index2 += 1
              if index1 != 0 and index1 % 15 == 0 and entry[1] == 1:
                 average1 = sum(tide_average1)/len(tide_average1)
                 if last_average1 == 0:
                    last_average1 = average1
                    continue
                 if average1 > last_average1 + 0.05:
                    if trend1 == 'low':
                       epochs.append([min_tide_time1,1,trend1])
                       min_tide1 = 99
                       max_tide1 = -99                        
                    trend1 = 'high'
                 elif average1 < last_average1 - 0.05:
                    if trend1 == 'high':
                       epochs.append([max_tide_time1,1,trend1])
                       min_tide1 = 99
                       max_tide1 = -99                            
                    trend1 = 'low'
                 last_average1 = average1

              elif index2 != 0 and index2 % 15 == 0 and entry[1] == 2:
                 average2 = sum(tide_average2)/len(tide_average2)
                 if last_average2 == 0:
                    last_average2 = average2
                    continue
                 if average2 > last_average2 + 0.05:
                    if trend2 == 'low':
                       epochs.append([min_tide_time2,2,trend2])
                       min_tide2 = 99
                       max_tide2 = -99                        
                    trend2 = 'high'
                 elif average2 < last_average2 - 0.05:
                    if trend2 == 'high':
                       epochs.append([max_tide_time2,2,trend2])
                       min_tide2 = 99
                       max_tide2 = -99                            
                    trend2 = 'low'
                 last_average2 = average2

           for index, entry in enumerate(new_tide_list):
              for epoch_entry in epochs:
                 if entry[0] == epoch_entry[0] and entry[1] == epoch_entry[1]:
                    new_tide_list[index][3] = epoch_entry[2]
           return new_tide_list


    def proc_data(self):
           canw_str = str(self.canvas_width)
           bored = 25
           currenttime = datetime.now()
           hrtime = datetime.strftime(currenttime, "%H:%M")
           self.outfile.write ("Content-type:text/html\r\n\r\n\r\n")
           self.outfile.write ('<html>\n')
           self.outfile.write ('<head>\n')
           self.outfile.write (f'<title>{self.station_location} Tide and Weather</title>\n')
           self.outfile.write ('<style type="text/css" media="screen">\n')
           self.outfile.write ('*{\n')
           self.outfile.write ('margin: 0px 0px 0px 0px;\n')
           self.outfile.write ('padding: 0px 0px 0px 0px;\n')
           self.outfile.write ('}\n') 
           self.outfile.write ('canvas {\n')
           self.outfile.write ('padding-left: 0;\n')
           self.outfile.write ('padding-right: 0;\n')
           self.outfile.write ('margin-left: auto;\n')
           self.outfile.write ('margin-right: auto;\n')
           self.outfile.write ('display: block;\n')
           self.outfile.write (f'width: {canw_str}px;\n')
           self.outfile.write ('}\n')
           self.outfile.write ('div {\n')
           self.outfile.write ('padding-left: 0;\n')
           self.outfile.write ('padding-right: 0;\n')
           self.outfile.write ('margin-left: auto;\n')
           self.outfile.write ('margin-right: auto;\n')
           self.outfile.write ('display: block;\n')
           self.outfile.write (f'width: {canw_str}px;\n')
           self.outfile.write ('}\n')
           self.outfile.write ('body, html {\n')
           self.outfile.write ('padding: 3px 3px 3px 3px;\n')
           self.outfile.write ('background-color: black;\n')
           self.outfile.write ('font-family: Verdana, sans-serif;\n')
           self.outfile.write ('font-size: 12pt;\n')
           self.outfile.write ('text-align: center;\n')
           self.outfile.write ('}\n')
           self.outfile.write ('</style>\n')
           self.outfile.write ('</head>\n')
           self.outfile.write ('<body style="background-color:black;">\n')
           self.outfile.write (f'<div style="background-color: #E0F8F1; width: {self.canvas_width}px; text-align: center; margin-left: auto; margin-right: auto;">\n') 
           self.outfile.write (f'{self.station_location}<br>')  
           self.outfile.write (f'<form style="background-color: #E0F8F1; width: {self.canvas_width}px; text-align: center; margin-left: auto; margin-right: auto;" id="myForm" action="/cgi-bin/tideplot.cgi" method="post">\n') 
           self.outfile.write ('<label for="endate">End date:</label>\n')
           self.outfile.write (f'<input type="date" name="endate" id="endate" value="{self.formdate}">&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="dayspan">Plot span in days:</label>\n')
           self.outfile.write (f'<input type="number" name="dayspan" id="dayspan" value="{str(self.plotdays)}" step=1 min="1" max="30" required>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<input type="hidden" name="screenwidth" id="screenwidth" value=''/>\n')
           self.outfile.write ('<input type="hidden" name="screenheight" id="screenheight" value=''/>\n')
           if self.s1enable:
              self.outfile.write ('<label for="station1">Sensor 1</label>\n')
              self.outfile.write (f'<input type="checkbox" id="station1" name="station1" value="1" {self.station1chk}>&nbsp&nbsp&nbsp&nbsp\n')
           if self.s2enable:
              self.outfile.write ('<label for="station2">Sensor 2</label>\n')
              self.outfile.write (f'<input type="checkbox" id="station2" name="station2" value="0" {self.station2chk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="tags">Tide Markers</label>\n')
           self.outfile.write (f'<input type="checkbox" id="tags" name="tags" value="1" {self.tagchk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="wind"> Wind</label>\n')
           self.outfile.write (f'<input type="checkbox" id="wind" name="wind" value="1" {self.windchk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="rain">Rain</label>\n')
           self.outfile.write (f'<input type="checkbox" id="rain" name="rain" value="1" {self.rainchk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="temp">Temperature</label>\n')
           self.outfile.write (f'<input type="checkbox" id="temp" name="temp" value="1" {self.tempchk}>&nbsp&nbsp&nbsp&nbsp\n')
           if self.s1enable:
              self.outfile.write ('<label for="batv">BatV 1</label>\n')
              self.outfile.write (f'<input type="checkbox" id="batv" name="batv" value="1" {self.batvchk}>&nbsp&nbsp&nbsp&nbsp\n')
           if self.s2enable:
              self.outfile.write ('<label for="batv2">BatV 2</label>\n')
              self.outfile.write (f'<input type="checkbox" id="batv2" name="batv2" value="0" {self.batv2chk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<input type="submit" value="Refresh"/>\n')
           self.outfile.write ('</form>\n')
           self.outfile.write ('</div>')
           self.outfile.write ('<script>\n')
           self.outfile.write ('var w = window.innerWidth;\n')
           self.outfile.write ('var h = window.innerHeight;\n')
           self.outfile.write ('document.getElementById("screenwidth").value=w;\n')
           self.outfile.write ('document.getElementById("screenheight").value=h;\n')
           self.outfile.write ('</script>\n')     
           self.outfile.write ('<div>\n')
           #outfile.write (f'<canvas id="tideplot" width={canvas_width} height={canvas_height}\n')
           self.outfile.write (f'<canvas id="tideplot" width={self.canvas_width} height={self.canvas_height}\n')
           self.outfile.write ('style="text-align: center; border:2px solid white; background-color: #E0F8F1">\n')
           self.outfile.write ('</canvas>\n')
           self.outfile.write ('<script>\n')
           self.outfile.write ('var canvas = document.getElementById("tideplot");\n')
           self.outfile.write ('var ctx = canvas.getContext("2d");\n')
           self.outfile.write ('ctx.fillStyle = "#1932E1";\n')
           self.outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
           self.outfile.write ('ctx.textAlign = "left";\n')  
           self.outfile.write ('ctx.strokeStyle = "black";\n')
           if len(self.tidelist) == 0:
              with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                 self.logfile.write ('tidelist length is zero - exiting\n')
              self.outfile.write ('ctx.textAlign = "center";\n')  
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write ('ctx.font = "48px Arial";\n')
              self.outfile.write (f'ctx.fillText("No Data Available for Requested Time Span", {int(self.canvas_width/2)}, {int(self.canvas_height/2)});\n')
              self.outfile.write ('</script>\n')
              self.outfile.write ('</div>\n')
              self.outfile.write ('</body>\n')
              self.outfile.write ('</html>\n')
              exit()
           wxlist = []
           self.msgtime = str(self.curtime)[:-10]
           curhour = datetime.now().hour
           curminute = datetime.now().minute
           curhrmin = datetime.strftime(self.curtime, "%H:%M")
           self.sqlcur.execute("select * from wxdata where dtime "+ \
                          "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
           wxlist = self.sqlcur.fetchall()
           self.wxlength = len(wxlist)
           #if debugit >= 0:
           #   pline = msgtime+' '+str(wxlist)
           #   with open('/var/www/html/tideplot.log', 'a') as logfile:
           #      logfile.write (pline+'\n')   
           #   debugit -= 1if self.tidesup:
              starttime = datetime.strptime(self.tidelist[0][0], self.sqltimeformat)
           else:
              starttime = self.dbquerytime
           offtime = starttime.timestamp() - self.dbquerytime.timestamp()
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
           self.outfile.write ('ctx.lineWidth = 1;\n')
           self.outfile.write ('ctx.fillStyle = "black";\n')
           self.outfile.write ('ctx.font = "12px Arial";\n')
           self.outfile.write ('ctx.globalCompositeOperation = "source-over";\n')
           x_start = 30
           gridx = self.plot_width
           gridy = self.tide_end_y
           for x in range(0,self.tide_grid_nbr+1):
              if x == 0 or x == self.tide_grid_nbr:
                 self.outfile.write ('ctx.strokeStyle = "black";\n')
              else:
                 self.outfile.write ('ctx.strokeStyle = "gray";\n')
              linbr = str(x+int(math.floor(self.mintide)))
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{int(gridy)});\n')
              self.outfile.write (f'ctx.lineTo({gridx},{int(gridy)});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write (f'ctx.fillText("{linbr}", {self.left_scale_x}, {int(gridy)});\n')
              self.outfile.write (f'ctx.fillText("{linbr}", {self.right_scale_x}, {int(gridy)});\n')
              gridy = gridy-self.grid_height
           if self.station1 and self.s1enable:
              self.outfile.write ('ctx.strokeStyle = "black";\n')   
              self.outfile.write ('ctx.textAlign = "center";\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.vari_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.vari_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width-1},{self.vari_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width-1},{self.vari_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              gridy = 0
              for x in range(0,self.vari_grid_nbr+1):
                 if x == 0 or x == 2 or x == self.vari_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.vari_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.vari_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText("{str(2-x)}", {self.left_scale_x}, {int(self.vari_start_y+gridy)});\n')                          
                 self.outfile.write (f'ctx.fillText("{str(2-x)}", {self.right_scale_x}, {int(self.vari_start_y+gridy)});\n')                          
                 gridy += self.grid_height
           if self.station2 and self.s2enable:
              self.outfile.write ('ctx.strokeStyle = "black";\n')   
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.vari2_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.vari2_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width-1},{self.vari2_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width-1},{self.vari2_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              gridy = 0   
              for x in range(0,self.vari_grid_nbr+1):
                 if x == 0 or x == 2 or x == self.vari_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.vari2_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.vari2_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText("{str(2-x)}", {self.left_scale_x}, {int(self.vari2_start_y+gridy+3)});\n')                          
                 self.outfile.write (f'ctx.fillText("{str(2-x)}", {self.right_scale_x}, {int(self.vari2_start_y+gridy+3)});\n')                          
                 gridy += self.grid_height
           if self.wind:
              gridy = 0
              for x in range(0,self.windir_grid_nbr+self.wind_grid_nbr+1):
                 if x == 0 or x == self.windir_grid_nbr+self.wind_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')

                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.windir_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.windir_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 if x == 0:
                    gridy += self.wind_grid_y*5
                    continue
                 self.outfile.write (f'ctx.fillText("{str(((self.wind_grid_nbr-x)+1)*5)}", {self.left_scale_x}, {int(self.windir_start_y+gridy+6)});\n')                          
                 self.outfile.write (f'ctx.fillText("{str(((self.wind_grid_nbr-x)+1)*5)}", {self.right_scale_x}, {int(self.windir_start_y+gridy+6)});\n')                          
                 gridy += self.wind_grid_y*5
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.windir_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.wind_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width},{self.windir_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width},{self.wind_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')                           
           if self.rain:
              gridy = 0
              for x in range(0,self.rain_grid_nbr+1):
                 if x == 0 or x == self.rain_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.rain_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.rain_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText("{str((self.rain_grid_nbr-x)/2)}", {self.left_scale_x}, {int(self.rain_start_y+gridy)});\n')                          
                 self.outfile.write (f'ctx.fillText("{str((self.rain_grid_nbr-x)/2)}", {self.right_scale_x}, {int(self.rain_start_y+gridy)});\n')                          
                 gridy += self.rain_grid_y         
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.rain_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.rain_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width},{self.rain_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width},{self.rain_end_y});\n')
              self.outfile.write ('ctx.stroke();\n') 
           if self.temp:
              gridy = 0
              for x in range(0,self.temp_grid_nbr+1):
                 if x == 0 or x == self.temp_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.temp_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.temp_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText("{str((self.temp_grid_nbr-x)*5+(round(self.mintemp/5)*5))}", {self.left_scale_x}, {int(self.temp_start_y+gridy+5)});\n')                          
                 self.outfile.write (f'ctx.fillText("{str((self.temp_grid_nbr-x)*5+(round(self.mintemp/5)*5))}", {self.right_scale_x}, {int(self.temp_start_y+gridy+5)});\n')                          
                 gridy += self.temp_grid_y         
                 #outfile.write (f'ctx.fillText("{str((temp_grid_nbr-x)*10)}", {left_scale_x},
                 #{int(temp_start_y+gridy+5)});\n')                          
                 # outfile.write (f'ctx.fillText("{str((temp_grid_nbr-x)*10)}", {right_scale_x},    #{int(temp_start_y+gridy+5)});\n')                          
                 #gridy += temp_grid_y         
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.temp_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.temp_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width},{self.temp_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width},{self.temp_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
           if self.batv and self.s1enable:
              gridy = 0
              for x in range(0,self.batv_grid_nbr+1):
                 if x == 0 or x == self.batv_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.batv_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.batv_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText({format(self.maxbatv-x*0.05,".2f")}, {self.left_scale_x}, {int(self.batv_start_y+gridy+5)});\n')                          
                 self.outfile.write (f'ctx.fillText({format(self.maxbatv-x*0.05,".2f")}, {self.right_scale_x}, {int(self.batv_start_y+gridy+5)});\n')                          
                 gridy += self.batv_grid_y        
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.batv_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.batv_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width},{self.batv_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width},{self.batv_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')       
           if self.batv2 and self.s2enable:
              gridy = 0
              for x in range(0,self.batv2_grid_nbr+1):
                 if x == 0 or x == self.batv2_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(self.batv2_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(self.batv2_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText({format(self.maxbatv2-x*0.05,".2f")}, {self.left_scale_x}, {int(self.batv2_start_y+gridy+5)});\n')                          
                 self.outfile.write (f'ctx.fillText({format(self.maxbatv2-x*0.05,".2f")}, {self.right_scale_x}, {int(self.batv2_start_y+gridy+5)});\n')                          
                 gridy += self.batv2_grid_y         
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{self.batv2_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{self.batv2_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width},{self.batv2_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width},{self.batv2_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')             
           tidelen = len(self.tidelist)
           batvlen = len(self.batvlist)
           batv2len = len(self.batv2list)
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
           for pidx, ent in enumerate(self.predlist):
              try:
                 predtime = ent[0]
                 predtime_hm = datetime.strptime(str(ent[0])[:16], self.mintimeformat)
                 if pidx < len(self.predlist)-1:
                    predtimenext = datetime.strptime(str(self.predlist[pidx+1][0])[:16], self.mintimeformat)
                 thisDate = predtime.date()
                 if thisDate != self.listDate:
                    self.listDate = thisDate
                    self.localsunrise = datetime.strftime(self.sun.riselocal(self.listDate),'%Y-%m-%d %H:%M')+':00'
                    self.localsunset = datetime.strftime(self.sun.setlocal(self.listDate),'%Y-%m-%d %H:%M')+':00'
                 predstate = ent[3]
                 plottime = predtime.timestamp() - starttime.timestamp()
                 tide_x = round((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                 hrmin = datetime.strftime(predtime, "%H:%M")
                 linedate = datetime.strftime(predtime, "%d %b")
                 if pidx == 0:
                    predstartx = int(pstart+ent[1]*(self.plot_width-30)/86400/self.plotdays)
                    predstarty = self.tide_end_y-int((ent[2]-math.floor(self.mintide))*self.tide_grid_y)
                    predstarthx = predstartx
                    predstarthy = predstarty
                    predstartft = ent[2]
                 predendx = int(pstart+ent[1]*(self.plot_width-30)/86400/self.plotdays)
                 predendy = self.tide_end_y-int((ent[2]-math.floor(self.mintide))*self.tide_grid_y)
                 predendft = ent[2]      
                 if aidx < tidelen-1:
                    tidetime = datetime.strptime(self.tidelist[aidx][0][:16], self.mintimeformat)
                 if aidx+1 < tidelen-1:
                    tidetimenext = datetime.strptime(self.tidelist[aidx+1][0][:16], self.mintimeformat)
                 if bidx < batvlen-1:
                    batvtime = datetime.strptime(self.batvlist[bidx][0][:16], self.mintimeformat)
                 if bidx+1 < batvlen-1:
                    batvtimenext = datetime.strptime(self.batvlist[bidx+1][0][:16], self.mintimeformat)
                 if b2idx < batv2len-1:
                    batv2time = datetime.strptime(self.batv2list[b2idx][0][:16], self.mintimeformat)
                 if b2idx+1 < batv2len-1:
                    batv2timenext = datetime.strptime(self.batv2list[b2idx+1][0][:16], self.mintimeformat)
                 if self.tidesup:
                    while tidetime == predtime_hm and aidx < tidelen-1:
                       if self.station1 and self.s1enable and self.tidelist[aidx][1] == 1:
                          tide_y = self.tide_end_y-int(((self.station1cal-self.tidelist[aidx][2]/12) -math.floor(self.mintide))*self.tide_grid_y)
                          tideft = self.station1cal-self.tidelist[aidx][2]/12
                          varift = tideft-predendft
                          vari_y = self.vari_end_y-int((varift+2)*self.grid_height)
                          if savetime == 0 or tidetime > savetime + timedelta(minutes=15):               
                             #outfile.write ('ctx.fillStyle = "blue";\n')
                             #outfile.write (f'ctx.fillRect({tide_x},{tide_y},1,2);\n')
                             pass
                          else:
                             self.outfile.write (f'ctx.strokeStyle = "blue";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({savex},{savey});\n')
                             self.outfile.write (f'ctx.lineTo({tide_x},{tide_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')                                    
                          savetime = tidetime
                          savex = tide_x
                          savey = tide_y
                          if predstate == 'L' or predstate == 'H':
                             if self.prestate == '':
                                self.prestate = predstate
                             elif self.prestate != predstate:
                                self.prestate = predstate
                                if variinit:
                                   self.outfile.write (f'ctx.strokeStyle = "blue";\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({varistart_x},{varistart_y});\n')
                                   self.outfile.write (f'ctx.lineTo({tide_x},{vari_y});\n')
                                   self.outfile.write (f'ctx.stroke();\n')                                    
                                   varistart_x = tide_x
                                   varistart_y = vari_y
                                variinit = True
                                if varistart_x == -99: varistart_x = tide_x
                                if varistart_y == -99: varistart_y = vari_y                    
                       elif self.station2 and self.s2enable and self.tidelist[aidx][1] == 2:
                          tide_y = self.tide_end_y-int(((self.station2cal-self.tidelist[aidx][2]/12)-math.floor(self.mintide))*self.tide_grid_y)
                          tideft = self.station2cal-self.tidelist[aidx][2]/12
                          varift = tideft-predendft
                          vari_y = self.vari2_end_y-int((varift+2)*self.grid_height)
                          if savetime2 == 0 or tidetime > savetime2 + timedelta(minutes=15):               
                             #outfile.write ('ctx.fillStyle = "darkgreen";\n')
                             #outfile.write (f'ctx.fillRect({tide_x},{tide_y},1,2);\n')
                             pass
                          else:
                             self.outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({savex2},{savey2});\n')
                             self.outfile.write (f'ctx.lineTo({tide_x},{tide_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')                                    
                          savetime2 = tidetime
                          savex2 = tide_x
                          savey2 = tide_y
                          if predstate == 'L' or predstate == 'H':
                             if self.prestate2 == '':
                                self.prestate2 = predstate
                             elif self.prestate2 != predstate:
                                self.prestate2 = predstate
                                if vari2init:
                                   self.outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({vari2start_x},{vari2start_y});\n')
                                   self.outfile.write (f'ctx.lineTo({tide_x},{vari_y});\n')
                                   self.outfile.write (f'ctx.stroke();\n')                                    
                                   vari2start_x = tide_x
                                   vari2start_y = vari_y
                                vari2init = True
                                if vari2start_x == -99: vari2start_x = tide_x
                                if vari2start_y == -99: vari2start_y = vari_y                                            
                       aidx += 1
                       if aidx < tidelen-1:
                          tidetime = datetime.strptime(self.tidelist[aidx][0][:16], self.mintimeformat)
                       if aidx+1 < tidelen-1:
                          tidetimenext = datetime.strptime(self.tidelist[aidx+1][0][:16], self.mintimeformat)
                    while tidetimenext < predtimenext and aidx < tidelen-1:
                       aidx += 1
                       if aidx < tidelen-1:
                          tidetimenext = datetime.strptime(self.tidelist[aidx][0][:16], self.mintimeformat)

                 if self.s1enable and self.batv and len(self.batvlist) != 0:
                    if batvtime == predtime_hm:
                       batv_y = self.batv_end_y-int((self.batvlist[bidx][1]-self.minbatv)*self.batv_y_fact)
                       if savebatvtime == 0 or predtime_hm > savebatvtime + timedelta(minutes=15):               
                          #outfile.write ('ctx.fillStyle = "black";\n')
                          #outfile.write (f'ctx.fillRect({tide_x},{batv_y},1,2);\n')
                          pass
                       else:
                          self.outfile.write (f'ctx.strokeStyle = "black";\n')
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({savebatvx},{savebatvy});\n')
                          self.outfile.write (f'ctx.lineTo({tide_x},{batv_y});\n')
                          self.outfile.write (f'ctx.stroke();\n')                                    
                          if str(predtime_hm) == self.localsunrise:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                          elif str(predtime_hm) == self.localsunset:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                       savebatvtime = batvtime
                       savebatvx = tide_x
                       savebatvy = batv_y                  
                       bidx += 1
                    else:
                       while batvtimenext < predtimenext and bidx < batvlen-1:
                          bidx += 1
                          if bidx < batvlen-1:
                             batvtimenext = datetime.strptime(self.batvlist[bidx][0][:16], self.mintimeformat)if self.s2enable and self.batv2 and len(self.batv2list) != 0:
                    if batv2time == predtime_hm:
                       batv2_y = self.batv2_end_y-int((self.batv2list[b2idx][1]-self.minbatv2)*self.batv2_y_fact)
                       if savebatv2time == 0 or predtime_hm > savebatv2time + timedelta(minutes=15):               
                          #outfile.write ('ctx.fillStyle = "black";\n')
                          #outfile.write (f'ctx.fillRect({tide_x},{batv2_y},1,2);\n')
                          pass
                       else:
                          self.outfile.write (f'ctx.strokeStyle = "black";\n')
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({savebatv2x},{savebatv2y});\n')
                          self.outfile.write (f'ctx.lineTo({tide_x},{batv2_y});\n')
                          self.outfile.write (f'ctx.stroke();\n')                                    
                          if str(predtime_hm) == self.localsunrise:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv2_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv2_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv2_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                          elif str(predtime_hm) == self.localsunset:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv2_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv2_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv2_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                       savebatv2time = batv2time
                       savebatv2x = tide_x
                       savebatv2y = batv2_y                  
                       b2idx += 1
                    else:
                       while batv2timenext < predtimenext and b2idx < batv2len-1:
                          b2idx += 1
                          if b2idx < batv2len-1:
                             batv2timenext = datetime.strptime(self.batv2list[b2idx][0][:16], self.mintimeformat)

              except Exception as errmsg:
                 pline = self.msgtime+' Error - '+str(errmsg)
                 with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                    self.logfile.write (pline+'\n')
                 continue            
              self.outfile.write ('ctx.fillStyle = "black";\n')
              if predtime.minute == 0 and predtime.hour  == 0:
                 self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write (f'ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({predstartx},{self.tide_start_y});\n')
                 self.outfile.write (f'ctx.lineTo({predstartx},{self.tide_end_y});\n')
                 self.outfile.write (f'ctx.stroke();\n')                                                                     
                 self.outfile.write (f'ctx.beginPath();\n')
                 if self.station1:
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.vari_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.vari_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.station2:
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.vari2_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.vari2_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.wind:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.wind_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.wind_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.rain:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.rain_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.rain_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.temp:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.temp_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.temp_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.s1enable and self.batv:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.batv_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.batv_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.s2enable and self.batv2:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.batv2_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
              if predtime.minute == 0 and predtime.hour == 12:
                 self.outfile.write (f'ctx.fillText("{linedate}", {predstartx}, {self.dtime_start_y+17});\n')                          
                 self.outfile.write (f'ctx.fillText("{linedate}", {predstartx}, {self.canvas_height-5});\n')                          
              if pidx % 10 == 0:
                 self.outfile.write (f'ctx.strokeStyle = "gray";\n')
                 self.outfile.write (f'ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({predstarthx},{predstarthy});\n')
                 self.outfile.write (f'ctx.lineTo({predendx},{predendy});\n')
                 self.outfile.write (f'ctx.stroke();\n')
                 predstarthx = predendx
                 predstarthy = predendy         
              predstartx = predendx
              predstarty = predendy
              predstartft = predendft                  
              if (self.wind or self.rain or self.temp) and self.wxsup and widx < self.wxlength-1:
                 try:
                    wxtime = datetime.strptime(wxlist[widx][0][:16], self.mintimeformat)
                    nextwxtime = datetime.strptime(wxlist[widx+1][0][:16], self.mintimeformat)
                    while widx < self.wxlength-1 and wxtime < predtime_hm:
                       widx += 1
                       wxtime = datetime.strptime(wxlist[widx][0][:16], self.mintimeformat)
                       nextwxtime = datetime.strptime(wxlist[widx+1][0][:16], self.mintimeformat)
                    if wxtime == predtime_hm:
                       if self.wind and wxinit:
                          if wxlist[widx][4] != '' and wxlist[widx][4] is not None:
                             wxendx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                             wxendy = self.wind_end_y-int(wxlist[widx][4]*self.grid_height/5)
                             self.windlist.append(wxendy)
                             if wxlist[widx][4] > maxwind:
                                maxwind = wxlist[widx][4]
                                maxwdir = wxlist[widx][5]
                             windcount += 1
                             if windcount == 5:
                                wxendy = sum(self.windlist)/len(self.windlist)
                                self.outfile.write (f'ctx.strokeStyle = "purple";\n')
                                self.outfile.write (f'ctx.beginPath();\n')
                                self.outfile.write (f'ctx.moveTo({wxstartx},{wxstarty});\n')
                                self.outfile.write (f'ctx.lineTo({wxendx},{wxendy});\n')
                                self.outfile.write (f'ctx.stroke();\n')
                                wxstartx = wxendx
                                wxstarty = wxendy
                                windcount = 0
                                self.windlist = []
                                if wxendx > windex+10 and maxwind > 2:
                                   windex = wxendx
                                   winddir = maxwdir
                                   windrad = winddir * (math.pi/180)
                                   windcos = math.cos(windrad)
                                   windsin = math.sin(windrad)
                                   newarrow = []
                                   for point in self.windarrow:
                                      x = point[0]
                                      y = point[1]
                                      newarrow.append([int(x*windcos-y*windsin+wxendx),int(x*windsin+y*windcos+self.windir_start_y+self.grid_height/2)])
                                   self.outfile.write (f'ctx.strokeStyle = "purple";\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({newarrow[0][0]},{newarrow[0][1]});\n')
                                   self.outfile.write (f'ctx.lineTo({newarrow[1][0]},{newarrow[1][1]});\n')
                                   self.outfile.write (f'ctx.stroke();\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({newarrow[0][0]},{newarrow[0][1]});\n')
                                   self.outfile.write (f'ctx.lineTo({newarrow[2][0]},{newarrow[2][1]});\n')
                                   self.outfile.write (f'ctx.stroke();\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({newarrow[0][0]},{newarrow[0][1]});\n')
                                   self.outfile.write (f'ctx.lineTo({newarrow[3][0]},{newarrow[3][1]});\n')
                                   self.outfile.write (f'ctx.stroke();\n')
                                maxwdir = 0
                                maxwind = 0
                       elif self.wind:
                          if wxlist[widx][4] != '' and wxlist[widx][4] is not None:
                             wxstartx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                             wxstarty = self.wind_end_y-int(wxlist[widx][4]*self.grid_height/5)
                             self.windlist.append(wxstarty)
                             windcount += 1
                             if windcount == 5:
                                wxstarty = sum(self.windlist)/len(self.windlist)
                                self.windlist = []
                                windcount = 0
                                wxinit = True
                       if self.rain and rxinit:
                          if wxlist[widx][10] != '' and wxlist[widx][10] is not None:
                             rxendx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                             rxendy = self.rain_end_y-int(wxlist[widx][10]*2*self.grid_height)
                             if widx % 10 == 0:
                                self.outfile.write (f'ctx.strokeStyle = "black";\n')
                                self.outfile.write (f'ctx.beginPath();\n')
                                self.outfile.write (f'ctx.moveTo({rxstarthx},{rxstarthy});\n')
                                self.outfile.write (f'ctx.lineTo({rxendx},{rxendy});\n')
                                self.outfile.write (f'ctx.stroke();\n')
                                rxstarthx = rxendx
                                rxstarthy = rxendy
                             rxstartx = rxendx
                             rxstarty = rxendy          
                       elif self.rain:
                          if wxlist[widx][10] != '' and wxlist[widx][10] is not None:
                             rxstartx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                             rxstarty = self.rain_end_y-int(wxlist[widx][10]*2*self.grid_height)
                             rxstarthx = rxstartx
                             rxstarthy = rxstarty
                             rxinit = True
                       if self.temp and txinit:
                          if wxlist[widx][1] != '' and wxlist[widx][1] is not None:
                             txendx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                             txendy = self.temp_end_y-int((wxlist[widx][1]-self.mintemp)/5*self.grid_height)
                             if widx % 10 == 0:
                                self.outfile.write (f'ctx.strokeStyle = "red";\n')
                                self.outfile.write (f'ctx.beginPath();\n')
                                self.outfile.write (f'ctx.moveTo({txstarthx},{txstarthy});\n')
                                self.outfile.write (f'ctx.lineTo({txendx},{txendy});\n')
                                self.outfile.write (f'ctx.stroke();\n')
                                txstarthx = txendx
                                txstarthy = txendy
                             txstartx = txendx
                             txstarty = txendy          
                       elif self.temp:
                          if wxlist[widx][1] != '' and wxlist[widx][1] is not None:
                             txstartx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                             txstarty = self.temp_end_y-int((wxlist[widx][1]-self.mintemp)/5*self.grid_height)
                             txstarthx = txstartx
                             txstarthy = txstarty
                             txinit = True
                       widx += 1
                    checktime = wxtime+timedelta(minutes=10)
                    if nextwxtime > checktime:
                       wxinit = False
                       rxinit = False
                       txinit = False            
                 except Exception as errmsg:
                    pline = '\n'+self.msgtime+' Error: '+str(errmsg)
                    with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                       self.logfile.write (pline+'\n')   

           self.outfile.write (f'ctx.strokeStyle = "black";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({x_start},{self.tide_start_y});\n')
           self.outfile.write (f'ctx.lineTo({x_start},{self.tide_end_y});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width-1},{self.tide_start_y});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width-1},{self.tide_end_y});\n')
           self.outfile.write (f'ctx.stroke();\n')
        #
        #   Create Actual High and Low tide annotation
        #
           midcanvas = self.tide_start_y+self.tide_height/2
           if self.tags and self.tidesup:
              self.outfile.write (f'ctx.textAlign = "center";\n')
              self.outfile.write (f'ctx.strokeStyle = "blue";\n')
              for pidx, ent in enumerate(self.tidelist):
                 try:
                    tidetime = datetime.strptime(ent[0], self.sqltimeformat)
                    hrmin = datetime.strftime(tidetime, "%H:%M")
                    linedate = datetime.strftime(tidetime, "%d %b")
                    plottime = tidetime.timestamp() - starttime.timestamp()
                    startx = int((plottime+offtime)*(self.plot_width-30)/86400/self.plotdays+30)
                    hourtime = tidetime.hour
                    if self.s1enable and self.station1 and ent[1] == 1:
                       tidestate = str(ent[3])
                       if tidestate == 'low' or tidestate == 'high':
                          if self.turntime == '' or abs(hourtime-self.turntime) >= 3:
                             self.turntime = hourtime
                             peak = format(self.station1cal-ent[2]/12,'.1f')
                             peaks = peak+' '+hrmin
                             self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                             self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y-19}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y-19}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillStyle = "blue";\n')
                             self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y+9});\n')
                             self.outfile.write (f'ctx.fillText("{peak}", {startx}, {self.tag_y-6});\n')
                    if self.s2enable and self.station2 and ent[1] == 2:
                       tidestate = str(ent[3])
                       if tidestate == 'low' or tidestate == 'high':
                          if self.turntime2 == '' or abs(hourtime-self.turntime2) >= 3:
                             self.turntime2 = hourtime
                             peak = format(self.station2cal-ent[2]/12,'.1f')
                             peaks = peak+' '+hrmin
                             self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                             self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y-51}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y-51}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillStyle = "darkgreen";\n')
                             self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y-23});\n')
                             self.outfile.write (f'ctx.fillText("{peak}", {startx}, {self.tag_y-38});\n')
                 except Exception as errmsg:
                    pline = self.msgtime+' Error - '+str(errmsg)
                    with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                       self.logfile.write (pline+'\n')
        #
        # Create Dashed vertical lines and if tags also create Predicted High and Low Tide Annotation
        #
           self.prestate = ''
           for pidx, ent in enumerate(self.predlist):
              if pidx == 0:
                 startx = pstart+ent[1]*(self.plot_width-30)/86400/self.plotdays
                 #starty = tide_end_y-int((ent[2]+2)*grid_height)
                 self.prestate = ent[3]
                 continue
              predstate = ent[3]
              predtime = ent[0]
              hrmin = datetime.strftime(predtime, "%H:%M")
              linedate = datetime.strftime(predtime, "%d %b")

              endx = int(pstart+ent[1]*(self.plot_width-30)/86400/self.plotdays)
              #endy = tide_end_y-int((ent[2]-mintide)*grid_height)
              if predstate == 'L' or predstate == 'H':
                 peak = format(ent[2],'.1f')
                 peaks = peak+' '+hrmin
                 if self.prestate == '':
                    self.prestate = predstate
                 elif self.prestate != predstate:
                    dash_size = 7
                    dash_end_y = self.tide_start_y
                    self.outfile.write (f'ctx.strokeStyle = "gray";\n')
                    while dash_end_y < self.tide_end_y:
                       self.outfile.write (f'ctx.beginPath();\n')
                       self.outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                       if dash_end_y+dash_size > self.tide_end_y:
                          self.outfile.write (f'ctx.lineTo({endx},{self.tide_end_y});\n')
                       else:
                          self.outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
                       self.outfile.write (f'ctx.stroke();\n')
                       dash_end_y += dash_size*2
                    if self.s1enable and self.station1:
                       dash_end_y = self.vari_start_y
                       while dash_end_y < self.vari_end_y:
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                          if dash_end_y+dash_size > self.vari_end_y:
                             self.outfile.write (f'ctx.lineTo({endx},{self.vari_end_y});\n')
                          else:
                             self.outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
                          self.outfile.write (f'ctx.stroke();\n')
                          dash_end_y += dash_size*2
                    if self.s2enable and self.station2:
                       dash_end_y = self.vari2_start_y
                       while dash_end_y < self.vari2_end_y:
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                          if dash_end_y+dash_size > self.vari2_end_y:
                             self.outfile.write (f'ctx.lineTo({endx},{self.vari2_end_y});\n')
                          else:
                             self.outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
                          self.outfile.write (f'ctx.stroke();\n')
                          dash_end_y += dash_size*2
                    self.prestate = predstate
                    if self.tags:                  
                       self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                       self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y+13}, 42, 30);\n')
                       self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y+13}, 42, 30);\n')
                       self.outfile.write (f'ctx.fillStyle = "gray";\n')
                       self.outfile.write (f'ctx.fillText("{peak}", {startx}, {self.tag_y+27});\n')
                       self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y+42});\n')
                 startx = endx
                 #starty = endy
           self.outfile.write (f'ctx.strokeStyle = "blue";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/4-60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/4-30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/4+30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/4+60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/4*2-60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/4*2-30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/4*2+30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/4*2+60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.strokeStyle = "gray";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/4*3-70},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/4*3-40},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/4*3+40},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/4*3+70},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write ('ctx.textAlign = "center";\n')
           self.outfile.write ('ctx.font = "14px Arial";\n')
           self.outfile.write ('ctx.fillStyle = "blue";\n')
           self.outfile.write (f'ctx.fillText("Sensor 1", {self.plot_width/4}, {self.tide_start_y-4});\n')
           self.outfile.write ('ctx.fillStyle = "darkgreen";\n')
           self.outfile.write (f'ctx.fillText("Sensor 2", {self.plot_width/4*2}, {self.tide_start_y-4});\n')
           if not self.tidesup and self.banflag == '1':
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("{self.banner}", {self.plot_width/2}, {self.tide_end_y-10});\n')      
           self.outfile.write ('ctx.fillStyle = "gray";\n')
           self.outfile.write (f'ctx.fillText("Predicted", {self.plot_width/4*3}, {self.tide_start_y-4});\n')
           if self.s1enable and self.station1:
              self.outfile.write ('ctx.fillStyle = "blue";\n')
              self.outfile.write (f'ctx.fillText("Variation between Sensor 1 and predicted tide in feet", {self.plot_width/2}, {self.vari_start_y-4});\n')
           if self.s2enable and self.station2:
              self.outfile.write ('ctx.fillStyle = "darkgreen";\n')
              self.outfile.write (f'ctx.fillText("Variation between Sensor 2 and predicted in feet", {self.plot_width/2}, {self.vari2_start_y-4});\n')
           if self.wind:   
              self.outfile.write ('ctx.fillStyle = "purple";\n')
              self.outfile.write (f'ctx.fillText("Wind speed (mph) and direction (arrow indicates wind direction relative to north)", {self.plot_width/2}, {self.windir_start_y-4});\n')
           if self.rain:      
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("Daily rainfall in inches", {self.plot_width/2}, {self.rain_start_y-4});\n')                          
           if self.temp:      
              self.outfile.write ('ctx.fillStyle = "red";\n')
              self.outfile.write (f'ctx.fillText("Temperature in degrees F", {self.plot_width/2}, {self.temp_start_y-4});\n')                          
           if self.s1enable and self.batv:      
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("Sensor 1 Battery Voltage", {self.plot_width/2}, {self.batv_start_y-4});\n')                          
           if self.s2enable and self.batv2:      
              self.outfile.write (f'ctx.fillText("Sensor 2 Battery Voltage", {self.plot_width/2}, {self.batv2_start_y-4});\n')                          
           self.outfile.write ('</script>\n')
           self.outfile.write ('</div>\n')
           self.outfile.write ('</body>\n')
           self.outfile.write ('</html>\n')
           if not self.is_cgi_request:
              self.outfile.close()
              os.system(f'mv {self.filetag} /var/www/html/tideplot.html')


    def run(self):
        self.curtime = datetime.now()
        self.msgtime = str(self.curtime)[:-10]# Mode detection: Apache sets REQUEST_METHOD for every CGI invocation; it is
        # absent when this script is run directly (e.g. from cron).
        self.is_cgi_request = "REQUEST_METHOD" in os.environ

        if self.is_cgi_request:
           self.filetag = None
           self.outfile = sys.stdout
        else:
           self.filetag = "tide"+datetime.strftime(self.curtime, "%y%m%d%H%M%S")+".html"
           self.outfile = open(self.filetag, "w")

        self.tags = False
        self.station1 = False
        self.station2 = False
        self.wind = False
        self.rain = False
        self.temp = False
        default_station_id = 1
        #
        # Get station name for webpage title
        #
        envfile = find_dotenv('tide.env')
        if load_dotenv(envfile):
           self.station_location = os.getenv('STATION_LOCATION')
           station_latitude = os.getenv('STATION_LATITUDE')
           station_longitude = os.getenv('STATION_LONGITUDE')
           default_station_id = int(os.getenv('DEFAULT_STATION_ID', '1'))
           #with open('/var/www/html/tideplot.log', 'a') as logfile:
           #   logfile.write (msgtime+ 'station_location: '+station_location+'\n')                  
        else:
           with open('/var/www/html/tideplot.log', 'a') as self.logfile:
              self.logfile.write (self.msgtime+ 'environment file read failed\n')                  

        #
        # Establish SQLite3 connection to the tides.db database
        #

        try:
           sqlcon = sqlite3.connect(f'/home/tide/Uploads/tides.db')
           self.sqlcur = sqlcon.cursor()
        except:
           with open('/var/www/html/tideplot.log', 'a') as self.logfile:
              self.logfile.write (self.msgtime+ 'tideplot sqlite3 connection failed\n')                  
           exit()
        #
        # Read initialization data from iparams table
        #
        try:
        #if True:
           self.sqlcur.execute("select * from iparams")
           iparams = self.sqlcur.fetchall()
           #banflag = iparams[0][2]
           #banner = iparams[0][3]
           self.station1cal = iparams[0][5]
           self.station2cal = iparams[0][6]
           self.s1enable = iparams[0][7]
           self.s2enable = iparams[0][8]
           #
           # Get the lastest time entry in the tides.db database
           # 
           self.formdate = self.curtime.strftime("%Y-%m-%d")
           #
           # Process form parameters
           #
           if self.is_cgi_request:
              form = cgi.FieldStorage()
              init = form.getvalue('init')
           else:
              # Cron/file mode never had a real request to parse; always render the
              # default (DEFAULT_STATION_ID-driven) view, matching prior tideplot.py behavior.
              form = None
              init = "1"
           if init != None:
              init = True
              self.plotdays = 3
              self.tags =  True
              self.tagchk = 'checked'
              self.station1 = (default_station_id == 1)
              self.station1chk = 'checked' if self.station1 else ''
              self.station2 = (default_station_id == 2)
              self.station2chk = 'checked' if self.station2 else ''
              self.wind = True
              self.windchk = 'checked'
              self.rain = True
              self.rainchk = 'checked'
              self.temp = True
              self.tempchk = 'checked'
              self.batv = (default_station_id == 1)
              self.batvchk = 'checked' if self.batv else ''
              self.batv2 = (default_station_id == 2)
              self.batv2chk = 'checked' if self.batv2 else ''
           else:
              init = False
              self.tags = form.getvalue('tags')
              if self.tags == None:
                 self.tags = False
                 self.tagchk = ''
              else:
                 self.tags = True
                 self.tagchk = 'checked'
              self.station1 = form.getvalue('station1')
              if self.station1 == None:
                 self.station1 = False
                 self.station1chk = ''
              else:
                 self.station1 = True
                 self.station1chk = 'checked'
              self.station2 = form.getvalue('station2')
              if self.station2 == None:
                 self.station2 = False
                 self.station2chk = ''
              else:
                 self.station2 = True
                 self.station2chk = 'checked'
              self.wind = form.getvalue('wind')
              if self.wind == None:
                 self.wind = False
                 self.windchk = ''
              else:
                 self.wind = True
                 self.windchk = 'checked'
              self.rain = form.getvalue('rain')
              if self.rain == None:
                 self.rain = False
                 self.rainchk = ''
              else:
                 self.rain = True
                 self.rainchk = 'checked'
              self.temp = form.getvalue('temp')
              if self.temp == None:
                 self.temp = False
                 self.tempchk = ''
              else:
                 self.temp = True
                 self.tempchk = 'checked'
              self.batv = form.getvalue('batv')
              if self.batv == None:
                 self.batv = False
                 self.batvchk = ''
              else:
                 self.batv = True
                 self.batvchk = 'checked'
              self.batv2 = form.getvalue('batv2')
              if self.batv2 == None:
                 self.batv2 = False
                 self.batv2chk = ''
              else:
                 self.batv2 = True
                 self.batv2chk = 'checked'
              self.plotdays = form.getvalue('dayspan')
              if self.plotdays == None:
                 self.plotdays = 3
              else:
                 self.plotdays = int(self.plotdays)
              if self.plotdays > 10:
                 self.tags = False
                 self.tagchk = ''
              getdate = form.getvalue('endate')
              if getdate != None:
                 chktime = datetime.now()
                 chktime = datetime.strptime(str(chktime)[:10], '%Y-%m-%d')
                 self.curtime = datetime.strptime(getdate,"%Y-%m-%d")
                 if self.curtime == chktime:
                    self.curtime = datetime.now()
                 self.formdate = self.curtime.strftime("%Y-%m-%d")
           if self.is_cgi_request:
              self.canvas_width = form.getvalue('screenwidth')
              if self.canvas_width ==  None:
                 self.canvas_width = 1200
              else:
                 self.canvas_width = int(self.canvas_width)-100
              default_height = form.getvalue('screenheight')
              if default_height == None:
                 default_height = 750
              else:
                 default_height = int(default_height)
                 if default_height < 750:
                    default_height = 750
           else:
              # Cron/file mode has no real request to read screen size from;
              # matches prior tideplot.py's hardcoded defaults.
              self.canvas_width = 1200
              default_height = 750
           radinc = math.pi*2/91080
           self.prestate = ''
           self.prestate2 = ''
           self.predicts = []
           self.turntime = ''
           self.turntime2 = ''
           self.tide_predict()
           self.tidelist = []
           self.batvlist= []
           self.batv2list = []
           self.windlist = []
           self.localsunrise = 0
           self.localsunset = 0
           self.listDate = 0

           self.dbquerytime = self.curtime - timedelta(days=self.plotdays)
           self.sqlcur.execute("select dtime, stationid, distance from sensors where dtime "+ \
                         "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
           self.tidelist = self.sqlcur.fetchall()

           self.tidelist = self._get_epochs(self.tidelist)

           if len(self.tidelist) == 0:
              self.station1 = False
              self.station2 = False
              self.canvas_height = 400
              self.proc_data()
              exit()

           if self.s1enable:
              self.sqlcur.execute("select dtime, batv from sensors where stationid = 1 and dtime "+ \
                            "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
              self.batvlist = self.sqlcur.fetchall()
           if self.s2enable:   
              self.sqlcur.execute("select dtime, batv from sensors where stationid = 2 and dtime "+ \
                            "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
              self.batv2list = self.sqlcur.fetchall()

           self.sqlcur.execute("select * from wxdata where dtime "+ \
                         "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
           self.sun = SunTimes(float(station_longitude),float(station_latitude))
           wxlist = self.sqlcur.fetchall()
           self.wxlength = len(wxlist)
           if self.wxlength != 0:
              self.wxsup = True
           else:
              self.wxsup = False
           self.tidesup = False
           tidesum = 0
           tidesum2 = 0
           tideave2 = 0
           maxtide = -99
           self.mintide = 99
           maxtide2 = -99
           mintide2 = 99
           self.minbatv = 99
           self.maxbatv = -99
           self.minbatv2 = 99
           self.maxbatv2 = -99
           minwind = 99
           maxwind = -99
           self.mintemp = 99
           maxtemp = -99
           minrain = 99
           maxrain = -99
           self.tide_grid_nbr = 0
           self.vari_grid_nbr = 0
           self.wind_grid_nbr = 0
           self.windir_grid_nbr = 0
           self.rain_grid_nbr = 0
           self.temp_grid_nbr = 0
           self.batv_grid_nbr = 0
           batv_grid_span = 0
           self.batv2_grid_nbr = 0
           batv2_grid_span = 0
           wind_height = 0
           rain_height = 0
           temp_height = 0
           batv_height = 0
           batv2_height = 0
           self.tide_grid_y = 0
           self.wind_grid_y = 0
           self.rain_grid_y = 0
           self.temp_grid_y = 0
           self.batv_grid_y = 0
           self.batv2_grid_y = 0
           if len(self.tidelist) != 0:
              self.tidesup = True
              for chkent in self.tidelist:
                 if self.station1 and chkent[1] == 1 and self.s1enable:
                    self.tidelevel = self.station1cal-chkent[2]/12
                    if self.tidelevel > maxtide:
                       maxtide = self.tidelevel 
                    if self.tidelevel < self.mintide:
                       self.mintide = self.tidelevel
                 elif self.station2 and chkent[1] == 2 and self.s2enable:
                    self.tidelevel = self.station2cal-chkent[2]/12
                    if self.tidelevel > maxtide2:
                       maxtide2 = self.tidelevel
                    if self.tidelevel < mintide2:
                       mintide2 = self.tidelevel 
              if self.mintide == 99 or maxtide == -99:
                 self.station1 = False
              if mintide2 == 99 or maxtide2 == -99:
                 self.station2 = False
              if mintide2 < self.mintide:
                 self.mintide = mintide2
              if maxtide2 > maxtide:
                 maxtide = maxtide2
              #with open('/var/www/html/tideplot.log', 'a') as logfile:
              #   logfile.write ('mintide: '+str(mintide)+'\n')
              #   logfile.write ('maxtide: '+str(maxtide)+'\n')
              #   logfile.write ('mintide2: '+str(mintide2)+'\n')
              #   logfile.write ('maxtide2: '+str(maxtide2)+'\n')
           if len(self.batvlist) != 0 and self.s1enable:
              for chkent in self.batvlist:
                 if chkent[1] != None and chkent[1] < 4.3 and chkent[1] > 2.5:
                    if chkent[1] > self.maxbatv:
                       self.maxbatv = chkent[1]
                    if chkent[1] < self.minbatv:
                       self.minbatv = chkent[1]
              if self.minbatv == 99 or self.maxbatv == -99:
                 self.batv = False
              else:
                 minbatv1 = int(self.minbatv/0.05)
                 self.minbatv = round(minbatv1*0.05,2)
                 maxbatv1 = int(self.maxbatv/0.05)
                 self.maxbatv = round(maxbatv1*0.05+0.05,2)
           else:
              self.batv = False       
           if len(self.batv2list) != 0 and self.s2enable:
              for chkent in self.batv2list:
                 if chkent[1] != None and chkent[1] < 4.3 and chkent[1] > 2.5:
                    if chkent[1] > self.maxbatv2:
                       self.maxbatv2 = chkent[1]
                    if chkent[1] < self.minbatv2:
                       self.minbatv2 = chkent[1]
              if self.minbatv2 == 99 or self.maxbatv2 == -99:
                 self.batv2 = False
              else:
                 minbatv1 = int(self.minbatv2/0.05)
                 self.minbatv2 = round(minbatv1*0.05,2)
                 maxbatv1 = int(self.maxbatv2/0.05)
                 self.maxbatv2 = round(maxbatv1*0.05+0.05,2)
           else:
              self.batv2 = False

           if len(wxlist) != 0:
              for chkent in wxlist:
                 if chkent[1] != None and chkent[1] != 0 and chkent[1] != '':
                    if chkent[1] > maxtemp:
                       maxtemp = chkent[1]
                    if chkent[1] < self.mintemp:
                       self.mintemp = chkent[1]
                 if chkent[4] != None and chkent[4] != 0 and chkent[4] != '':
                    if chkent[4] > maxwind:
                       maxwind = chkent[4]
                    if chkent[4] < minwind:
                       minwind = chkent[4]
                 if chkent[10] != None and chkent[10] != 0 and chkent[10] != '':
                    if chkent[10] > maxrain:
                       maxrain = chkent[10]
                    if chkent[10] < minrain:
                       minrain = chkent[10]
              if self.mintemp == 99 or maxtemp == -99:
                  self.temp = False
              if minrain == 99 or maxrain == -99:
                  self.rain = False
           else:
              pass
           if self.maxpred > maxtide:
              maxtide = self.maxpred
           if self.minpred < self.mintide:
              self.mintide = self.minpred
           self.tide_grid_nbr = round(maxtide+0.5)-math.floor(self.mintide)
           self.vari_grid_nbr = 4
           total_grids = self.tide_grid_nbr
           nbr_gaps = 0
           if self.station1 and self.s1enable:
              total_grids += self.vari_grid_nbr
              nbr_gaps += 1
           if self.station2 and self.s2enable:
              total_grids += self.vari_grid_nbr
              nbr_gaps += 1
           if self.wind:
              self.windir_grid_nbr = 1
              total_grids += self.windir_grid_nbr
              windir_height = self.windir_grid_nbr*self.grid_height
              self.wind_grid_nbr = round((maxwind-minwind)/5+0.5)
              total_grids += self.wind_grid_nbr
              nbr_gaps += 1
              wind_height = self.wind_grid_nbr*self.grid_height
              self.wind_grid_y = round(wind_height/self.wind_grid_nbr/5,3)
           if self.rain:
              self.rain_grid_nbr = 4
              total_grids += self.rain_grid_nbr
              nbr_gaps += 1
              rain_height = self.rain_grid_nbr*self.grid_height
              self.rain_grid_y = round(rain_height/self.rain_grid_nbr,3)
           if self.temp:
              self.temp_grid_nbr = round((maxtemp-self.mintemp)/5+0.5)
              total_grids += self.temp_grid_nbr
              nbr_gaps += 1
              temp_height = self.temp_grid_nbr*self.grid_height
              self.temp_grid_y = round(temp_height/self.temp_grid_nbr,3)
           if self.batv and self.s1enable:
              self.batv_grid_nbr = round((self.maxbatv-self.minbatv)/0.05)
              total_grids += self.batv_grid_nbr  
              nbr_gaps += 1
              batv_grid_span = round(self.maxbatv-self.minbatv,2)
              batv_height = self.batv_grid_nbr*self.grid_height
              self.batv_grid_y = round(batv_height/self.batv_grid_nbr,3)
              self.batv_y_fact = batv_height/batv_grid_span
           if self.batv2 and self.s2enable:
              self.batv2_grid_nbr = round((self.maxbatv2-self.minbatv2)/0.05)
              total_grids += self.batv2_grid_nbr  
              nbr_gaps += 1
              batv2_grid_span = round(self.maxbatv2-self.minbatv2,2)
              batv2_height = self.batv2_grid_nbr*self.grid_height
              self.batv2_grid_y = round(batv2_height/self.batv2_grid_nbr,3)
              self.batv2_y_fact = batv2_height/batv2_grid_span

           dtime_height = 10
           gap_size = 30
           dtime_height = 30
           footer_height = 12
           self.tide_height = self.tide_grid_nbr*self.grid_height
           vari_height = self.vari_grid_nbr*self.grid_height
           self.tide_grid_y = round(self.tide_height/self.tide_grid_nbr,3)
           self.wind_start_y = 0
           self.wind_end_y = 0
           self.rain_start_y = 0
           self.rain_end_y = 0
           self.temp_start_y =0
           self.temp_end_y = 0
           self.vari_start_y = 0
           self.vari_end_y =0
           self.vari2_start_y = 0
           self.vari2_end_y =0
           total_grid_height = total_grids*self.grid_height
           total_gaps = gap_size*nbr_gaps
           self.canvas_height = dtime_height+self.title_height+total_gaps+footer_height+total_grid_height
           self.plot_width = self.canvas_width-30
           self.right_scale_x = self.plot_width+15
           dtime_end_y = self.dtime_start_y + dtime_height
           self.tide_start_y = dtime_end_y
           self.tide_end_y = int(self.tide_height+self.tide_start_y)
           self.tag_y = int(self.tide_end_y-(self.tide_grid_nbr/2*self.grid_height))
           next_y = self.tide_end_y
           if self.station1 and self.s1enable:
              self.vari_start_y = next_y+gap_size
              self.vari_end_y = int(vari_height+self.vari_start_y)
              next_y = self.vari_end_y
           if self.station2 and self.s2enable:
              self.vari2_start_y = next_y+gap_size
              self.vari2_end_y = int(vari_height+self.vari2_start_y)
              next_y = self.vari2_end_y
           if self.wind:
              self.windir_start_y = next_y+gap_size
              windir_end_y = int(windir_height+self.windir_start_y)
              self.wind_start_y = windir_end_y
              self.wind_end_y = int(wind_height+self.wind_start_y)
              next_y = self.wind_end_y
           if self.rain:
              self.rain_start_y = next_y+gap_size
              self.rain_end_y = int(rain_height+self.rain_start_y)
              next_y = self.rain_end_y
           if self.temp:
              self.temp_start_y = next_y+gap_size
              self.temp_end_y = int(temp_height+self.temp_start_y)
              next_y = self.temp_end_y
           if self.batv and self.s1enable:
              self.batv_start_y = next_y+gap_size
              self.batv_end_y = int(batv_height+self.batv_start_y)
              next_y = self.batv_end_y
           if self.batv2 and self.s2enable:
              self.batv2_start_y = next_y+gap_size
              self.batv2_end_y = int(batv2_height+self.batv2_start_y)
        except Exception as errmsg:
        #else:
           pline = self.msgtime+' Error - '+str(errmsg)
           with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                    self.logfile.write (pline+'\n')
        #
        #  Function to obtain and process plot parameters.
        #

        self.proc_data()



if __name__ == "__main__":
    is_cgi_request = "REQUEST_METHOD" in os.environ
    renderer = TidePlotRenderer(is_cgi_request)
    renderer.run()