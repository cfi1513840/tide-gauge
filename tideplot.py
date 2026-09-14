#!/home/tide/.tidenv/bin/python3
# -*- coding: utf-8 -*-
"""tideplot.py

Renders the historical tide/weather/wind/battery plot page.

Runs in two contexts from this single file:
  - As a CGI script (invoked by Apache, REQUEST_METHOD set in the
    environment): reads request parameters via cgi.FieldStorage() and
    writes the response directly to stdout. Reached both for the
    initial default view and for every custom redraw submitted via
    the page's own form.
  - As a cron job (no REQUEST_METHOD; currently scheduled at
    :01/:21/:41, one minute after tide.py refreshes the database
    copy): always renders the default (iparams.stationid-driven) view
    and publishes it to /var/www/html/tideplot.html as a static page.

This replaces the former separate tideplot.py / tideplot.cgi files,
which had drifted into two independently-maintained copies of the
same logic.

Two classes: Station holds the static, per-station configuration
built once per render (iparams, form parameters); TidePlotRenderer
does the actual drawing.
"""
import time
import sys
import os
from datetime import datetime, date, timedelta, timezone
import sqlite3
import math
import cgi, cgitb
from dataclasses import dataclass, field
from dotenv import load_dotenv, find_dotenv
from suntimes import SunTimes

#
# Function to generate the predicted tide at one minute intervals. The predicted tide
# levels are saved in [predlist] for the requested plot duration based on the NOAA tide tables.
#


@dataclass
class Station:
    """Static, per-station configuration built once per render from iparams
    and the request's form parameters. Used to drive the mechanical,
    structurally-identical per-station work (iparams read, form checkboxes,
    legend, battery queries, min/max battery voltage, grid drawing, and
    vertical layout stacking) via a simple loop instead of separately-named
    per-station variables.

    The deeply time-dependent main trace-drawing loop (tide/variation
    trace with 15-minute gap detection, battery trace with sunrise/sunset
    overlay) intentionally keeps its existing self.station1cal-style
    attributes and if/elif shape rather than looping over this list --
    that logic is stateful across loop iterations in ways that are safer
    to extend by direct analogy (a third branch matching station 2's
    exactly) than to generalize, especially with no prior station-3
    baseline to verify subtle timing edge cases against.
    """
    num: int
    enabled: bool = False
    cal: float = 0.0
    color: str = 'black'
    selected: bool = False      # station{num} form checkbox
    show_battery: bool = False  # batv{num} form checkbox (batv for num==1)
    selected_chk: str = ''
    battery_chk: str = ''
    batv_list: list = field(default_factory=list)
    min_batv: float = float('inf')
    max_batv: float = float('-inf')
    batv_grid_nbr: int = 0
    batv_grid_y: float = 0
    batv_height: float = 0
    batv_y_fact: float = 0
    batv_start_y: int = 0
    batv_end_y: int = 0
    vari_start_y: int = 0
    vari_end_y: int = 0


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
           self.maxpred = float('-inf')
           self.minpred = float('inf')
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
           trend3 = ''
           epochs = []
           tide_average1 = [0 for x in range(0,15)]
           last_average1 = 0
           max_tide1 = float('-inf')
           min_tide1 = float('inf')
           tide_average2 = [0 for x in range(0,15)]
           last_average2 = 0
           max_tide2 = float('-inf')
           min_tide2 = float('inf')
           tide_average3 = [0 for x in range(0,15)]
           last_average3 = 0
           max_tide3 = float('-inf')
           min_tide3 = float('inf')
           new_tide_list = []
           index1 = 0
           index2 = 0
           index3 = 0
           min_tide_time1 = ''
           min_tide_time2 = ''
           min_tide_time3 = ''
           max_tide_time1 = ''
           max_tide_time2 = ''
           max_tide_time3 = ''

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
              elif entry[1] == 3:
                 if entry[2] > max_tide3:
                    max_tide3 = entry[2]
                    max_tide_time3 = entry[0]
                 if entry[2] < min_tide3:
                    min_tide3 = entry[2]
                    min_tide_time3 = entry[0]
                 tide_average3 = tide_average3[1:]+[entry[2]]
                 index3 += 1
              if index1 != 0 and index1 % 15 == 0 and entry[1] == 1:
                 average1 = sum(tide_average1)/len(tide_average1)
                 if last_average1 == 0:
                    last_average1 = average1
                    continue
                 if average1 > last_average1 + 0.05:
                    if trend1 == 'low':
                       epochs.append([min_tide_time1,1,trend1])
                       min_tide1 = float('inf')
                       max_tide1 = float('-inf')                        
                    trend1 = 'high'
                 elif average1 < last_average1 - 0.05:
                    if trend1 == 'high':
                       epochs.append([max_tide_time1,1,trend1])
                       min_tide1 = float('inf')
                       max_tide1 = float('-inf')                            
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
                       min_tide2 = float('inf')
                       max_tide2 = float('-inf')                        
                    trend2 = 'high'
                 elif average2 < last_average2 - 0.05:
                    if trend2 == 'high':
                       epochs.append([max_tide_time2,2,trend2])
                       min_tide2 = float('inf')
                       max_tide2 = float('-inf')                            
                    trend2 = 'low'
                 last_average2 = average2

              elif index3 != 0 and index3 % 15 == 0 and entry[1] == 3:
                 average3 = sum(tide_average3)/len(tide_average3)
                 if last_average3 == 0:
                    last_average3 = average3
                    continue
                 if average3 > last_average3 + 0.05:
                    if trend3 == 'low':
                       epochs.append([min_tide_time3,3,trend3])
                       min_tide3 = float('inf')
                       max_tide3 = float('-inf')                        
                    trend3 = 'high'
                 elif average3 < last_average3 - 0.05:
                    if trend3 == 'high':
                       epochs.append([max_tide_time3,3,trend3])
                       min_tide3 = float('inf')
                       max_tide3 = float('-inf')                            
                    trend3 = 'low'
                 last_average3 = average3

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
           self.outfile.write ('.navbar {\n')
           self.outfile.write ('max-width: 560px;\n')
           self.outfile.write ('margin: 14px auto;\n')
           self.outfile.write ('text-align: center;\n')
           self.outfile.write ('}\n')
           self.outfile.write ('.navbar button {\n')
           self.outfile.write ('font-family: "Arial", "Helvetica", sans-serif;\n')
           self.outfile.write ('font-size: 1em;\n')
           self.outfile.write ('font-weight: bold;\n')
           self.outfile.write ('color: #FFFFFF;\n')
           self.outfile.write ('background-color: #1B3A5C;\n')
           self.outfile.write ('border: 2px solid #000000;\n')
           self.outfile.write ('border-radius: 6px;\n')
           self.outfile.write ('padding: 8px 18px;\n')
           self.outfile.write ('margin: 0 8px;\n')
           self.outfile.write ('cursor: pointer;\n')
           self.outfile.write ('}\n')
           self.outfile.write ('</style>\n')
           self.outfile.write ('</head>\n')
           self.outfile.write ('<body style="background-color:black;">\n')
           self.outfile.write ('<div class="navbar">\n')
           self.outfile.write ('<a href="/index.html"><button type="button">Home</button></a>\n')
           self.outfile.write ('<a href="/alertlogin.html"><button type="button">Request Alerts</button></a>\n')
           self.outfile.write ('<a href="/tide.html"><button type="button">Tide &amp; Weather</button></a>\n')
           self.outfile.write ('</div>\n')
           self.outfile.write (f'<div style="background-color: #E0F8F1; width: {self.canvas_width}px; text-align: center; margin-left: auto; margin-right: auto;">\n') 
           self.outfile.write (f'{self.station_location}<br>')  
           self.outfile.write (f'<form style="background-color: #E0F8F1; width: {self.canvas_width}px; text-align: center; margin-left: auto; margin-right: auto;" id="myForm" action="/cgi-bin/tideplot.cgi" method="post">\n') 
           self.outfile.write ('<label for="endate">End date:</label>\n')
           self.outfile.write (f'<input type="date" name="endate" id="endate" value="{self.formdate}">&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="dayspan">Plot span in days:</label>\n')
           self.outfile.write (f'<input type="number" name="dayspan" id="dayspan" value="{str(self.plotdays)}" step=1 min="1" max="30" required>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<input type="hidden" name="screenwidth" id="screenwidth" value=''/>\n')
           self.outfile.write ('<input type="hidden" name="screenheight" id="screenheight" value=''/>\n')
           # value="..." here is purely cosmetic -- the form-parsing code only
           # checks whether the key is present at all, never its value -- but
           # station1's/station2's existing markup differ (1 vs 0) and are
           # preserved exactly rather than unified. station3 (new) uses "1".
           station_chk_value = {1: '1', 2: '0', 3: '1'}
           batv_chk_value = {1: '1', 2: '0', 3: '1'}
           for s in self.stations:
              if s.enabled:
                 self.outfile.write (f'<label for="station{s.num}">Sensor {s.num}</label>\n')
                 self.outfile.write (f'<input type="checkbox" id="station{s.num}" name="station{s.num}" value="{station_chk_value[s.num]}" {s.selected_chk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="tags">Tide Markers</label>\n')
           self.outfile.write (f'<input type="checkbox" id="tags" name="tags" value="1" {self.tagchk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="wind"> Wind</label>\n')
           self.outfile.write (f'<input type="checkbox" id="wind" name="wind" value="1" {self.windchk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="rain">Rain</label>\n')
           self.outfile.write (f'<input type="checkbox" id="rain" name="rain" value="1" {self.rainchk}>&nbsp&nbsp&nbsp&nbsp\n')
           self.outfile.write ('<label for="temp">Temperature</label>\n')
           self.outfile.write (f'<input type="checkbox" id="temp" name="temp" value="1" {self.tempchk}>&nbsp&nbsp&nbsp&nbsp\n')
           for s in self.stations:
              if s.enabled:
                 field_id = 'batv' if s.num == 1 else f'batv{s.num}'
                 self.outfile.write (f'<label for="{field_id}">BatV {s.num}</label>\n')
                 self.outfile.write (f'<input type="checkbox" id="{field_id}" name="{field_id}" value="{batv_chk_value[s.num]}" {s.battery_chk}>&nbsp&nbsp&nbsp&nbsp\n')
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
              self.outfile.write ('<div class="navbar">\n')
              self.outfile.write ('<a href="/index.html"><button type="button">Home</button></a>\n')
              self.outfile.write ('<a href="/alertlogin.html"><button type="button">Request Alerts</button></a>\n')
              self.outfile.write ('<a href="/tide.html"><button type="button">Tide &amp; Weather</button></a>\n')
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
           #   debugit -= 1

           if self.tidesup:
              starttime = datetime.strptime(self.tidelist[0][0], self.sqltimeformat)
           else:
              starttime = self.dbquerytime
           offtime = starttime.timestamp() - self.dbquerytime.timestamp()
           aidx = 0
           b1idx = 0
           b2idx = 0
           b3idx = 0
           widx = 0
           saidx = -10
           swidx = -10
           pstart = 30
           windcount = 0
           windex = 0
           tideinit = False
           vari1init = False
           vari2init = False
           vari3init = False
           wxinit = False
           rxinit = False
           txinit = False
           vari1start_x = float('-inf')
           vari1start_y = float('-inf')
           vari2start_x = float('-inf')
           vari2start_y = float('-inf')
           vari3start_x = float('-inf')
           vari3start_y = float('-inf')
           tidestart_x = float('-inf')
           tidestart_y = float('-inf')
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
           for s in self.stations:
              if not (s.selected and s.enabled):
                 continue
              self.outfile.write ('ctx.strokeStyle = "black";\n')
              if s.num == 1:
                 self.outfile.write ('ctx.textAlign = "center";\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{s.vari_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{s.vari_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width-1},{s.vari_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width-1},{s.vari_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              gridy = 0
              # station1's original block omitted the +3 label offset that
              # station2's had; preserved here rather than unified, since
              # neither original is being changed. station3 (new) matches
              # station2's version.
              label_offset = 0 if s.num == 1 else 3
              for x in range(0,self.vari_grid_nbr+1):
                 if x == 0 or x == 2 or x == self.vari_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(s.vari_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(s.vari_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText("{str(2-x)}", {self.left_scale_x}, {int(s.vari_start_y+gridy+label_offset)});\n')
                 self.outfile.write (f'ctx.fillText("{str(2-x)}", {self.right_scale_x}, {int(s.vari_start_y+gridy+label_offset)});\n')
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
           for s in self.stations:
              if not (s.show_battery and s.enabled):
                 continue
              gridy = 0
              for x in range(0,s.batv_grid_nbr+1):
                 if x == 0 or x == s.batv_grid_nbr:
                    self.outfile.write ('ctx.strokeStyle = "black";\n')
                 else:
                    self.outfile.write ('ctx.strokeStyle = "gray";\n')
                 self.outfile.write ('ctx.beginPath();\n')
                 self.outfile.write (f'ctx.moveTo({x_start},{int(s.batv_start_y+gridy)});\n')
                 self.outfile.write (f'ctx.lineTo({self.plot_width},{int(s.batv_start_y+gridy)});\n')
                 self.outfile.write ('ctx.stroke();\n')
                 self.outfile.write ('ctx.fillStyle = "black";\n')
                 self.outfile.write (f'ctx.fillText({format(s.max_batv-x*0.05,".2f")}, {self.left_scale_x}, {int(s.batv_start_y+gridy+5)});\n')
                 self.outfile.write (f'ctx.fillText({format(s.max_batv-x*0.05,".2f")}, {self.right_scale_x}, {int(s.batv_start_y+gridy+5)});\n')
                 gridy += s.batv_grid_y
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({x_start},{s.batv_start_y});\n')
              self.outfile.write (f'ctx.lineTo({x_start},{s.batv_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
              self.outfile.write ('ctx.beginPath();\n')
              self.outfile.write (f'ctx.moveTo({self.plot_width},{s.batv_start_y});\n')
              self.outfile.write (f'ctx.lineTo({self.plot_width},{s.batv_end_y});\n')
              self.outfile.write ('ctx.stroke();\n')
           tidelen = len(self.tidelist)
           batv1len = len(self.batv1list)
           batv2len = len(self.batv2list)
           batv3len = len(self.batv3list)
           tidetimenext = 0
           batv1timenext = 0
           batv2timenext = 0
           batv3timenext = 0
           savetime1 = 0
           savex1 = 0
           savey1 = 0
           savetime2 = 0
           savex2 = 0
           savey2 = 0
           savetime3 = 0
           savex3 = 0
           savey3 = 0
           savebatv1time = 0
           savebatv1x = 0
           savebatv1y = 0
           savebatv2time = 0
           savebatv2x = 0
           savebatv2y = 0
           savebatv3time = 0
           savebatv3x = 0
           savebatv3y = 0
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
                 if b1idx < batv1len-1:
                    batv1time = datetime.strptime(self.batv1list[b1idx][0][:16], self.mintimeformat)
                 if b1idx+1 < batv1len-1:
                    batv1timenext = datetime.strptime(self.batv1list[b1idx+1][0][:16], self.mintimeformat)
                 if b2idx < batv2len-1:
                    batv2time = datetime.strptime(self.batv2list[b2idx][0][:16], self.mintimeformat)
                 if b2idx+1 < batv2len-1:
                    batv2timenext = datetime.strptime(self.batv2list[b2idx+1][0][:16], self.mintimeformat)
                 if b3idx < batv3len-1:
                    batv3time = datetime.strptime(self.batv3list[b3idx][0][:16], self.mintimeformat)
                 if b3idx+1 < batv3len-1:
                    batv3timenext = datetime.strptime(self.batv3list[b3idx+1][0][:16], self.mintimeformat)
                 if self.tidesup:
                    while tidetime == predtime_hm and aidx < tidelen-1:
                       if self.station1 and self.s1enable and self.tidelist[aidx][1] == 1:
                          tide_y = self.tide_end_y-int(((self.station1cal-self.tidelist[aidx][2]/12) -math.floor(self.mintide))*self.tide_grid_y)
                          tideft = self.station1cal-self.tidelist[aidx][2]/12
                          varift = tideft-predendft
                          vari_y = self.vari1_end_y-int((varift+2)*self.grid_height)
                          if savetime1 == 0 or tidetime > savetime1 + timedelta(minutes=15):               
                             #outfile.write ('ctx.fillStyle = "blue";\n')
                             #outfile.write (f'ctx.fillRect({tide_x},{tide_y},1,2);\n')
                             pass
                          else:
                             self.outfile.write (f'ctx.strokeStyle = "blue";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({savex1},{savey1});\n')
                             self.outfile.write (f'ctx.lineTo({tide_x},{tide_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')                                    
                          savetime1 = tidetime
                          savex1 = tide_x
                          savey1 = tide_y
                          if predstate == 'L' or predstate == 'H':
                             if self.prestate1 == '':
                                self.prestate1 = predstate
                             elif self.prestate1 != predstate:
                                self.prestate1 = predstate
                                if vari1init:
                                   self.outfile.write (f'ctx.strokeStyle = "blue";\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({vari1start_x},{vari1start_y});\n')
                                   self.outfile.write (f'ctx.lineTo({tide_x},{vari_y});\n')
                                   self.outfile.write (f'ctx.stroke();\n')                                    
                                   vari1start_x = tide_x
                                   vari1start_y = vari_y
                                vari1init = True
                                if vari1start_x == float('-inf'): vari1start_x = tide_x
                                if vari1start_y == float('-inf'): vari1start_y = vari_y                    
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
                                if vari2start_x == float('-inf'): vari2start_x = tide_x
                                if vari2start_y == float('-inf'): vari2start_y = vari_y                                            
                       elif self.station3 and self.s3enable and self.tidelist[aidx][1] == 3:
                          tide_y = self.tide_end_y-int(((self.station3cal-self.tidelist[aidx][2]/12)-math.floor(self.mintide))*self.tide_grid_y)
                          tideft = self.station3cal-self.tidelist[aidx][2]/12
                          varift = tideft-predendft
                          vari_y = self.vari3_end_y-int((varift+2)*self.grid_height)
                          if savetime3 == 0 or tidetime > savetime3 + timedelta(minutes=15):
                             pass
                          else:
                             self.outfile.write (f'ctx.strokeStyle = "brown";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({savex3},{savey3});\n')
                             self.outfile.write (f'ctx.lineTo({tide_x},{tide_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                          savetime3 = tidetime
                          savex3 = tide_x
                          savey3 = tide_y
                          if predstate == 'L' or predstate == 'H':
                             if self.prestate3 == '':
                                self.prestate3 = predstate
                             elif self.prestate3 != predstate:
                                self.prestate3 = predstate
                                if vari3init:
                                   self.outfile.write (f'ctx.strokeStyle = "brown";\n')
                                   self.outfile.write (f'ctx.beginPath();\n')
                                   self.outfile.write (f'ctx.moveTo({vari3start_x},{vari3start_y});\n')
                                   self.outfile.write (f'ctx.lineTo({tide_x},{vari_y});\n')
                                   self.outfile.write (f'ctx.stroke();\n')
                                   vari3start_x = tide_x
                                   vari3start_y = vari_y
                                vari3init = True
                                if vari3start_x == float('-inf'): vari3start_x = tide_x
                                if vari3start_y == float('-inf'): vari3start_y = vari_y
                       aidx += 1
                       if aidx < tidelen-1:
                          tidetime = datetime.strptime(self.tidelist[aidx][0][:16], self.mintimeformat)
                       if aidx+1 < tidelen-1:
                          tidetimenext = datetime.strptime(self.tidelist[aidx+1][0][:16], self.mintimeformat)
                    while tidetimenext < predtimenext and aidx < tidelen-1:
                       aidx += 1
                       if aidx < tidelen-1:
                          tidetimenext = datetime.strptime(self.tidelist[aidx][0][:16], self.mintimeformat)

                 if self.s1enable and self.batv1 and len(self.batv1list) != 0:
                    if batv1time == predtime_hm:
                       batv_y = self.batv1_end_y-int((self.batv1list[b1idx][1]-self.minbatv1)*self.batv1_y_fact)
                       if savebatv1time == 0 or predtime_hm > savebatv1time + timedelta(minutes=15):               
                          #outfile.write ('ctx.fillStyle = "black";\n')
                          #outfile.write (f'ctx.fillRect({tide_x},{batv_y},1,2);\n')
                          pass
                       else:
                          self.outfile.write (f'ctx.strokeStyle = "black";\n')
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({savebatv1x},{savebatv1y});\n')
                          self.outfile.write (f'ctx.lineTo({tide_x},{batv_y});\n')
                          self.outfile.write (f'ctx.stroke();\n')                                    
                          if str(predtime_hm) == self.localsunrise:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv1_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv1_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv1_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                          elif str(predtime_hm) == self.localsunset:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv1_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv1_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv1_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                       savebatv1time = batv1time
                       savebatv1x = tide_x
                       savebatv1y = batv_y                  
                       b1idx += 1
                    else:
                       while batv1timenext < predtimenext and b1idx < batv1len-1:
                          b1idx += 1
                          if b1idx < batv1len-1:
                             batv1timenext = datetime.strptime(self.batv1list[b1idx][0][:16], self.mintimeformat)

                 if self.s2enable and self.batv2 and len(self.batv2list) != 0:
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

                 if self.s3enable and self.batv3 and len(self.batv3list) != 0:
                    if batv3time == predtime_hm:
                       batv3_y = self.batv3_end_y-int((self.batv3list[b3idx][1]-self.minbatv3)*self.batv3_y_fact)
                       if savebatv3time == 0 or predtime_hm > savebatv3time + timedelta(minutes=15):
                          pass
                       else:
                          self.outfile.write (f'ctx.strokeStyle = "black";\n')
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({savebatv3x},{savebatv3y});\n')
                          self.outfile.write (f'ctx.lineTo({tide_x},{batv3_y});\n')
                          self.outfile.write (f'ctx.stroke();\n')
                          if str(predtime_hm) == self.localsunrise:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv3_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv3_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv3_start_y+10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                          elif str(predtime_hm) == self.localsunset:
                             self.outfile.write (f'ctx.strokeStyle = "orange";\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_start_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx},{self.batv3_end_y});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx-10},{self.batv3_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                             self.outfile.write (f'ctx.beginPath();\n')
                             self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_end_y});\n')
                             self.outfile.write (f'ctx.lineTo({predstartx+10},{self.batv3_end_y-10});\n')
                             self.outfile.write (f'ctx.stroke();\n')
                       savebatv3time = batv3time
                       savebatv3x = tide_x
                       savebatv3y = batv3_y
                       b3idx += 1
                    else:
                       while batv3timenext < predtimenext and b3idx < batv3len-1:
                          b3idx += 1
                          if b3idx < batv3len-1:
                             batv3timenext = datetime.strptime(self.batv3list[b3idx][0][:16], self.mintimeformat)

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
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.vari1_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.vari1_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.station2:
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.vari2_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.vari2_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.station3:
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.vari3_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.vari3_end_y});\n')
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
                 if self.s1enable and self.batv1:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.batv1_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.batv1_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.s2enable and self.batv2:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.batv2_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.batv2_end_y});\n')
                    self.outfile.write (f'ctx.stroke();\n')
                 if self.s3enable and self.batv3:
                    self.outfile.write (f'ctx.beginPath();\n')
                    self.outfile.write (f'ctx.moveTo({predstartx},{self.batv3_start_y});\n')
                    self.outfile.write (f'ctx.lineTo({predstartx},{self.batv3_end_y});\n')
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
                          if self.turntime1 == '' or abs(hourtime-self.turntime1) >= 3:
                             self.turntime1 = hourtime
                             peak = format(self.station1cal-ent[2]/12,'.1f')
                             peaks = peak+' '+hrmin
                             # High tide tags sit one grid height (30px) lower
                             # than low tide tags so they clear the tide trace
                             # near its peak; low tide tags are unaffected.
                             # _get_epochs() labels are inverted relative to
                             # actual tide height (it tracks raw sensor distance,
                             # which is inversely related to water level): the
                             # actual HIGH tide peak is tagged 'low', and the
                             # actual LOW tide trough is tagged 'high'. Verified
                             # directly against real calibrated peak values, not
                             # assumed from the label name.
                             high_shift = 30 if tidestate == 'low' else 0
                             self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                             self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y-19+high_shift}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y-19+high_shift}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillStyle = "blue";\n')
                             self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y+9+high_shift});\n')
                             self.outfile.write (f'ctx.fillText("{peak} ft", {startx}, {self.tag_y-6+high_shift});\n')
                    if self.s2enable and self.station2 and ent[1] == 2:
                       tidestate = str(ent[3])
                       if tidestate == 'low' or tidestate == 'high':
                          if self.turntime2 == '' or abs(hourtime-self.turntime2) >= 3:
                             self.turntime2 = hourtime
                             peak = format(self.station2cal-ent[2]/12,'.1f')
                             peaks = peak+' '+hrmin
                             # _get_epochs() labels are inverted relative to
                             # actual tide height (it tracks raw sensor distance,
                             # which is inversely related to water level): the
                             # actual HIGH tide peak is tagged 'low', and the
                             # actual LOW tide trough is tagged 'high'. Verified
                             # directly against real calibrated peak values, not
                             # assumed from the label name.
                             high_shift = 30 if tidestate == 'low' else 0
                             self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                             self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y-51+high_shift}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y-51+high_shift}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillStyle = "darkgreen";\n')
                             self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y-23+high_shift});\n')
                             self.outfile.write (f'ctx.fillText("{peak} ft", {startx}, {self.tag_y-38+high_shift});\n')
                    if self.s3enable and self.station3 and ent[1] == 3:
                       tidestate = str(ent[3])
                       if tidestate == 'low' or tidestate == 'high':
                          if self.turntime3 == '' or abs(hourtime-self.turntime3) >= 3:
                             self.turntime3 = hourtime
                             peak = format(self.station3cal-ent[2]/12,'.1f')
                             peaks = peak+' '+hrmin
                             # _get_epochs() labels are inverted relative to
                             # actual tide height (it tracks raw sensor distance,
                             # which is inversely related to water level): the
                             # actual HIGH tide peak is tagged 'low', and the
                             # actual LOW tide trough is tagged 'high'. Verified
                             # directly against real calibrated peak values, not
                             # assumed from the label name.
                             high_shift = 30 if tidestate == 'low' else 0
                             self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                             self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y-83+high_shift}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y-83+high_shift}, 42, 30);\n')
                             self.outfile.write (f'ctx.fillStyle = "brown";\n')
                             self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y-55+high_shift});\n')
                             self.outfile.write (f'ctx.fillText("{peak} ft", {startx}, {self.tag_y-70+high_shift});\n')
                 except Exception as errmsg:
                    pline = self.msgtime+' Error - '+str(errmsg)
                    with open('/var/www/html/tideplot.log', 'a') as self.logfile:
                       self.logfile.write (pline+'\n')
        #
        # Create Dashed vertical lines and if tags also create Predicted High and Low Tide Annotation
        #
           self.prestate1 = ''
           for pidx, ent in enumerate(self.predlist):
              if pidx == 0:
                 startx = pstart+ent[1]*(self.plot_width-30)/86400/self.plotdays
                 #starty = tide_end_y-int((ent[2]+2)*grid_height)
                 self.prestate1 = ent[3]
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
                 if self.prestate1 == '':
                    self.prestate1 = predstate
                 elif self.prestate1 != predstate:
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
                       dash_end_y = self.vari1_start_y
                       while dash_end_y < self.vari1_end_y:
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                          if dash_end_y+dash_size > self.vari1_end_y:
                             self.outfile.write (f'ctx.lineTo({endx},{self.vari1_end_y});\n')
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
                    if self.s3enable and self.station3:
                       dash_end_y = self.vari3_start_y
                       while dash_end_y < self.vari3_end_y:
                          self.outfile.write (f'ctx.beginPath();\n')
                          self.outfile.write (f'ctx.moveTo({endx},{dash_end_y});\n')
                          if dash_end_y+dash_size > self.vari3_end_y:
                             self.outfile.write (f'ctx.lineTo({endx},{self.vari3_end_y});\n')
                          else:
                             self.outfile.write (f'ctx.lineTo({endx},{dash_end_y+dash_size});\n')
                          self.outfile.write (f'ctx.stroke();\n')
                          dash_end_y += dash_size*2
                    self.prestate1 = predstate
                    if self.tags:                  
                       # Same high/low split as the measured tags: predicted
                       # high tide tags sit one grid height (30px) lower than
                       # predicted low tide tags so they clear the trace near
                       # its peak. Note: predstate=='L' is empirically the
                       # state associated with the HIGH tide value at this
                       # render point (and 'H' with the low value) -- verified
                       # directly against ent[2] across many samples, not
                       # assumed from the variable name.
                       high_shift = 30 if predstate == 'L' else 0
                       self.outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                       self.outfile.write (f'ctx.strokeRect({startx-21}, {self.tag_y+13+high_shift}, 42, 30);\n')
                       self.outfile.write (f'ctx.fillRect({startx-21}, {self.tag_y+13+high_shift}, 42, 30);\n')
                       self.outfile.write (f'ctx.fillStyle = "gray";\n')
                       self.outfile.write (f'ctx.fillText("{peak} ft", {startx}, {self.tag_y+27+high_shift});\n')
                       self.outfile.write (f'ctx.fillText("{hrmin}", {startx}, {self.tag_y+42+high_shift});\n')
                 startx = endx
                 #starty = endy
           self.outfile.write (f'ctx.strokeStyle = "blue";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5-60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5-30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5+30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5+60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.strokeStyle = "darkgreen";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5*2-60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5*2-30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5*2+30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5*2+60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.strokeStyle = "brown";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5*3-60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5*3-30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5*3+30},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5*3+60},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.strokeStyle = "gray";\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5*4-70},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5*4-40},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write (f'ctx.beginPath();\n')
           self.outfile.write (f'ctx.moveTo({self.plot_width/5*4+40},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.lineTo({self.plot_width/5*4+70},{self.tide_start_y-10});\n')
           self.outfile.write (f'ctx.stroke();\n')
           self.outfile.write ('ctx.textAlign = "center";\n')
           self.outfile.write ('ctx.font = "14px Arial";\n')
           self.outfile.write ('ctx.fillStyle = "blue";\n')
           self.outfile.write (f'ctx.fillText("Sensor 1", {self.plot_width/5}, {self.tide_start_y-4});\n')
           self.outfile.write ('ctx.fillStyle = "darkgreen";\n')
           self.outfile.write (f'ctx.fillText("Sensor 2", {self.plot_width/5*2}, {self.tide_start_y-4});\n')
           self.outfile.write ('ctx.fillStyle = "brown";\n')
           self.outfile.write (f'ctx.fillText("Sensor 3", {self.plot_width/5*3}, {self.tide_start_y-4});\n')
           if not self.tidesup and self.banflag == '1':
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("{self.banner}", {self.plot_width/2}, {self.tide_end_y-10});\n')      
           self.outfile.write ('ctx.fillStyle = "gray";\n')
           self.outfile.write (f'ctx.fillText("Predicted", {self.plot_width/5*4}, {self.tide_start_y-4});\n')
           if self.s1enable and self.station1:
              self.outfile.write ('ctx.fillStyle = "blue";\n')
              self.outfile.write (f'ctx.fillText("Variation between Sensor 1 and predicted tide in feet", {self.plot_width/2}, {self.vari1_start_y-4});\n')
           if self.s2enable and self.station2:
              self.outfile.write ('ctx.fillStyle = "darkgreen";\n')
              self.outfile.write (f'ctx.fillText("Variation between Sensor 2 and predicted in feet", {self.plot_width/2}, {self.vari2_start_y-4});\n')
           if self.s3enable and self.station3:
              self.outfile.write ('ctx.fillStyle = "brown";\n')
              self.outfile.write (f'ctx.fillText("Variation between Sensor 3 and predicted in feet", {self.plot_width/2}, {self.vari3_start_y-4});\n')
           if self.wind:   
              self.outfile.write ('ctx.fillStyle = "purple";\n')
              self.outfile.write (f'ctx.fillText("Wind speed (mph) and direction (arrow indicates wind direction relative to north)", {self.plot_width/2}, {self.windir_start_y-4});\n')
           if self.rain:      
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("Daily rainfall in inches", {self.plot_width/2}, {self.rain_start_y-4});\n')                          
           if self.temp:      
              self.outfile.write ('ctx.fillStyle = "red";\n')
              self.outfile.write (f'ctx.fillText("Temperature in degrees F", {self.plot_width/2}, {self.temp_start_y-4});\n')                          
           if self.s1enable and self.batv1:      
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("Sensor 1 Battery Voltage", {self.plot_width/2}, {self.batv1_start_y-4});\n')                          
           if self.s2enable and self.batv2:      
              self.outfile.write (f'ctx.fillText("Sensor 2 Battery Voltage", {self.plot_width/2}, {self.batv2_start_y-4});\n')                          
           if self.s3enable and self.batv3:
              self.outfile.write ('ctx.fillStyle = "black";\n')
              self.outfile.write (f'ctx.fillText("Sensor 3 Battery Voltage", {self.plot_width/2}, {self.batv3_start_y-4});\n')
           self.outfile.write ('</script>\n')
           self.outfile.write ('</div>\n')
           self.outfile.write ('<div class="navbar">\n')
           self.outfile.write ('<a href="/index.html"><button type="button">Home</button></a>\n')
           self.outfile.write ('<a href="/alertlogin.html"><button type="button">Request Alerts</button></a>\n')
           self.outfile.write ('<a href="/tide.html"><button type="button">Tide &amp; Weather</button></a>\n')
           self.outfile.write ('</div>\n')
           self.outfile.write ('</body>\n')
           self.outfile.write ('</html>\n')
           if not self.is_cgi_request:
              self.outfile.close()
              os.system(f'mv {self.filetag} /var/www/html/tideplot.html')


    def run(self):
        self.curtime = datetime.now()
        self.msgtime = str(self.curtime)[:-10]

        # Mode detection: Apache sets REQUEST_METHOD for every CGI invocation; it is
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
        self.station3 = False
        self.wind = False
        self.rain = False
        self.temp = False
        default_station_id = 1
        #
        # Get station name for webpage title
        #
        envfile = find_dotenv(os.path.join(
          os.path.dirname(os.path.realpath(__file__)), 'tide.env'))
        if load_dotenv(envfile):
           self.station_location = os.getenv('STATION_LOCATION')
           station_latitude = os.getenv('STATION_LATITUDE')
           station_longitude = os.getenv('STATION_LONGITUDE')
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
           iparams = self.sqlcur.fetchone()
           # The active station is defined by iparams.stationid, the same
           # column tide.py and the rest of the site use -- not a separate
           # tideplot-specific setting, so the two can never drift apart.
           default_station_id = iparams[0]
           #banflag = iparams[2]
           #banner = iparams[3]
           self.station1cal = iparams[5]
           self.station2cal = iparams[6]
           self.s1enable = iparams[7]
           self.s2enable = iparams[8]
           self.station3cal = iparams[11]
           self.s3enable = iparams[12]
           # s3type (iparams[13]) governs tide.py's own sensor transport
           # selection (LoRa vs Notecard) and has no bearing on plotting
           # already-stored rows, so it is intentionally not read here --
           # matching s1type/s2type, which were never used in this file either.
           #
           # A station with s{n}enable set but no calibration value configured
           # (station{n}cal left NULL, e.g. right after the column was added
           # and before it was ever set) can't actually be used -- treat it as
           # disabled rather than crashing later when None is subtracted from
           # a float in the tide-level calculation.
           if self.station1cal is None:
              self.s1enable = False
           if self.station2cal is None:
              self.s2enable = False
           if self.station3cal is None:
              self.s3enable = False
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
              # default (iparams.stationid-driven) view, matching prior tideplot.py behavior.
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
              self.station3 = (default_station_id == 3)
              self.station3chk = 'checked' if self.station3 else ''
              self.wind = True
              self.windchk = 'checked'
              self.rain = True
              self.rainchk = 'checked'
              self.temp = True
              self.tempchk = 'checked'
              self.batv1 = (default_station_id == 1)
              self.batv1chk = 'checked' if self.batv1 else ''
              self.batv2 = (default_station_id == 2)
              self.batv2chk = 'checked' if self.batv2 else ''
              self.batv3 = (default_station_id == 3)
              self.batv3chk = 'checked' if self.batv3 else ''
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
              self.station3 = form.getvalue('station3')
              if self.station3 == None:
                 self.station3 = False
                 self.station3chk = ''
              else:
                 self.station3 = True
                 self.station3chk = 'checked'
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
              self.batv1 = form.getvalue('batv')
              if self.batv1 == None:
                 self.batv1 = False
                 self.batv1chk = ''
              else:
                 self.batv1 = True
                 self.batv1chk = 'checked'
              self.batv2 = form.getvalue('batv2')
              if self.batv2 == None:
                 self.batv2 = False
                 self.batv2chk = ''
              else:
                 self.batv2 = True
                 self.batv2chk = 'checked'
              self.batv3 = form.getvalue('batv3')
              if self.batv3 == None:
                 self.batv3 = False
                 self.batv3chk = ''
              else:
                 self.batv3 = True
                 self.batv3chk = 'checked'
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
           self.prestate1 = ''
           self.prestate2 = ''
           self.prestate3 = ''
           self.predicts = []
           self.turntime1 = ''
           self.turntime2 = ''
           self.turntime3 = ''
           # Built once, from the now-fully-determined per-station attributes
           # above, for the mechanical per-station work that follows (battery
           # queries, min/max battery voltage, grid drawing, layout stacking).
           # The main trace-drawing loop further below keeps using the
           # self.station1cal-style attributes directly -- see the Station
           # class docstring for why.
           self.stations = [
              Station(1, self.s1enable, self.station1cal, 'blue',
                      self.station1, self.batv1, self.station1chk, self.batv1chk),
              Station(2, self.s2enable, self.station2cal, 'darkgreen',
                      self.station2, self.batv2, self.station2chk, self.batv2chk),
              Station(3, self.s3enable, self.station3cal, 'brown',
                      self.station3, self.batv3, self.station3chk, self.batv3chk),
           ]
           self.tide_predict()
           self.tidelist = []
           self.batv1list= []
           self.batv2list = []
           self.batv3list = []
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
              self.station3 = False
              self.canvas_height = 400
              self.proc_data()
              exit()

           if self.s1enable:
              self.sqlcur.execute("select dtime, batv from sensors where stationid = 1 and dtime "+ \
                            "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
              self.batv1list = self.sqlcur.fetchall()
           if self.s2enable:   
              self.sqlcur.execute("select dtime, batv from sensors where stationid = 2 and dtime "+ \
                            "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
              self.batv2list = self.sqlcur.fetchall()
           if self.s3enable:
              self.sqlcur.execute("select dtime, batv from sensors where stationid = 3 and dtime "+ \
                            "between ? and ? order by dtime", (str(self.dbquerytime),str(self.curtime)))
              self.batv3list = self.sqlcur.fetchall()
           for s in self.stations:
              s.batv_list = {1: self.batv1list, 2: self.batv2list, 3: self.batv3list}[s.num]

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
           maxtide = float('-inf')
           self.mintide = float('inf')
           self.minbatv1 = float('inf')
           self.maxbatv1 = float('-inf')
           self.minbatv2 = float('inf')
           self.maxbatv2 = float('-inf')
           minwind = float('inf')
           maxwind = float('-inf')
           self.mintemp = float('inf')
           maxtemp = float('-inf')
           minrain = float('inf')
           maxrain = float('-inf')
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
              # Per-station min/max tide level, tracked as a pure reduction
              # (no time-ordering dependency, so safe to generalize over
              # self.stations rather than duplicating this block a third
              # time) then merged into the overall self.mintide/maxtide the
              # rest of the layout math actually reads.
              station_mintide = {s.num: float('inf') for s in self.stations}
              station_maxtide = {s.num: float('-inf') for s in self.stations}
              for chkent in self.tidelist:
                 for s in self.stations:
                    if s.selected and s.enabled and chkent[1] == s.num:
                       self.tidelevel = s.cal - chkent[2]/12
                       if self.tidelevel > station_maxtide[s.num]:
                          station_maxtide[s.num] = self.tidelevel
                       if self.tidelevel < station_mintide[s.num]:
                          station_mintide[s.num] = self.tidelevel
                       break
              for s in self.stations:
                 if station_mintide[s.num] == float('inf') or station_maxtide[s.num] == float('-inf'):
                    s.selected = False
                    setattr(self, f'station{s.num}', False)
                 else:
                    if station_mintide[s.num] < self.mintide:
                       self.mintide = station_mintide[s.num]
                    if station_maxtide[s.num] > maxtide:
                       maxtide = station_maxtide[s.num]
              #with open('/var/www/html/tideplot.log', 'a') as logfile:
              #   logfile.write ('mintide: '+str(self.mintide)+'\n')
              #   logfile.write ('maxtide: '+str(maxtide)+'\n')
           # Same pure-reduction pattern as the tide min/max above.
           for s in self.stations:
              if len(s.batv_list) != 0 and s.enabled:
                 for chkent in s.batv_list:
                    if chkent[1] != None and chkent[1] < 4.3 and chkent[1] > 2.5:
                       if chkent[1] > s.max_batv:
                          s.max_batv = chkent[1]
                       if chkent[1] < s.min_batv:
                          s.min_batv = chkent[1]
                 if s.min_batv == float('inf') or s.max_batv == float('-inf'):
                    s.show_battery = False
                    setattr(self, f'batv{s.num}', False)
                 else:
                    minbatv1 = int(s.min_batv/0.05)
                    s.min_batv = round(minbatv1*0.05,2)
                    maxbatv1 = int(s.max_batv/0.05)
                    s.max_batv = round(maxbatv1*0.05+0.05,2)
              else:
                 s.show_battery = False
                 setattr(self, f'batv{s.num}', False)
              # Mirrored into the legacy self.minbatv-style attributes the
              # main trace-drawing loop below still reads directly.
              setattr(self, f'minbatv{s.num}', s.min_batv)
              setattr(self, f'maxbatv{s.num}', s.max_batv)

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
              if self.mintemp == float('inf') or maxtemp == float('-inf'):
                  self.temp = False
              if minrain == float('inf') or maxrain == float('-inf'):
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
           for s in self.stations:
              if s.selected and s.enabled:
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
           for s in self.stations:
              if s.show_battery and s.enabled:
                 s.batv_grid_nbr = round((s.max_batv-s.min_batv)/0.05)
                 total_grids += s.batv_grid_nbr
                 nbr_gaps += 1
                 batv_grid_span = round(s.max_batv-s.min_batv,2)
                 s.batv_height = s.batv_grid_nbr*self.grid_height
                 s.batv_grid_y = round(s.batv_height/s.batv_grid_nbr,3)
                 s.batv_y_fact = s.batv_height/batv_grid_span
                 # Mirrored into the legacy self.batv_y_fact-style attribute
                 # the main trace-drawing loop below still reads directly.
                 setattr(self, f'batv{s.num}_y_fact', s.batv_y_fact)

           dtime_height = 10
           gap_size = 30
           dtime_height = 35
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
           for s in self.stations:
              s.vari_start_y = 0
              s.vari_end_y = 0
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
           for s in self.stations:
              if s.selected and s.enabled:
                 s.vari_start_y = next_y+gap_size
                 s.vari_end_y = int(vari_height+s.vari_start_y)
                 next_y = s.vari_end_y
                 # Mirrored into the legacy self.vari_start_y-style attribute
                 # the main trace-drawing loop below still reads directly.
                 setattr(self, f'vari{s.num}_start_y', s.vari_start_y)
                 setattr(self, f'vari{s.num}_end_y', s.vari_end_y)
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
           for s in self.stations:
              if s.show_battery and s.enabled:
                 s.batv_start_y = next_y+gap_size
                 s.batv_end_y = int(s.batv_height+s.batv_start_y)
                 next_y = s.batv_end_y
                 # Mirrored into the legacy self.batv_start_y-style attribute
                 # the main trace-drawing loop below still reads directly.
                 setattr(self, f'batv{s.num}_start_y', s.batv_start_y)
                 setattr(self, f'batv{s.num}_end_y', s.batv_end_y)
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
