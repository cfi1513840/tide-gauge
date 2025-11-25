#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File: tidehtml.py
Author: K. Howell
Version: 1.0
Date: 2025-05-11
Description:
Create HTML file for Internet display of tide station data and weather
"""
import os, sys
import cgi
import time
import subprocess
from datetime import datetime
from datetime import timedelta
import sqlite3
import math
import re
from pytz import timezone
import logging
from dotenv import load_dotenv, find_dotenv

class CreateHTML:
    def __init__(self, cons, tide_only):
        self.cons = cons
        self.tide_only = tide_only
        self.html_directory = self.cons.HTML_DIRECTORY
        self.plotspan = 24
        self.offtime = 0
        self.lastidetime = 0
        self.lastidesams = [0 for x in range(0,5)]
        self.samcnt = 0
        self.wxexit = ''
        envfile = find_dotenv('/var/www/html/tide.env')
        if load_dotenv(envfile):
            self.NDBC_URL = os.getenv('NDBC_URL')
            self.WX_UND_URL = os.getenv('WX_UND_URL')
            self.STATION_NAME = os.getenv('STATION_NAME')
            self.NOAA_STATION_NAME = os.getenv('NOAA_STATION_NAME')

    def create(self, weather, ndbcdata, predicts, tidelist, iparams, sensor):
        self.wxexit = ''
        currentdata = []
        reform = []
        timeformat = "%Y-%m-%d %H:%M:%S"
        current_time = datetime.now()
        hrtime = datetime.strftime(current_time, "%H:%M")
        minute = datetime.strftime(current_time, "%M")
        filetag = "tides"+datetime.strftime(current_time, "%y%m%d%H%M%S")+".tmp"
        outfile = open(filetag, "w")    
        #outfile = open('tidetest.html', "w")    
        then = current_time - timedelta(hours=self.plotspan)
        predtime = current_time - timedelta(hours=self.plotspan+8)
        #
        # Initialize processing parameters
        #
        activechan = iparams['stationid']
        station1cal = iparams['station1cal']
        station2cal = iparams['station2cal']
        banner = iparams['alertmsg']
        sunrise = iparams['sunrise']
        sunset = iparams['sunset']
        dispdate = iparams['dispdate']
        banflag = iparams['banflag']
        batv = 0
        solarv = 0
        rssi = 0
        ndbc_currency = 0
        if sensor:
            if 'V' in sensor: batv = sensor['V']
            if 's' in sensor: solarv = sensor['s']
            if 'P' in sensor: rssi = sensor['P']
        #
        # Extract NDBC dictionary data
        #
        ndbc_wind_f = 0
        ndbc_gust_f = 0
        ndbc_wave_f = 0
        timecheck = 0
        ndbc_time = 0
        ndbc_location = 0
        ndbc_wind = 0
        ndbc_wind_direction = 0
        ndbc_gust = 0
        ndbc_wave_height = 0
        ndbc_wave_period = 0
        ndbc_air_temp = 0
        ndbc_water_temp = 0
        ndbc_wave_direction = 0
        ndbc_baro = 0
        #print (ndbcdata)
        if ndbcdata and not self.tide_only:
            if 'DateTime' in ndbcdata:
                ndbc_time = ndbcdata['DateTime']
                timecheck = datetime.strptime(ndbc_time,'%b %d, %Y %H:%M')
            if 'Location' in ndbcdata:
                ndbc_location = ndbcdata['Location']
            if 'Wind Speed' in ndbcdata:
                ndbc_wind = ndbcdata['Wind Speed']
            if 'Wind Direction' in ndbcdata:
                ndbc_wind_direction = ndbcdata['Wind Direction']
            if 'Wind Gust' in ndbcdata:
                ndbc_gust = ndbcdata['Wind Gust']
            if 'Wave Height' in ndbcdata:
                ndbc_wave_height = ndbcdata['Wave Height']+ ' ft'
            if 'Wave Period' in ndbcdata:
                ndbc_wave_period = ndbcdata['Wave Period']+ ' secs'
            if 'Air Temperature' in ndbcdata:
                ndbc_air_temp = ndbcdata['Air Temperature']+ '&deg; F'
            if 'Water Temperature' in ndbcdata:
                ndbc_water_temp = ndbcdata['Water Temperature']+ '&deg; F'
            if 'Wave Direction' in ndbcdata:
                ndbc_wave_direction = ndbcdata['Wave Direction']
            if 'Atmospheric Pressure' in ndbcdata:
                ndbc_baro = ndbcdata['Atmospheric Pressure']
            ndbc_currency = 2
            if current_time < timecheck+timedelta(minutes=300):
                if current_time >= timecheck+timedelta(minutes=150):
                    ndbc_currency = 1
                else:
                    ndbc_currency = 0
                try:
                    ndbc_time = datetime.strftime(timecheck,'%b %d, %Y %H:%M')
                    if ndbc_wind != 0:
                        ndbc_wind_f = float(ndbc_wind)
                        ndbc_wind = ndbc_wind_direction+' '+ndbc_wind
                    if ndbc_gust != 0:
                        ndbc_gust_f = float(ndbc_gust)
                    if ndbc_wave_height != 0:
                        ndbc_wave_f = float(ndbc_wave_height)
                except:
                    logging.info('Error processing NDBC wind parameters')
            ndbc_wind = ndbc_wind+' kts'
            ndbc_gust = ndbc_gust+' kts'
        #
        # Extract weather dictionary data
        #
        if weather and not self.tide_only:
            #print (weather)
            temperature = 0
            humidity = 0
            baro = 0
            wind_speed = 0
            wind_gust = 0
            baro_trend = 0
            dewpoint = 0
            rain_rate = 0
            rain_today = 0
            obs_time  = ''
            wind_direction_symbol = ''
            if 'obs_time' in weather:
                obs_time = weather['obs_time']
            if 'temperature' in weather:
                temperature = str(int(weather['temperature']))+'&deg; F'
            if 'humidity' in weather:
                humidity = str(weather['humidity'])+'&percnt;'
            if 'baro' in weather:
                baro = weather['baro']
            if 'wind_speed' in weather:
                wind_speed = weather['wind_speed']
            if 'wind_gust' in weather:
                wind_gust = weather['wind_gust']
            if 'baro_trend' in weather:
                baro_trend = weather['baro_trend']
            if 'dewpoint' in weather:
                dewpoint = str(weather['dewpoint'])+'&deg; F'
            if 'rain_rate' in weather:
                rain_rate = weather['rain_rate']
            if 'rain_today' in weather:
                rain_today = weather['rain_today']
            if 'wind_direction_symbol' in weather:
                wind_direction_symbol = weather['wind_direction_symbol']+' '
            if wind_gust == 0 and wind_speed != 0:
                wind_gust = wind_speed
            if baro_trend != 0 and baro_trend < -0.01:
                baro = '&darr; '+str(baro)+' &darr;'
            elif baro_trend != 0 and baro_trend > 0.01:
                baro = '&uarr; '+str(baro)+' &uarr;'   
            #if wind_gust < wind_speed+4 and wind_gust > wind_speed-4:
            #    wind_gust = '--'
            #else:
            if wind_gust != 0:
                wind_gust = str(wind_gust)+" mph"
            if wind_speed != 0:
                wind_speed = wind_direction_symbol+str(wind_speed)+" mph"
            
        # Check for minimum and maximum tide levels and get
        # current time and tide level from last tidelist entry
        #
        curtime = str(current_time)[:-10]
        max_tide = -99
        min_tide = 99
        tide = '--'
        offtime = 0
        if tidelist:
            for chkent in tidelist:
                if chkent[1] > max_tide:
                    max_tide = chkent[1]
                if chkent[1] < min_tide:
                    min_tide = chkent[1]
            starttime = datetime.strptime(tidelist[0][0], timeformat)
            offtime = starttime.timestamp() - then.timestamp()   
            tide = tidelist[len(tidelist)-1][1]
            tide = round(tide,2)
        if predicts:
            for chkent in predicts:
                if chkent[2] > max_tide:
                    max_tide = chkent[2]
                if chkent[2] < min_tide:
                    min_tide = chkent[2]
       #print ('len(tidelist)=',len(tidelist),'max_tide=',max_tide,'min_tide=',min_tide)
        top_marg = 30
        bot_marg = 35
        plot_start_y = 30
        canvas_width = 1200
        mid_tide = round((max_tide-min_tide)/2+min_tide,1)
        min_y = int(round(min_tide-0.5,0))
        max_y = int(round(max_tide+0.5,0))
        y_divs = int((max_y-min_y))
        canvas_height = int(canvas_width/24*y_divs)
        plot_height = canvas_height-(top_marg+bot_marg)
        plot_base = plot_height+top_marg
        y_grid_size = round(plot_height/y_divs,2)
        midy = int(plot_height-(mid_tide)*y_grid_size)
        outfile.write ('ctx.globalCompositeOperation = "source-over";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
        midcanvas = int(plot_height/2+bot_marg)
        bored = 25
        plot_width = canvas_width-40
        plotsecs = plot_width/(self.plotspan*3600)/2
        canw_str = str(canvas_width)
        x_start = bored+(offtime*plotsecs)    
        outfile.write ("Content-type:text/html\r\n\r\n\r\n")
        outfile.write ('<html>\n')
        outfile.write ('<head>\n')
        outfile.write (f'<title>{self.cons.STATION_LOCATION} Tides</title>\n')
        outfile.write ('<meta http-equiv="refresh" content="300" />\n')
        outfile.write ('<style>\n')
        outfile.write ('div {\n')
        outfile.write (f'width: {canw_str}px;\n')
        outfile.write ('margin-left: auto;\n')
        outfile.write ('margin-right: auto;\n')
        outfile.write ('}\n')
        outfile.write ('table {\n')
        outfile.write (f'width: {canw_str}px;\n')
        outfile.write ('border-collapse: collapse;\n')
        outfile.write ('margin-left: auto;\n')
        outfile.write ('margin-right: auto;\n')
        outfile.write ('}\n')
        outfile.write ('td {\n')
        outfile.write ('border: 2px solid Black;\n')
        outfile.write ('}\n')
        outfile.write ('td.special {\n')
        outfile.write ('border: 1px solid #ccffff;\n')
        outfile.write ('}\n')
        outfile.write ('img {\n')
        outfile.write (f'width: 100%;\n')
        outfile.write ('display: block;\n')
        outfile.write ('}\n')
        outfile.write ('td.gif {\n')
        outfile.write (f'text-align: left; vertical-align:top;\n')
        outfile.write (f'width: 600px; height: 500px;\n')
        outfile.write (f'color: black; background-color: snow;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt;\n')
        outfile.write ('}\n')
        outfile.write ('td.day {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: black; background-color: snow;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt;\n')
        outfile.write ('}\n')
        outfile.write ('td.night {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: black; background-color: lightgray;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt;\n')
        outfile.write ('}\n')
        outfile.write ('td.day-name {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: black; background-color: snow;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt; font-weight: bold;\n')
        outfile.write ('}\n')
        outfile.write ('td.night-name {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: black; background-color: lightgray;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt; font-weight: bold;\n')
        outfile.write ('}\n')
        outfile.write ('td.day-temp {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: red; background-color: snow;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt; font-weight: bold;\n')
        outfile.write ('}\n')
        outfile.write ('td.night-temp {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: blue; background-color: lightgray;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 11pt; font-weight: bold;\n')
        outfile.write ('}\n')
        outfile.write ('td.day-time {\n')
        outfile.write (f'text-align: center;\n')
        outfile.write (f'width: 10%;\n')
        outfile.write (f'color: black; background-color: snow;\n')
        outfile.write (f'border: 1px solid black;\n')
        outfile.write (f'font-size: 14pt; font-weight: bold;\n')
        outfile.write ('}\n')
        outfile.write ('form {\n')
        outfile.write ("font-size: 12pt; font-family: 'Arial', 'Helvetica', sans-serif;\n")
        outfile.write ('font-weight: bold; color: #000000; text-align: center;\n')
        outfile.write ('text-indent: 0px;\n')
        outfile.write ('padding: 0px; margin: 0px;\n')  
        outfile.write ('}\n')
        outfile.write ('button {\n')
        outfile.write ("font-size: 12pt; font-family: 'Arial', 'Helvetica', sans-serif;\n")
        outfile.write ('font-weight: bold; color: #000000; text-align: center;\n')
        outfile.write ('text-indent: 0px;\n')
        outfile.write ('padding: 0px; margin: 0px;\n')  
        outfile.write ('}\n')
        outfile.write ('p {\n')
        outfile.write ("font-size: 12pt; font-family: 'Arial', 'Helvetica', sans-serif;\n")
        outfile.write ('font-weight: bold; color: #000000; text-align: center;\n')
        outfile.write ('text-indent: 0px;\n')
        outfile.write ('padding: 0px; margin: 0px;\n')  
        outfile.write ('}\n')
        outfile.write ('p.wx {\n')
        outfile.write ("font-size: 10pt; font-family: 'Arial', 'Helvetica', sans-serif;\n")
        outfile.write ('color: #000000; text-align: left;\n')
        outfile.write ('text-indent: 0px;\n')
        outfile.write ('padding: 0px; margin: 0px;\n')  
        outfile.write ('}\n')
        outfile.write ('<span {\n')
        outfile.write (f'width: {canw_str}px;\n')
        outfile.write ('margin-left: auto;\n')
        outfile.write ('margin-right: auto;\n')
        outfile.write ("font-size: 12pt; font-family: 'Arial', 'Helvetica', sans-serif;\n")
        outfile.write ('font-style: normal; font-weight: bold; color: #000000;\n')
        outfile.write ('background-color: transparent; text-decoration: none;\n')
        outfile.write ('}\n')
        outfile.write ('p.gbot {\n')
        outfile.write ('border-style: solid;\n')
        outfile.write ('border-bottom-color: Gray;\n')
        outfile.write ('}\n')
        outfile.write ('p.gtop {\n')
        outfile.write ('border-style: solid;\n')
        outfile.write ('border-top-color: Gray;\n')
        outfile.write ('}\n')
        outfile.write ('p.ntop {\n')
        outfile.write ('border-top-style: none;\n')
        outfile.write ('}\n')
        outfile.write ('p.nbot {\n')
        outfile.write ('border-bottom-style: none;\n')
        outfile.write ('}\n')    
        outfile.write ('</style>\n')
        outfile.write ('</head>\n')
        outfile.write ('<body style="background-color:black;">\n')
        outfile.write ('<div>\n')
        outfile.write (f'<table width="{canw_str}" border="2" cellpadding="2" cellspacing="2" style="border-color: #000000; border-style: solid; background-color: #ccffff;">\n')
        outfile.write ('<tr valign="middle">\n') 
        #outfile.write ('<td colspan="4" style="background-color: #1A53FF;"><p><span style=" font-size: 12pt; font-family: ''Arial'', ''Helvetica'', sans-serif; font-style: normal; font-weight: bold; color: #FFFFFF; background-color: transparent; text-decoration: none;">\n')
        #outfile.write (f'BatV: {round(float(batv)/1000, 3)}&nbsp&nbsp&nbsprssi: {rssi}</span></p>\n')
        #outfile.write ('</td>\n')
        outfile.write ('<td colspan="5" style="background-color: #1A53FF;"><p><span style=" font-size: 12pt; font-family: ''Arial'', ''Helvetica'', sans-serif; font-style: normal; font-weight: bold; color: #FFFFFF; background-color: transparent; text-decoration: none;">\n')
        outfile.write (f'{self.cons.STATION_LOCATION} Tide & Weather - {dispdate}.&nbsp&nbspSunrise: {sunrise} - Sunset: {sunset}</span></p>\n')
        outfile.write ('</td>\n')
        outfile.write ('<td colspan="4" style="background-color: #1A53FF;"><p><span style=" font-size: 12pt; font-family: ''Arial'', ''Helvetica'', sans-serif; font-style: normal; font-weight: bold; color: #FFFFFF; background-color: transparent; text-decoration: none;">\n')
        outfile.write (f'BatV: {round(float(batv)/1000, 3)}&nbsp&nbsp&nbsprssi: {rssi}</span></p>\n')
        outfile.write ('</td>\n')
        outfile.write ('<td colspan="2" style="background-color: #1A53FF;"><p><span style=" font-size: 12pt; font-family: ''Arial'', ''Helvetica'', sans-serif; font-style: normal; font-weight: bold; color: #FFFFFF; background-color: transparent; text-decoration: none;">\n')
        outfile.write (f'<form action="/alertlogin.html"><button type="submit">Alerts</button></form></span></p>\n')
        outfile.write ('</td>\n')
        outfile.write ('</tr>\n')
        if not self.tide_only:
            outfile.write ('<tr valign="middle">\n')
            if self.cons.WX_SERVICE == 'openwx':
                outfile.write ('<td colspan="2">\n')
                outfile.write ('<p style="font-size: 0.65rem; opacity: 0.6; padding: 0px; margin: 0px; text-indent: 0px;">\n')
                outfile.write ('Weather data provided by '
                  '<a href="https://openweathermap.org/" target="_blank">OpenWeather</a></p>\n')
                outfile.write ('</td>\n')
            elif self.cons.WX_SERVICE == 'wxund':                            
                outfile.write (f'<td colspan="2"><p><a href="{self.WX_UND_URL}">\n')
                outfile.write (f'Local Weather</a></p>\n')
                outfile.write ('</td>\n')
            outfile.write ('<td><p>Air Temp</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>humidity</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>Dew Point</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>Winds</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>Gusts</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>Barometer</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>Rain Rate</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p>Rain Today</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('</tr>\n')
            outfile.write ('<tr valign="middle">\n')
            if not weather:
                outfile.write ('<td colspan = "8" style="background-color: snow;"> <p>Local Weather Temporarily Unavailable</p>\n')
            else:
                outfile.write ('<td colspan="2" style="background-color: snow;"><p>\n')
                outfile.write (f'{obs_time}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write ('<td style="background-color: snow;"><p>\n')
                outfile.write (f'{temperature}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{humidity}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{dewpoint}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{wind_speed}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{wind_gust}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{baro}</p>\n')
                outfile.write (f'</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{rain_rate}</p>\n')
                outfile.write ('</td>\n')
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{rain_today}</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('</tr>\n')
            outfile.write ('<tr valign="middle">\n')
            #outfile.write ('<td colspan="10" style="background-color: #1A53FF;">\n')
            outfile.write ('<td colspan="10" style="background-color: #6BB4E2;">\n')
            if True:
                outfile.write (
                  f'<p><a href="{self.NDBC_URL}" '+
                  f'style="color: black">{self.cons.NDBC_TITLE}</a></p>\n')
                  #f'style="color: white">NDBC Marine Observation - '+
                  #f'{self.cons.NDBC_LOCATION} - '+
                  #f'Location: {str(self.cons.NDBC_LATITUDE)} '+
                  #f'{str(self.cons.NDBC_LONGITUDE)}</a></span></p>\n')
            elif ndbc_currency == 1:
                outfile.write (
                  f'<a href="{self.NDBC_URL}" '+
                  f'style="color: white">NDBC Marine Observation - {self.cons.NDBC_LOCATION} - '+
                  f'Location: {str(self.cons.NDBC_LATITUDE)} '+
                  f'{str(self.cons.NDBC_LONGITUDE)}<font color="#FF9999"> '+
                  f'(This report is more than 2 hours old)</font></a></span></p>\n')
            elif ndbc_currency == 2:
                outfile.write (
                  f'<a href="{self.NDBC_URL}" '+
                  f'style="color: white">NDBC Marine Observation - {self.cons.NDBC_LOCATION} - '+
                  f'Location: {str(self.cons.NDBC_LATITUDE)} '+
                  f'{str(self.cons.NDBC_LONGITUDE)}<font color="red"> '+
                  f'Temporarily Out of Service</a></span></p>\n')
            outfile.write (f'</td>\n')
            outfile.write ('</tr>\n')
            outfile.write ('<tr valign="middle" style="background-color: #6BB4E2;">\n')
            outfile.write ('<td colspan = "2"><p style="color: black">Offshore Conditions</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Air Temp<span></p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Wave Hgt</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Wave Per</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Winds</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Gusts</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Barometer</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Water Temp</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('<td><p style="color: black">Wave Dir</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('</tr>\n')
            outfile.write ('</span>\n')
            outfile.write ('<tr valign="middle">\n')
            outfile.write ('<td colspan = "2" style="background-color: snow;"><p>\n')
            outfile.write (f'{ndbc_time}</p>\n')
            outfile.write (f'</td>\n')
            outfile.write (f'<td style="background-color: snow;"><p>\n')
            outfile.write (f'{ndbc_air_temp}</p>\n')
            outfile.write ('</td>\n')
            if not isinstance(ndbc_wave_f, float) or ndbc_wave_f <= 2.5:
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{ndbc_wave_height}</p>\n')
            elif ndbc_wave_f > 2.5 and ndbc_wave_f <= 5:
                outfile.write (f'<td style="background-color: #FFA533;"><p>\n')
                outfile.write (f'{ndbc_wave_height}</p>\n')
            else:  
                outfile.write (f'<td style="background-color: #FF5480;"><p>\n')
                outfile.write (f'{ndbc_wave_height}</p>\n')
            outfile.write (f'</td>\n')
            outfile.write (f'<td style="background-color: snow;"><p>\n')
            outfile.write (f'{ndbc_wave_period}</p>\n')
            outfile.write (f'</td>\n')
            if not isinstance(ndbc_wind_f, float) or ndbc_wind_f <= 12.0:
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{ndbc_wind}</p>\n')
            elif ndbc_wind_f > 12.0 and ndbc_wind_f < 20.0:
                outfile.write (f'<td style="background-color: #FFA533;"><p>\n')
                outfile.write (f'{ndbc_wind}</p>\n')
            else:
                outfile.write (f'<td style="background-color: #FF5480;"><p>\n')
                outfile.write (f'{ndbc_wind}</p>\n')
            outfile.write (f'</td>\n')
            if not isinstance(ndbc_gust_f, float) or ndbc_gust_f <= 12.0:
                outfile.write (f'<td style="background-color: snow;"><p>\n')
                outfile.write (f'{ndbc_gust}</p>\n')
            elif ndbc_gust_f > 12.0 and ndbc_gust_f < 20.0:
                outfile.write (f'<td style="background-color: #FFA533;"><p>\n')
                outfile.write (f'{ndbc_gust}</p>\n')
            else:
                outfile.write (f'<td style="background-color: #FF5480;"><p>\n')
                outfile.write (f'{ndbc_gust}</p>\n')
            outfile.write (f'</td>\n')
            outfile.write (f'<td style="background-color: snow;"><p>\n')
            outfile.write (f'{ndbc_baro}</p>\n')
            outfile.write (f'</td>\n')
            outfile.write (f'<td style="background-color: snow;"><p>\n')
            outfile.write (f'{ndbc_water_temp}</p>\n')
            outfile.write ('</td>\n')
            outfile.write (f'<td style="background-color: snow;"><p>\n')
            outfile.write (f'{ndbc_wave_direction}</p>\n')
            outfile.write ('</td>\n')
            outfile.write ('</tr>\n')    
        outfile.write ('</table>\n')
        outfile.write (f'<canvas id="bbitide" width={canvas_width} height={canvas_height}\n')
        outfile.write ('style="border:2px solid white; background-color: #E0F8F1">\n')
        outfile.write ('</canvas>\n')
        outfile.write ('<script>\n')
        outfile.write ('var canvas = document.getElementById("bbitide");\n')
        outfile.write ('var ctx = canvas.getContext("2d");\n')
        outfile.write ('ctx.fillStyle = "#1932E1";\n')
        outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
       #
       # Calculate X and Y axis coordinates from tidelist entries
       #       and prepare plotlist
       #
        tidestate = ''
        timeline = []
        turntime = ''
        turntime2 = ''
        if tidelist:
            x_start = bored+(offtime*plotsecs)
            for pidx, ent in enumerate(tidelist):
                ploty = 0
                try:
                    thistime = datetime.strptime(ent[0], timeformat)
                except:
                    continue
                plottime = thistime.timestamp() - starttime.timestamp()
                plotx = int((plotsecs*plottime)+x_start)
                hourtime = thistime.hour
                hm = datetime.strftime(thistime, "%H:%M")
                linedate = datetime.strftime(thistime, "%d %b")
                ploty = 1
                thistate = ent[2]
                if thistate == 'low' or thistate == 'high':
                    if turntime == '' or thistime > turntime:
                        turntime = thistime+timedelta(hours=3)
                        timeline.append(
                          [plotx,ploty,ent[1],hm,linedate,thistate])             
    
        x_start = bored
        #
        # Left hand black vertical boundary line
        #
        outfile.write ('ctx.strokeStyle = "#000000";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
        outfile.write ('ctx.globalCompositeOperation = "source-over";\n')
        outfile.write ('ctx.beginPath();\n')
        outfile.write (f'ctx.moveTo({x_start},{plot_start_y});\n')
        outfile.write (f'ctx.lineTo({x_start},{int(plot_base)});\n')
        outfile.write ('ctx.stroke();\n')
        outfile.write ('ctx.fillStyle = "black";\n')
        outfile.write ('ctx.font = "12px Arial";\n')
        #
        # Horizontal tide level grid lines and tide level annotation
        #
        gridx = plot_width+bored
        outfile.write ('ctx.strokeStyle = "#6E6E6E";\n')
        outfile.write ('ctx.lineWidth = 1;\n')
        outfile.write ('ctx.globalCompositeOperation = "source-over";\n')
        for gidx in range(0,y_divs+1):
            linbr = str(min_y+gidx)
            if gidx == 0 or gidx == y_divs:
                outfile.write ('ctx.lineWidth=2;\n')
            else:           
                outfile.write ('ctx.lineWidth=1;\n')
            gridy = int((plot_base)-y_grid_size*gidx)
            outfile.write ('ctx.beginPath();\n')
            outfile.write (f'ctx.moveTo({x_start},{gridy});\n')
            outfile.write (f'ctx.lineTo({gridx},{gridy});\n')
            outfile.write ('ctx.stroke();\n')
            outfile.write ('ctx.textAlign = "left";\n')
            outfile.write (f'ctx.fillText("{linbr}", 7, {gridy});\n')
        #
        # Right hand vertical boundary line
        #
        outfile.write ('ctx.strokeStyle = "#000000";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
        outfile.write ('ctx.beginPath();\n')
        outfile.write (f'ctx.moveTo({gridx},{plot_start_y});\n')
        outfile.write (f'ctx.lineTo({gridx},{int(plot_base)});\n')
        outfile.write ('ctx.stroke();\n')
        outfile.write ('ctx.textAlign = "center";\n')
        outfile.write ('ctx.strokeStyle = "#FFFFFF";\n')
        #
        # Blue time line
        #
        plotx = (plot_width)/2+bored
        outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
        outfile.write ('ctx.beginPath();\n')
        outfile.write (f'ctx.moveTo({plotx},{plot_start_y-2});\n')
        outfile.write (f'ctx.lineTo({plotx},{int(plot_base)});\n')
        outfile.write ('ctx.stroke();\n')
        ploty = canvas_height-20
        if banflag == 1:
            outfile.write ('ctx.font = "18px Arial";\n')
            outfile.write (f'ctx.fillText("{banner}", {canvas_width/2},{canvas_height-40});\n')
        outfile.write ('ctx.font = "12px Arial";\n')
        outfile.write ('ctx.strokeStyle = "#FFFFFF";\n')
        outfile.write ('ctx.lineWidth = 1;\n')
        outfile.write ('ctx.font = "bold 12px Arial";\n')
        outfile.write ('ctx.fillStyle = "black";\n')
        outfile.write ('ctx.strokeStyle = "#808080";\n')
        #
        # First plot the predicted tide level for the previous and next 24 hours
        #
        for pidx, ent in enumerate(predicts):
            if pidx == 0:
             #startx = int(bored+ent[1]*(plot_width)/self.plotspan*3600/2)
                startx = int(bored+ent[1]*plotsecs)
                starty = int(plot_base-(ent[2]-min_y)*y_grid_size)
                outfile.write ('ctx.beginPath();\n')
                outfile.write (f'ctx.moveTo({startx},{starty});\n')
                continue
            endx = int(bored+ent[1]*plotsecs)
            endy = int(plot_base-(ent[2]-min_y)*y_grid_size)
            outfile.write (f'ctx.lineTo({endx},{endy});\n')
            outfile.write ('ctx.stroke();\n')
        #
        # Then plot the high and low tides, vertical grid lines and annotation
        #
        outfile.write ('ctx.globalCompositeOperation = "source-over";\n')
        outfile.write ('ctx.lineWidth = 1;\n')
        outfile.write ('ctx.strokeStyle = "#6E6E6E";\n')
        outfile.write ('ctx.font = "bold 12px Arial";\n')
        for pidx, ent in enumerate(predicts):
            if pidx == 0:
                prestate = ent[3]
                continue
            thistate = ent[3]
            thistime = ent[0]
            try:
                hrmin = datetime.strftime(thistime, "%H:%M")
            except:
                continue
            linedate = datetime.strftime(thistime, "%d %b")
            endx = int(bored+ent[1]*plotsecs)
            if thistime.minute == 0 and thistime.hour % 2 == 0:
                outfile.write ('ctx.beginPath();\n')
                outfile.write (f'ctx.moveTo({endx},{int(plot_base)});\n')
                outfile.write (f'ctx.lineTo({endx},{plot_start_y});\n')
                outfile.write ('ctx.stroke();\n')
       
            if thistime.minute == 0 and thistime.hour % 4 == 0:
                outfile.write ('ctx.fillStyle = "black";\n')
                outfile.write (f'ctx.fillText("{hrmin}", {endx}, {ploty+6});\n')
                if thistime.hour == 4 or thistime.hour == 12 or thistime.hour == 20:
                    outfile.write (f'ctx.fillText("{linedate}", {endx}, {ploty+17});\n')
        outfile.write (f'ctx.font = "bold 14px Arial";\n')
        outfile.write ('ctx.strokeStyle = "#000000";\n')
        for pidx, ent in enumerate(predicts):
            if pidx == 0:
             #outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                prestate = ent[3]
                continue
            thistate = ent[3]
            thistime = ent[0]
            try:
                hrmin = datetime.strftime(thistime, "%H:%M")
            except:
                continue
            linedate = datetime.strftime(thistime, "%d %b")
            endx = int(bored+ent[1]*plotsecs)
            if thistate == 'L' or thistate == 'H':
                if prestate == '':
                    prestate = thistate
                elif prestate != thistate:
                    prestate = thistate
                    peak = format(ent[2], '.2f') 
                    if prestate == 'H':
                        outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                        outfile.write (f'ctx.strokeRect({endx-21}, {midcanvas+28}, 42, 30);\n')
                        outfile.write (f'ctx.fillRect({endx-21}, {midcanvas+28}, 42, 30);\n')
                        outfile.write (f'ctx.fillStyle = "#808080";\n')
                        outfile.write (f'ctx.fillText("{peak}", {endx}, {midcanvas+42});\n')
                        outfile.write (f'ctx.fillText("{hrmin}", {endx}, {midcanvas+57});\n')
                    else:
                        outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                        outfile.write (f'ctx.strokeRect({endx-21}, {midcanvas-28}, 42, 30);\n')
                        outfile.write (f'ctx.fillRect({endx-21}, {midcanvas-28}, 42, 30);\n')
                        outfile.write (f'ctx.fillStyle = "#808080";\n')
                        outfile.write (f'ctx.fillText("{hrmin}", {endx}, {midcanvas+1});\n')
                        outfile.write (f'ctx.fillText("{peak}", {endx}, {midcanvas-14});\n')
       
        if tidelist:
            for ent in timeline:
                plotx = int(ent[0])
                hm = ent[3]
                peak = format(ent[2], '.2f')
                outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
                if ent[5] != '':
                    if ent[5] == 'high':
                        outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                        outfile.write (f'ctx.strokeRect({plotx-21}, {midcanvas-60}, 42, 30);\n')
                        outfile.write (f'ctx.fillRect({plotx-21}, {midcanvas-60}, 42, 30);\n')
                        outfile.write (f'ctx.fillStyle = "#1A53FF";\n')
                        outfile.write (f'ctx.fillText("{peak}", {plotx}, {midcanvas-49});\n')
                        outfile.write (f'ctx.fillText("{hm}", {plotx}, {midcanvas-34});\n')
                    else:
                        outfile.write (f'ctx.fillStyle = "#ffffff";\n')
                        outfile.write (f'ctx.strokeRect({plotx-21}, {midcanvas-4}, 42, 30);\n')
                        outfile.write (f'ctx.fillRect({plotx-21}, {midcanvas-4}, 42, 30);\n')
                        outfile.write (f'ctx.fillStyle = "#1A53FF";\n')
                        outfile.write (f'ctx.fillText("{hm}", {plotx}, {midcanvas+24});\n')
                        outfile.write (f'ctx.fillText("{peak}", {plotx}, {midcanvas+9});\n')
                        
        outfile.write (f'ctx.font = "bold 20px Arial";\n')
        outfile.write ('ctx.strokeStyle = "black";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
        outfile.write (f'ctx.fillStyle = "white";\n')
        outfile.write (f'ctx.fillRect({canvas_width/2-50}, 4, 110, 23);\n')
        outfile.write (f'ctx.strokeRect({canvas_width/2-50}, 4, 110, 23);\n')
        outfile.write ('ctx.fillStyle = "black";\n')
        outfile.write (f'ctx.fillText(" Time {hrtime} ", {canvas_width/2+5},22);\n')
        
        outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
        outfile.write (f'ctx.fillStyle = "white";\n')
        outfile.write (f'ctx.fillRect({canvas_width/2-265}, 4, 210, 23);\n')
        outfile.write (f'ctx.strokeRect({canvas_width/2-265}, 4, 210, 23);\n')
        outfile.write (f'ctx.fillStyle = "#1A53FF";\n')
        outfile.write (f'ctx.fillText("Current Tide {tide} Ft ", {canvas_width/2-160},22);\n')
        outfile.write (f'ctx.font = "bold 14px Arial";\n')
        outfile.write (f'ctx.fillStyle = "#1A53FF";\n')
        #outfile.write (f'ctx.fillText("Actual Tide Trace", {canvas_width/2-400},20);\n')    
        outfile.write (f'ctx.fillText("{self.STATION_NAME}", {canvas_width/2-400},20);\n')    
        #outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
        #outfile.write ('ctx.beginPath();\n')
        #outfile.write (f'ctx.moveTo({canvas_width/2-500},15);\n')
        #outfile.write (f'ctx.lineTo({canvas_width/2-470},15);\n')
        #outfile.write ('ctx.stroke();\n')
        
        #outfile.write ('ctx.beginPath();\n')
        #outfile.write (f'ctx.moveTo({canvas_width/2-335},15);\n')
        #outfile.write (f'ctx.lineTo({canvas_width/2-305},15);\n')
        #outfile.write ('ctx.stroke();\n')
       
        outfile.write (f'ctx.fillStyle = "#808080";\n')
        #outfile.write (f'ctx.fillText("Predicted Tide Trace", {canvas_width/2+350},20);\n')
        outfile.write (f'ctx.fillText("{self.NOAA_STATION_NAME}", {canvas_width/2+350},20);\n')
    
        #outfile.write ('ctx.strokeStyle = "#808080";\n')
        #outfile.write ('ctx.beginPath();\n')
        #outfile.write (f'ctx.moveTo({canvas_width/2+240},15);\n')
        #outfile.write (f'ctx.lineTo({canvas_width/2+270},15);\n')
        #outfile.write ('ctx.stroke();\n')
        
        #outfile.write ('ctx.beginPath();\n')
        #outfile.write (f'ctx.moveTo({canvas_width/2+430},15);\n')
        #outfile.write (f'ctx.lineTo({canvas_width/2+460},15);\n')
        #outfile.write ('ctx.stroke();\n')
       
        outfile.write (f'ctx.font = "bold 14px Arial";\n')
        outfile.write ('ctx.fillStyle = "#1932E1";\n')
        outfile.write ('ctx.strokeStyle = "#1A53FF";\n')
        outfile.write ('ctx.lineWidth = 2;\n')
        #
        # Plot the actual tide
        #
        if tidelist:
            x_start = bored+(offtime*plotsecs)
            for pidx, ent in enumerate(tidelist):
                try:
                    thistime = datetime.strptime(ent[0], timeformat)
                except:
                    continue
                plottime = thistime.timestamp() - starttime.timestamp()
                plotx = int((plotsecs*plottime)+x_start)
                if self.lastidetime == 0 or thistime > self.lastidetime+timedelta(minutes=3):
                    self.samcnt = 0
                else:
                    self.samcnt += 1
                    self.lastidesams = self.lastidesams[1:]+[ent[1]]              
                self.lastidetime = thistime                   
                if self.samcnt > 4:
                    avetide = 0
                    for x in self.lastidesams:
                        avetide += x
                    avetide = avetide/len(self.lastidesams)              
                    outfile.write ('ctx.fillStyle = "#1932E1";\n')
                    ploty = int(plot_base-(avetide-min_y)*y_grid_size)
                    outfile.write (f'ctx.fillRect({plotx},{ploty},2,2);\n')                                             
        outfile.write ('</script>\n')
        #outfile.write ('</body>\n') # temporary
        #outfile.write ('</html>\n') # temporary
        outfile.close()
        self.wxexit = filetag
        excode = subprocess.run(['mv', f'{filetag}', 'tide.tmp'])
        if not self.tide_only:
            os.system(f'cat tide.tmp wx.html > {self.html_directory}tide.html')
        else:
             os.system(f'cat tide.tmp tide_only.html > {self.html_directory}tide.html')           
        return self.wxexit