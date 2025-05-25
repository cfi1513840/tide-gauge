#import math
#import smtplib
#import socket
#import sqlite3
#import time
import tkinter as tk
from tkinter import StringVar
from datetime import datetime, timedelta, timezone
#from influxdb_client import InfluxDBClient, Point, WritePrecision
#from influxdb_client.client.write_api import SYNCHRONOUS
#from cryptography.fernet import Fernet
#from suntime import Sun, SunTimeException
#from twilio.rest import Client
#import feedparser
#import serial
#import requests
#import tideutils
import logging

class TideDisplay:

    def __init__(self, station, cons):
        self.cons = cons
        self.active_station = station
        self.canvas_width = 1200
        self.canvas_height = 680
        self.y_start = 30
        self.start_plot_x = 30
        self.last_baro = 0
        self.x_plot_start = 30
        self.y_plot_start = 30
        self.tide_turn_time = 0
        self.y_grid_size = (self.canvas_height-self.y_start)/13
        self.master = tk.Tk()
        self.master.configure(background='LightBlue1')
        self.master.geometry('+10+50')
        self.wind_speed_tk_var = StringVar()
        self.temperature_tk_var = StringVar()
        self.wind_gust_tk_var = StringVar()
        self.humidity_tk_var = StringVar()
        self.dew_point_tk_var = StringVar()
        self.heat_index_tk_var = StringVar()
        self.baro_tk_var = StringVar()
        self.rain_rate_tk_var = StringVar()
        self.rain_today_tk_var = StringVar()
        self.title_text = StringVar()
        self.ndbc_time_tk_var = StringVar()
        self.ndbc_wind_tk_var = StringVar()
        self.ndbc_gust_tk_var = StringVar()
        self.ndbc_wave_height_tk_var = StringVar()
        self.ndbc_wave_period_tk_var = StringVar()
        self.ndbc_air_temperature_tk_var = StringVar()
        self.ndbc_water_temperature_tk_var = StringVar()
        self.ndbc_wave_direction_tk_var = StringVar()
        self.ndbc_baro_tk_var = StringVar()
        self.ndbc_title_tk_var = StringVar()
        self.tk_display_width_tk_var = StringVar()
        self.display_predicted_tide_tk_var = StringVar()
        self.station_battery_voltage_tk_var = StringVar()
        self.station_signal_strength_tk_var = StringVar()
        self.active_station_tk_var = StringVar()
        self.active_station_tk_var.set(str(self.active_station))
        self.tk_display_width_tk_var.set('1')
        self.display_predicted_tide_tk_var.set('1')
        self.ndbc_title_tk_var.set(
          f'NDBC Marine Observation - {self.cons.NDBC_LOCATION} '+
          f' - Location: {str(self.cons.NDBC_LATITUDE)} '+
          f'{str(self.cons.NDBC_LONGITUDE)}')
        #
        # Create tkinter display format
        #
        proc_frame = tk.Frame(
                self.master, borderwidth = 2, highlightbackground =
                'black', highlightthickness=1, width = 500, pady=1)
        proc_frame.pack(side='top', fill='both', anchor='center')

        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Local Weather',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 22).grid(row = 0,
                column = 0, rowspan=2, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Air Temp',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 0,
                column = 1, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Humidity',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 0,
                column = 2, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Dew Pt',
                wraplength = 85, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 0,
                column = 3, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Winds',
                wraplength = 90, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 11).grid(row = 0,
                column = 4, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Gusts',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 0,
                column = 5,sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Barometer',
                wraplength = 85, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 8).grid(row = 0,
                column = 6, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Rain Rate',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 11).grid(row = 0,
                column = 7, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Rain Today',
                wraplength = 100, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 12).grid(row = 0,
                column = 8, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.temperature_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 1,
                column = 1, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.humidity_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 1,
                column = 2, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.dew_point_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 1,
                column = 3, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.wind_speed_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 11).grid(row = 1,
                column = 4, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.wind_gust_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 7).grid(row = 1,
                column = 5, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.baro_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 8).grid(row = 1,
                column = 6, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.rain_rate_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 9).grid(row = 1,
                column = 7, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.rain_today_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 12).grid(row = 1,
                column = 8, sticky = tk.NSEW)
        tk.Label(proc_frame, fg='White', bg = 'DarkBlue',
                textvariable = self.ndbc_title_tk_var,
                font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE).grid(row = 2, column = 0,
                columnspan = 9, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1',
                text = 'Observation Time', wraplength = 150,
                font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 22).grid(row = 3,
                column = 0, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Air Temp',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 14).grid(row = 3,
                column = 1, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Wave Hgt',
                wraplength = 75, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 13).grid(row = 3,
                column = 2, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Wave Per',
                wraplength = 85, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 14).grid(row = 3,
                column = 3, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Winds',
                wraplength = 80, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 16).grid(row = 3,
                column = 4, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Gusts',
                wraplength = 85, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 14).grid(row = 3,
                column = 5, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Barometer',
                wraplength = 100, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 14).grid(row = 3,
                column = 6, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Water Temp',
                wraplength = 100, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 12).grid(row = 3,
                column = 7, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'LightBlue1', text = 'Visibility',
                wraplength = 125, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 12).grid(row = 3,
                column = 8, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_time_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 22).grid(row = 4,
                column = 0, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_air_temperature_tk_var, font = ("Arial", 12,
                'bold'), relief = tk.RIDGE, width = 14).grid(row = 4,
                column = 1, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_wave_height_tk_var, font = ("Arial", 12,
                'bold'), relief = tk.RIDGE, width = 13).grid(row = 4,
                column = 2, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_wave_period_tk_var, font = ("Arial", 12,
                'bold'), relief = tk.RIDGE, width = 14).grid(row = 4,
                column = 3, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_wind_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 16).grid(row = 4,
                column = 4, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_gust_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 14).grid(row = 4,
                column = 5, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_baro_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 14).grid(row = 4,
                column = 6, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', textvariable =
                self.ndbc_water_temperature_tk_var,
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 12).grid(row = 4,
                column = 7, sticky = tk.NSEW)
        tk.Label(proc_frame, bg = 'snow', text = 'N/A',
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 12).grid(row = 4, column = 8, sticky = tk.NSEW)
        sel_frame = tk.Frame(self.master, bg = 'snow', borderwidth = 2,
                highlightbackground='black', highlightthickness=1,
                width = 500, pady=1)
        sel_frame.pack(side='top', fill='both', anchor='center')
        tk.Label(sel_frame,bg = 'LightBlue1', text = 'Active Sensor',
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 12, borderwidth = 0, highlightthickness=0).grid(
                row = 2, column = 0, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'snow', textvariable =
                self.active_station_tk_var, font = ("Arial", 12,
                'bold'), relief = tk.RIDGE, width = 2).grid(row = 2,
                column = 1, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text = 'Battery Voltage',
            font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
            width = 14, borderwidth = 0, highlightthickness=0).grid(
            row = 2, column = 2, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'snow', textvariable =
                self.station_battery_voltage_tk_var,
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 5).grid(row = 2, column = 3,
                sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text = 'Sig Strength',
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 12).grid(row = 2, column = 4, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'snow', textvariable =
                self.station_signal_strength_tk_var,
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 8).grid(row = 2, column = 5,
                sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text = 'Plot Span',
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                width = 12, borderwidth = 0, highlightthickness=0).grid(
                row = 2, column = 6, sticky = tk.NSEW)
        tk.Radiobutton(sel_frame, bg = 'snow', text = '48 Hr',
                font = ("Arial", 12, 'bold'), value='1',
                variable = self.tk_display_width_tk_var, width = 4).grid(
                row = 2, column = 7, sticky = tk.NSEW)
        tk.Radiobutton(sel_frame, bg = 'snow', text = '24 Hr',
                font = ("Arial", 12, 'bold'), value='2',
                variable = self.tk_display_width_tk_var, width = 4).grid(
                row = 2, column = 8, sticky = tk.NSEW)
        tk.Radiobutton(sel_frame, bg = 'snow', text = '12 Hr',
                font = ("Arial", 12, 'bold'), value='3',
                variable = self.tk_display_width_tk_var, width = 4).grid(
                row = 2, column = 9, sticky = tk.NSEW)
        tk.Radiobutton(sel_frame, bg = 'snow', text = '6 Hr',
                font = ("Arial", 12, 'bold'), value='4',
                variable = self.tk_display_width_tk_var, width = 4).grid(
                row = 2, column = 10, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text =
                'Predicted Tide Trace', font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE, width = 20, borderwidth = 0,
                highlightthickness=0).grid(row = 2, column = 11,
                sticky = tk.NSEW)
        tk.Radiobutton(sel_frame, bg = 'snow', text = 'On',
                font = ("Arial", 12, 'bold'), value='1',
                variable = self.display_predicted_tide_tk_var,
                width = 3).grid(row = 2, column = 12, sticky = tk.NSEW)
        tk.Radiobutton(sel_frame, bg = 'snow', text = 'Off',
                font = ("Arial", 12, 'bold'), value='0', variable =
                self.display_predicted_tide_tk_var, width = 3).grid(
                row = 2, column = 13, sticky = tk.NSEW)
        self.plot_window = tk.Canvas(self.master, bg = "#E0F8F1",
                width = self.canvas_width, height=self.canvas_height)
        self.plot_window.pack(side='top', fill='both')
        
        #import logging
        logging.info('Tkinter display initialized')

    def update(self, weather, ndbc_data):
        """Update tkinter display"""
        if weather:
            self.wind_speed_tk_var.set(str(weather['wind_speed']))
            self.temperature_tk_var.set(str(weather['temperature']))       
            self.wind_gust_tk_var.set(str(weather['wind_gust']))
            self.humidity_tk_var.set(str(weather['humidity']))
            self.dew_point_tk_var.set(str(weather['dewpoint']))
            #self.baro_tk_var.set(str(weather['baro']))
            self.rain_rate_tk_var.set(str(weather['rain_rate']))
            self.rain_today_tk_var.set(str(weather['rain_today']))
            baro = weather['baro']
            if self.last_baro != 0:
                if float(baro) < self.last_baro - 0.01:
                    self.baro_tk_var.set('\u2193 '+str(baro)+' \u2193')
                elif float(baro) > self.last_baro + 0.01:
                    self.baro_tk_var.set('\u2191 '+str(baro)+' \u2191')
                else:               
                    self.baro_tk_var.set(str(baro))
            else:               
                self.baro_tk_var.set(str(baro))
            self.last_baro = float(baro)
        if ndbc_data:
            self.ndbc_time_tk_var.set(ndbc_data['DateTime'])
            self.ndbc_wind_tk_var.set(ndbc_data['Wind Speed'])
            self.ndbc_gust_tk_var.set(ndbc_data['Wind Gust'])
            self.ndbc_wave_height_tk_var.set(ndbc_data['Wave Height'])
            self.ndbc_wave_period_tk_var.set(ndbc_data['Wave Period'])
            air_temp_display = ndbc_data['Air Temperature']
            water_temp_display = ndbc_data['Water Temperature']
            if air_temp_display != 'N/A':
                air_temp_display = air_temp_display+'\u00b0 F' 
            if water_temp_display != 'N/A':
                water_temp_display = water_temp_display+'\u00b0 F' 
            self.ndbc_air_temperature_tk_var.set(air_temp_display)
            self.ndbc_water_temperature_tk_var.set(water_temp_display)
            self.ndbc_wave_direction_tk_var.set(ndbc_data['Wave Direction'])
            self.ndbc_baro_tk_var.set(ndbc_data['Atmospheric Pressure'])

    def tide(self, predicts, measurements):
        """Plot grid lines, predicted tide level and annotation"""
        max_tide = -99
        min_tide = 99
        y_divs = 12
        if measurements:
            for chkent in measurements:
                if chkent[1] > max_tide:
                    max_tide = chkent[1]
                if chkent[1] < min_tide:
                    min_tide = chkent[1]
        if predicts:
            for chkent in predicts:
                if chkent[2] > max_tide:
                    max_tide = chkent[2]
                if chkent[2] < min_tide:
                    min_tide = chkent[2]
        min_y = int(round(min_tide-0.5,0))
        max_y = int(round(max_tide+0.5,0))
        y_divs = int((max_y-min_y))
        self.y_grid_size = (self.canvas_height-self.y_start)/(y_divs+1)
        print ('max_tide: '+str(max_tide)+' min_tide: '+str(min_tide)+' y_divs: '+str(y_divs))
        self.plot_window.delete("all")
        #
        # Draw grid lines
        #
        self.plot_window.create_line(
          self.x_plot_start, self.y_plot_start, self.x_plot_start,
          self.canvas_height-self.y_grid_size, fill="black")
        self.plot_window.create_line(
          self.canvas_width-1, self.y_plot_start, self.canvas_width-1,
          self.canvas_height-self.y_grid_size, fill="black")
        for x in range(0,y_divs+1):
            if x == y_divs or x == 0:
                 self.plot_window.create_line(
                   self.x_plot_start,self.y_grid_size*x+self.y_plot_start,
                   self.canvas_width, self.y_grid_size*x+self.y_plot_start,
                   fill="black")
            else:
                 self.plot_window.create_line(
                   self.x_plot_start, self.y_grid_size*x+self.y_plot_start,
                   self.canvas_width, self.y_grid_size*x+self.y_plot_start,
                   fill="gray")
            self.plot_window.create_text(
              10,self.canvas_height-((x+1)*self.y_grid_size),
              fill="black", text=str(x+min_y), font=("Arial", 10))
   
        mid_point = (self.canvas_width-30)/2+30
        self.plot_window.create_line(mid_point, self.y_plot_start, mid_point,
          self.canvas_height-self.y_grid_size, fill="RoyalBlue3", width=2)
        #
        # Plot Predicted tide and High and Low Tide Annotation
        #
        for pidx, entry in enumerate(predicts):
            if pidx == 0:
                start_plot_x = (self.x_plot_start+entry[1]*
                  (self.canvas_width-30)/86400/2)
                start_plot_y = entry[2]*self.y_grid_size+(self.y_grid_size*3)
                preliminary_tide_state = entry[3]
                start_plot_time = entry[0]
                continue
            thistate = entry[3]
            this_time = entry[0]
            try:
                hrmin = datetime.strftime(this_time, "%H:%M")
            except Exception as errmsg:
                #logging.warning(entry[0]+str(errmsg))
                continue
            linedate = datetime.strftime(this_time, "%d %b")  
            end_plot_x = (self.x_plot_start+entry[1]*
              (self.canvas_width-30)/86400/2)
            end_plot_y = entry[2]*self.y_grid_size+(self.y_grid_size*3)
            self.plot_window.create_line(
              start_plot_x, self.canvas_height-start_plot_y, end_plot_x, 
              self.canvas_height-end_plot_y, fill="snow4", width=3)  
            if this_time.minute == 0 and this_time.hour % 2 == 0:
                self.plot_window.create_line(
                  start_plot_x,self.y_plot_start, start_plot_x,
                  self.canvas_height-self.y_grid_size, fill="gray")
            if this_time.minute == 0 and this_time.hour % 4 == 0:
                self.plot_window.create_text(
                  start_plot_x,self.canvas_height-20, fill="black",
                  text=hrmin, font=("Arial", 10))
                if (this_time.hour == 4 or this_time.hour == 12 or
                  this_time.hour == 20):
                    self.plot_window.create_text(
                      start_plot_x,self.canvas_height-6,
                      fill="black", text=linedate, font=("Arial", 10))
               
            if thistate == 'L' or thistate == 'H':
                peaks = format(entry[2],'.2f')+' '+hrmin
                if preliminary_tide_state == '':
                    preliminary_tide_state = thistate
                elif preliminary_tide_state != thistate:
                    preliminary_tide_state = thistate 
                    hbox = self.plot_window.create_text(
                      start_plot_x,self.canvas_height/2+40, width=48,
                      fill="gray30", text=peaks, font=("Arial", 12),
                      justify="center")
                    hboxcors = self.plot_window.bbox(hbox)
                    hboxwid = self.plot_window.create_rectangle(
                      hboxcors, outline="gray30", fill="white")
                    self.plot_window.tag_lower(hboxwid,hbox)
            start_plot_x = end_plot_x
            start_plot_y = end_plot_y
        """Plot measured tide"""
        tide = 0
        if measurements:
            start_time = datetime.strptime(measurements[0][0], "%Y-%m-%d %H:%M:%S")
            off_time = start_time.timestamp() - start_plot_time.timestamp()
            for pidx, entry in enumerate(measurements):
                try:
                    this_time = datetime.strptime(entry[0], "%Y-%m-%d %H:%M:%S")
                    plot_time = this_time.timestamp() - start_time.timestamp()
                    hrmin = datetime.strftime(this_time, "%H:%M")
                    linedate = datetime.strftime(this_time, "%d %b")
                except:
                    continue
                end_plot_x = (
                  int((plot_time+off_time)*(self.canvas_width-30)/86400/2+30))
                end_plot_y = entry[1]*self.y_grid_size+(self.y_grid_size*3)
                if pidx == 0:
                    start_plot_x = end_plot_x
                    start_plot_y = end_plot_y
                    continue           
                self.plot_window.create_line(
                  start_plot_x, self.canvas_height-start_plot_y, end_plot_x, 
                  self.canvas_height-end_plot_y, fill="RoyalBlue3", width=3)  
                thistate = entry[2]
                hourtime = this_time.hour
                if thistate != None and (thistate == 'low' or thistate == 'high'):
                    if (self.tide_turn_time == 0 or 
                      abs(hourtime-self.tide_turn_time) >= 3):
                        self.tide_turn_time = hourtime
                        peaks = format(entry[1],'.2f')+' '+hrmin
                        abox = self.plot_window.create_text(
                          start_plot_x,self.canvas_height/2, width=48,
                          fill="blue", text=peaks, font=("Arial", 12),
                          justify="center")
                        aboxcors = self.plot_window.bbox(abox)
                        aboxwid = self.plot_window.create_rectangle(
                          aboxcors, outline="blue", fill="white")
                        self.plot_window.tag_lower(aboxwid,abox)
                start_plot_x = end_plot_x
                start_plot_y = end_plot_y
            tide = measurements[len(measurements)-1][1]
        tide_text = format(tide, '.2f')+' Ft.'
        current_time = datetime.now()
        curhrmin = datetime.strftime(current_time, "%H:%M")
        self.plot_window.create_line(
          60, 15, 110, 15, fill="RoyalBlue3", width=3)
        self.plot_window.create_text(190,15,
           fill="RoyalBlue3", text="Actual Tide Trace",
           font=("Arial", 12, 'bold'))
        self.plot_window.create_line(
          270, 15, 320, 15, fill="RoyalBlue3", width=3)
        cdbox = self.plot_window.create_text(
           450, 17, fill="RoyalBlue3", text=" Current Tide "+
           tide_text+" ", font=("Arial", 14, 'bold'))
        tbox = self.plot_window.create_text(
          615,17, fill="black", text=" Time "+curhrmin+" ",
          font=("Arial", 14, 'bold'))
        cdboxcors = self.plot_window.bbox(cdbox)
        cdboxwid = self.plot_window.create_rectangle(
          cdboxcors, outline="RoyalBlue3", fill="white", width=2)
        self.plot_window.tag_lower(cdboxwid,cdbox)
        tboxcors = self.plot_window.bbox(tbox)
        tboxwid = self.plot_window.create_rectangle(
          tboxcors, outline="black", fill="white", width=2)
        self.plot_window.tag_lower(tboxwid,tbox)
        self.plot_window.create_line(810, 15, 860, 15, fill="gray", width=3)
        self.plot_window.create_text(950,15,
          fill="gray", text="Predicted Tide Trace",
          font=("Arial", 12, 'bold'))
        self.plot_window.create_line(1040, 15, 1090, 15,
          fill="gray", width=3)

