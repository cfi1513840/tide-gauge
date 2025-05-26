import requests
import json
import os
import pytz
from datetime import datetime, timedelta
import time
import sqlite3
from dotenv import load_dotenv, find_dotenv

class CreateWxHTML:
    
    def __init__(self, cons):
        self.cons = cons
        self.sqlpath = self.cons.SQL_PATH
        self.local_points = self.cons.NWS_LOCAL_GRIDPOINTS
        self.marine_points = self.cons.NWS_MARINE_GRIDPOINTS
        self.filetag = ''
        self.outfile = 0        
        self.sqlcon = sqlite3.connect(f'{self.sqlpath}')
        self.sqlcur = self.sqlcon.cursor()
    #
    # UTC to local time conversion
    #
    def utc_to_local(self, utc_time):
        time = utc_time.replace('T',' ')
        timeform = datetime.strptime(time,"%Y-%m-%d %H:%M:%S")
        local_tz = pytz.timezone('US/Eastern')
        local_time = timeform.replace(tzinfo=pytz.utc).astimezone(local_tz)
        local_time = str(local_tz.normalize(local_time))[:-6]
        return (local_time)
        
    def wxproc(self, iparams):
        canvas_width = 1200
        nbrcols = 11
       #col_width = str(int(canvas_width/nbrcols))
        col_width = '100'
        canw_str = str(canvas_width)
        current_time = datetime.now()
        curtimestr = datetime.strftime(current_time,"%Y-%m-%d %H:%M:%S")
        minute = datetime.strftime(current_time, "%M")
        self.filetag = "wx"+datetime.strftime(current_time, "%y%m%d%H%M%S")+".tmp"
        self.outfile = open(self.filetag, "w")    
        self.outfile.write (f'<table border="2" cellpadding="2" cellspacing="2" style="border-color: #000000; border-style: solid; background-color: #ccffff;">\n')
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<td colspan="{nbrcols}" style="background-color: #1A53FF;"><p><span style=" font-size: 12pt; font-family: ''Arial'', ''Helvetica'', sans-serif; font-style: normal; font-weight: bold; color: #FFFFFF; background-color: transparent; text-decoration: none;">\n')
        headers = {'User-Agent': '(bbitide.org, alert@bbitidereport.com)'}
        fcurl = f"https://api.weather.gov/gridpoints/{self.local_points}/forecast"
        response = requests.get(fcurl, headers=headers)
        if str(response) != '<Response [200]>':
            print (curtimestr,'Error '+str(response)+' from api.weather.gov call')
            wxtime = iparams['wxtime']
            timecheck = datetime.strptime(wxtime,"%Y-%m-%d %H:%M:%S")+timedelta(hours=6)
            if current_time > timecheck:
                self.outfile.write (f'National Weather Service Forecast Out of Service</span></p>\n')
                self.outfile.write ('</td>\n')
                self.outfile.write ('</tr>\n')
                self.outfile.close()
                return -2
            self.outfile.close()
            return -1
        else:
            self.sqlcur.execute(f"update iparams set wxtime = '{curtimestr}'")
            self.sqlcon.commit()
        self.outfile.write (f'{self.cons.STATION_LOCATION} Five Day Weather Forecast</span></p>\n')
        self.outfile.write ('</td>\n')
        self.outfile.write ('</tr>\n')
        try:
            result=response.json()
            dumpedic = json.dumps(result)
            loadedic = json.loads(dumpedic)
            dofw = loadedic['properties']['periods']
        except Exception as errmsg:
            print (str(current_time),errmsg)
            self.outfile.close()
            return -1   
        self.outfile.write ('<tr valign="middle">\n')
        names = []
        windspds = []
        winddirs = []
        icons = []
        temps = []
        phrases = []
        detailed = []
        tdclasses = []
        tdclassesname = []
        tdclassestemp = []
        for index in range(0,len(dofw)):
            tdclass = dofw[index]['name'].find('ight')
            if tdclass != -1:
                tdclasses.append('night')
                tdclassesname.append('night-name')
                tdclassestemp.append('night-temp')
            else:
                tdclasses.append('day')   
                tdclassesname.append('day-name')
                tdclassestemp.append('day-temp')
            names.append(dofw[index]['name'])
            windspds.append(dofw[index]['windSpeed'])
            icons.append(dofw[index]['icon'])
            winddirs.append(dofw[index]['windDirection'])
            temps.append(dofw[index]['temperature'])
            phrases.append(dofw[index]['shortForecast'])
            detailed.append(dofw[index]['detailedForecast'])
        for indx, name in enumerate(names):
            if indx == 10: break
            self.outfile.write (f'<td class="{tdclassesname[indx]}">\n')
            self.outfile.write (f'{name}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')  
        for indx, temp in enumerate(temps):
            if indx == 10: break
            self.outfile.write (f'<td class="{tdclassestemp[indx]}">\n')
            if tdclassestemp[indx] == 'night-temp':
                newtemp = 'Low: '+str(temp)+'&deg;F'
            else:
                newtemp = 'High: '+str(temp)+'&deg;F'
            self.outfile.write (f'{newtemp}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')
        for indx, speed in enumerate(windspds):
            if indx == 10: break
            self.outfile.write (f'<td class="{tdclasses[indx]}">\n')
            newspeed = winddirs[indx]+' '+speed
            self.outfile.write (f'{newspeed}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')
        for indx, iconurl in enumerate(icons):
            if indx == 10: break
            self.outfile.write (f'<td class="{tdclasses[indx]}">\n')
            self.outfile.write (f'<img src="{iconurl}">\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle";>\n')
        for indx, phrase in enumerate(phrases):
            if indx == 10: break
            self.outfile.write (f'<td class="{tdclasses[indx]}">\n')
            self.outfile.write (f'{phrase}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('</table>\n')
        self.outfile.write (f'<table>\n')
        self.outfile.write ('<tr>\n')
        self.outfile.write (f'<td class="gif"><p>Detailed Forecast</p>\n')
        for indx, name in enumerate(names):
            if indx == 10: break
            detext = detailed[indx]
            self.outfile.write (f'<p>{name}:</p><p class="wx">{detext}</p>\n')   
        self.outfile.write ('</td>\n')
        self.outfile.write (f'<td class="gif">\n')
        self.outfile.write (f'<img style="display: block;-webkit-user-select: none;margin: auto;background-color: hsl(0, 0%, 90%);" src="{self.cons.NWS_RADAR}">\n')
        self.outfile.write ('</td>\n')
       #self.outfile.write ('<td class="gif">test</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('</table>\n')
        self.outfile.write ('<table>\n')      
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<th colspan="{nbrcols}" style="background-color: #1A53FF;"><span style=" font-size: 12pt; font-family: ''Arial'', ''Helvetica'', sans-serif; font-style: normal; font-weight: bold; color: #FFFFFF; background-color: transparent; text-decoration: none;">\n')
        self.outfile.write (f'Hourly Marine Point Forecast - {self.cons.NDBC_LOCATION} - Location: {self.cons.NDBC_LATITUDE} {self.cons.NDBC_LONGITUDE}\n')
        self.outfile.write ('</th>\n')
        self.outfile.write ('</tr>\n')
        headers = {'User-Agent': '(bbitide.org, alert@bbitidereport.com)'}
        fcurl = f"https://api.weather.gov/gridpoints/{self.marine_points}/" 
        response = requests.get(fcurl, headers=headers)
        if str(response) != '<Response [200]>':
            print (str(current_time),'Error response from api.weather.gov call')
            self.outfile.close()
            return -1
        result=response.json()
        tempList = []
        windDirList = []
        windSpeedList = []
        windGustList = []
        waveHeightList = []
        wavePeriodList = []
        waveDirList = []
        weatherList = []
        dumpedic = json.dumps(result)
        loadedic = json.loads(dumpedic)
        winddir = loadedic['properties']['windDirection']['values']
        windspeed = loadedic['properties']['windSpeed']['values']
        windgust = loadedic['properties']['windGust']['values']
        temps = loadedic['properties']['temperature']['values']
        waveheight = loadedic['properties']['waveHeight']['values']
        waveperiod = loadedic['properties']['wavePeriod']['values']
        wavedir = loadedic['properties']['waveDirection']['values']
        weather = loadedic['properties']['weather']['values']
        for thiswx in weather:
            thistime = thiswx['validTime']
            thistime = thistime[:thistime.find('+')]
            thisvalue = thiswx['value']
            wxtext = ''
            for val in thisvalue:
                if val['intensity'] != None and val['coverage'] != None and val['weather'] != None:
                    wxtext = wxtext+val['coverage']+' '+val['intensity']+' '+val['weather']+' '
                elif val['coverage'] != None and val['weather'] != None:
                    wxtext = wxtext+val['coverage']+' '+val['weather']+' '
                elif val['weather'] != None:
                    wxtext = wxtext+val['weather']+' '
            wxtext = wxtext.replace('_',' ')
             #print (thistime, wxtext)
            weatherList.append([self.utc_to_local(thistime), wxtext])
       #print (weatherList)
        for indx in range(0, len(temps)):
            thistime = loadedic['properties']['temperature']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['temperature']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            tempList.append([self.utc_to_local(thistime), thisvalue])
        for indx in range(0, len(winddir)):
            thistime = loadedic['properties']['windDirection']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['windDirection']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            windDirList.append([self.utc_to_local(thistime), thisvalue])
        for indx in range(0, len(windspeed)):
            thistime = loadedic['properties']['windSpeed']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['windSpeed']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            windSpeedList.append([self.utc_to_local(thistime), thisvalue])
        for indx in range(0, len(windgust)):
            thistime = loadedic['properties']['windGust']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['windGust']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            windGustList.append([self.utc_to_local(thistime), thisvalue])
        for indx in range(0, len(waveheight)):
            thistime = loadedic['properties']['waveHeight']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['waveHeight']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            waveHeightList.append([self.utc_to_local(thistime), thisvalue])
        for indx in range(0, len(waveperiod)):
            thistime = loadedic['properties']['wavePeriod']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['wavePeriod']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            wavePeriodList.append([self.utc_to_local(thistime), thisvalue])
        for indx in range(0, len(wavedir)):
            thistime = loadedic['properties']['waveDirection']['values'][indx]['validTime']
            thisvalue = loadedic['properties']['waveDirection']['values'][indx]['value']
            thistime = thistime[:thistime.find('+')]
            waveDirList.append([self.utc_to_local(thistime), thisvalue])
        tempLen = len(tempList)
        windDirLen = len(windDirList)
        windSpeedLen = len(windSpeedList)
        windGustLen = len(windGustList)
        waveHeightLen = len(waveHeightList)
        wavePeriodLen = len(wavePeriodList)
        waveDirLen = len(waveDirList)
        weatherLen = len(weatherList)
        outidx = 0
        tidx = 0
        wsidx = 0
        wdidx = 0
        wgidx = 0
        wahidx = 0
        wapidx = 0
        wadidx = 0
        wxidx = 0
        tempTime = ''
        windSpeedtime = ''
        windDirTime = ''
        windGustTime = ''
        waveHeightTime = ''
        wavePeriodTime = ''
        waveDirTime = ''
        weatherTime = ''
        thisTemp = ''
        thisWindSpeed = ''
        thisWindDir = ''
        thisWindGust = ''
        thisWaveHeight = ''
        thisWavePeriod = ''
        thisWaveDir = ''
        thisWeather = ''
        timeOut = []
        tempOut = []
        dateOut = []
        windSpeedOut = []
        windDirOut = []
        windGustOut = []
        waveHeightOut = []
        wavePeriodOut = []
        waveDirOut = []
        weatherOut = []
       #rowHeader = ['Time','Temperature','Wind Speed','Wind Gust','Wave Ht.','Wave Prd.','Weather']
        rowHeader = ['Time','Temperature','Wind Speed','Wind Gust','Wave Ht.','Weather']
        EaglesSoar = True
        while EaglesSoar:
            while tempLen > 0 and tempLen > tidx and datetime.strptime(tempList[tidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                tempTime = tempList[tidx][0]
                dispTime = datetime.strptime(tempTime, "%Y-%m-%d %H:%M:%S")
                thisTemp = str(int(round(tempList[tidx][1]*1.8+32,0)))+'\u00b0 F'
                thisTemp = str(int(round(tempList[tidx][1]*1.8+32,0)))+'&deg F'
                tidx += 1
            while windSpeedLen > 0 and windSpeedLen > wsidx and datetime.strptime(windSpeedList[wsidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                windSpeedTime = windSpeedList[wsidx][0]
                timeCheck = datetime.strptime(windSpeedTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
             #thisWindSpeed = int(round(windSpeedList[wsidx][1]*0.621,0)) # mph
                thisWindSpeed = int(round(windSpeedList[wsidx][1]*0.54,0)) # kts
                wsidx += 1
            while windDirLen > 0 and windDirLen > wdidx and datetime.strptime(windDirList[wdidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                windDirTime = windDirList[wdidx][0]
                timeCheck = datetime.strptime(windDirTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
                thisWindDir= int(round(windDirList[wdidx][1],0))
                wdidx += 1
            while windGustLen > 0 and windGustLen > wgidx and datetime.strptime(windGustList[wgidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                windGustTime = windGustList[wgidx][0]
                timeCheck = datetime.strptime(windGustTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
             #thisWindGust = int(round(windGustList[wgidx][1]*0.621,0)) # mph
                thisWindGust = int(round(windGustList[wgidx][1]*0.54,0)) # kts
                wgidx += 1
            while waveHeightLen > 0 and waveHeightLen > wahidx and datetime.strptime(waveHeightList[wahidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                waveHeightTime = waveHeightList[wahidx][0]
                timeCheck = datetime.strptime(waveHeightTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
                thisWaveHeight = str(int(round(waveHeightList[wahidx][1]*3.28,0)))+'ft'
                wahidx += 1
            while wavePeriodLen > 0 and wavePeriodLen > wapidx and datetime.strptime(wavePeriodList[wapidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                wavePeriodTime = wavePeriodList[wapidx][0]
                timeCheck = datetime.strptime(wavePeriodTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
                thisWavePeriod = str(int(round(wavePeriodList[wapidx][1],0)))+'sec'
                wapidx += 1
            while waveDirLen > 0 and waveDirLen > wadidx and datetime.strptime(waveDirList[wadidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                waveDirTime = waveDirList[wadidx][0]
                timeCheck = datetime.strptime(waveDirTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
                thisWaveDir = int(round(waveDirList[wadidx][1],0))
                wadidx += 1
            while weatherLen > 0 and weatherLen > wxidx and datetime.strptime(weatherList[wxidx][0],"%Y-%m-%d %H:%M:%S") <= current_time:
                weatherTime = weatherList[wxidx][0]
                timeCheck = datetime.strptime(weatherTime, "%Y-%m-%d %H:%M:%S")
                if timeCheck > dispTime:
                    dispTime = timeCheck
                thisWeather= weatherList[wxidx][1]
                wxidx += 1
            timeOut.append(datetime.strftime(dispTime, "%Y-%m-%d %H:%M:%S"))
            thisDate = datetime.strftime(dispTime, "%y%m%d")
            dateOut.append(datetime.strptime(thisDate, "%y%m%d"))
            tempOut.append(thisTemp)
            windSpeedOut.append(thisWindSpeed)
            windDirOut.append(thisWindDir)
            windGustOut.append(thisWindGust)
            waveHeightOut.append(thisWaveHeight)
            wavePeriodOut.append(thisWavePeriod)
            waveDirOut.append(thisWaveDir)
            weatherOut.append(thisWeather)
            outidx += 1
            nextTime = current_time
            try:
                nextTime = datetime.strptime(tempList[tidx][0], "%Y-%m-%d %H:%M:%S")
                try:
                    timeCheck = datetime.strptime(windSpeedList[wsidx][0], "%Y-%m-%d %H:%M:%S")
                    if timeCheck < nextTime:
                        nextTime = timeCheck
                except:
                    pass
                try:
                    timeCheck = datetime.strptime(windDirList[wdidx][0], "%Y-%m-%d %H:%M:%S")
                    if timeCheck < nextTime:
                        nextTime = timeCheck
                except:
                    pass
                try:
                    timeCheck = datetime.strptime(windGustList[wgidx][0], "%Y-%m-%d %H:%M:%S")
                    if timeCheck < nextTime:
                        nextTime = timeCheck
                except:
                    pass
                try:
                    timeCheck = datetime.strptime(waveHeightList[wahidx][0], "%Y-%m-%d %H:%M:%S")
                    if timeCheck < nextTime:
                        nextTime = timeCheck
                except:
                    pass
                try:
                    timeCheck = datetime.strptime(wavePeriodList[wapidx][0], "%Y-%m-%d %H:%M:%S")
                    if timeCheck < nextTime:
                        nextTime = timeCheck
                except:
                    pass
                try:
                    timeCheck = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                    if timeCheck < nextTime:
                        nextTime = timeCheck
                except:
                    pass         
            except:
                try:
                    nextTime = datetime.strptime(windSpeedList[wsidx][0], "%Y-%m-%d %H:%M:%S")
                    try:
                        timeCheck = datetime.strptime(windDirList[wdidx][0], "%Y-%m-%d %H:%M:%S")
                        if timeCheck < nextTime:
                            nextTime = timeCheck
                    except:
                        pass
                    try:
                        timeCheck = datetime.strptime(windGustList[wgidx][0], "%Y-%m-%d %H:%M:%S")
                        if timeCheck < nextTime:
                            nextTime = timeCheck
                    except:
                        pass
                    try:
                        timeCheck = datetime.strptime(waveHeightList[wahidx][0], "%Y-%m-%d %H:%M:%S")
                        if timeCheck < nextTime:
                            nextTime = timeCheck
                    except:
                        pass
                    try:
                        timeCheck = datetime.strptime(wavePeriodList[wapidx][0], "%Y-%m-%d %H:%M:%S")
                        if timeCheck < nextTime:
                            nextTime = timeCheck
                    except:
                        pass
                    try:
                        timeCheck = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                        if timeCheck < nextTime:
                            nextTime = timeCheck
                    except:
                        pass
                except:
                    try:
                        nextTime = datetime.strptime(windDirList[wdidx][0], "%Y-%m-%d %H:%M:%S")           
                        try:
                          timeCheck = datetime.strptime(windGustList[wgidx][0], "%Y-%m-%d %H:%M:%S")
                          if timeCheck < nextTime:
                              nextTime = timeCheck
                        except:
                            pass
                        try:
                            timeCheck = datetime.strptime(waveHeightList[wahidx][0], "%Y-%m-%d %H:%M:%S")
                            if timeCheck < nextTime:
                                nextTime = timeCheck
                        except:
                            pass
                        try:
                            timeCheck = datetime.strptime(wavePeriodList[wapidx][0], "%Y-%m-%d %H:%M:%S")
                            if timeCheck < nextTime:
                                nextTime = timeCheck
                        except:
                            pass
                        try:
                            timeCheck = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                            if timeCheck < nextTime:
                                nextTime = timeCheck
                        except:
                            pass           
                    except:
                        try:
                            nextTime = datetime.strptime(windGustList[wgidx][0], "%Y-%m-%d %H:%M:%S")
                            try:
                                timeCheck = datetime.strptime(waveHeightList[wahidx][0], "%Y-%m-%d %H:%M:%S")
                                if timeCheck < nextTime:
                                    nextTime = timeCheck
                            except:
                                pass
                            try:
                                timeCheck = datetime.strptime(wavePeriodList[wapidx][0], "%Y-%m-%d %H:%M:%S")
                                if timeCheck < nextTime:
                                    nextTime = timeCheck
                            except:
                                pass
                            try:
                                timeCheck = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                                if timeCheck < nextTime:
                                    nextTime = timeCheck
                            except:
                                pass           
                        except:
                            try:
                                nextTime = datetime.strptime(waveHeightList[wahidx][0], "%Y-%m-%d %H:%M:%S")
                                try:
                                    timeCheck = datetime.strptime(wavePeriodList[wapidx][0], "%Y-%m-%d %H:%M:%S")
                                    if timeCheck < nextTime:
                                        nextTime = timeCheck
                                except:
                                    pass
                                try:
                                    timeCheck = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                                    if timeCheck < nextTime:
                                        nextTime = timeCheck
                                except:
                                    pass           
                            except:
                                try:
                                    nextTime = datetime.strptime(wavePeriodList[wapidx][0], "%Y-%m-%d %H:%M:%S")
                                    try:
                                        timeCheck = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                                        if timeCheck < nextTime:
                                            nextTime = timeCheck
                                    except:
                                        pass           
                                except:
                                    try:
                                        nextTime = datetime.strptime(waveDirList[wadidx][0], "%Y-%m-%d %H:%M:%S")
                                    except:
                                        pass
            if outidx > 9:
                EaglesSoar = False
            current_time = nextTime
        windDispComp = []
        
        for widx, windspeed in enumerate(windSpeedOut):
            winddir = windDirOut[widx]
            windgust = windGustOut[widx]
            windsym = ''
            if winddir != '':
                if winddir >= 349 or winddir < 12:
                    windsym = 'N '
                elif winddir >= 12 and winddir < 34:
                    windsym = 'NNE '
                elif winddir >= 34 and winddir < 56:
                    windsym = 'NE '
                elif winddir >= 56 and winddir < 79:
                    windsym = 'ENE '
                elif winddir >= 79 and winddir < 101:
                    windsym = 'E '
                elif winddir >= 101 and winddir < 124:
                    windsym = 'ESE '
                elif winddir >= 124 and winddir < 146:
                    windsym = 'SE '
                elif winddir >= 146 and winddir < 169:
                    windsym = 'SSE '
                elif winddir >= 169 and winddir < 191:
                    windsym = 'S '
                elif winddir >= 191 and winddir < 214:
                    windsym = 'SSW '
                elif winddir >= 214 and winddir < 236:
                    windsym = 'SW '
                elif winddir >= 236 and winddir < 259:
                    windsym = 'WSW '
                elif winddir >= 259 and winddir < 281:
                    windsym = 'W '
                elif winddir >= 281 and winddir < 304:
                    windsym = 'WNW '
                elif winddir >= 304 and winddir < 326:
                    windsym = 'NW '
                elif winddir >= 326 and winddir < 349:
                    windsym = 'NNW '
            windDispComp.append(windsym+str(windspeed)+'kt')
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<td class="day-time">\n')
        self.outfile.write (f'{rowHeader[0]}</td>\n')
        for time in timeOut:
            disptime = datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
            disptime = datetime.strftime(disptime, "%I:%M%p")
            self.outfile.write (f'<td class="day-time">\n')
            self.outfile.write (f'{disptime}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')  
        self.outfile.write (f'<td class="day-time">\n')
        self.outfile.write (f'{rowHeader[1]}</td>\n')
        for temp in tempOut:
            self.outfile.write (f'<td class="day-name">\n')
            self.outfile.write (f'{temp}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<td class="day-time">\n')
        self.outfile.write (f'{rowHeader[2]}</td>\n')
        for windspd in windDispComp:
            if windspd != '':
                windfloat = float(windspd.split()[1].replace('kt',''))
            if windfloat <= 15:
                self.outfile.write (f'<td class="day-name" style="background-color: snow;">\n')
            elif windfloat > 15 and windfloat <= 25:
                self.outfile.write (f'<td class="day-name" style="background-color: #FFA533;">\n')
            else:
                self.outfile.write (f'<td class="day-name" style="background-color: #FF5480;">\n')
            self.outfile.write (f'{windspd}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<td class="day-time">\n')
        self.outfile.write (f'{rowHeader[3]}</td>\n')
        for windgust in windGustOut:
            if windgust != '':
                windfloat = float(windgust)
            if windfloat <= 15:
                self.outfile.write (f'<td class="day-name" style="background-color: snow;">\n')
            elif windfloat > 15 and windfloat <= 25:
                self.outfile.write (f'<td class="day-name" style="background-color: #FFA533;">\n')
            else:
                self.outfile.write (f'<td class="day-name" style="background-color: #FF5480;">\n')
            self.outfile.write (f'{windgust}kt</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<td class="day-time">\n')
        self.outfile.write (f'{rowHeader[4]}</td>\n')
        for waveheight in waveHeightOut:
            if waveheight != '':
                wavefloat = float(waveheight.replace('ft',''))
            if wavefloat <= 3:
                self.outfile.write (f'<td class="day-name" style="background-color: snow;">\n')
            elif wavefloat > 3 and wavefloat <= 6:
                self.outfile.write (f'<td class="day-name" style="background-color: #FFA533;">\n')
            else:
                self.outfile.write (f'<td class="day-name" style="background-color: #FF5480;">\n')
            self.outfile.write (f'{waveheight}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('<tr valign="middle">\n')
        self.outfile.write (f'<td class="day-time">\n')
        self.outfile.write (f'{rowHeader[5]}</td>\n')
       #for waveperiod in wavePeriodOut:
       #   self.outfile.write (f'<td class="day-name">\n')
       #   self.outfile.write (f'{waveperiod}</td>\n')
       #self.outfile.write ('</tr>\n')
       #self.outfile.write ('<tr valign="middle">\n')
       #self.outfile.write (f'<td class="day-time">\n')
       #self.outfile.write (f'{rowHeader[6]}</td>\n')
        for weather in weatherOut:
            self.outfile.write (f'<td class="day-name">\n')
            self.outfile.write (f'{weather}</td>\n')
        self.outfile.write ('</tr>\n')
        self.outfile.write ('</table>\n')    
        self.outfile.write ('</div>\n')
        self.outfile.write ('</body>\n')
        self.outfile.write ('</html>\n')
        self.outfile.close()
        os.system(f'mv {self.filetag} wx.html')
        return 0
    
    