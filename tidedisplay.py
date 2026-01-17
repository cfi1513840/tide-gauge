import tkinter as tk
import tkinter.font as tkfont
from tkinter import StringVar
from datetime import datetime, timedelta, timezone
import logging

class TideDisplay:

    def __init__(self, station, cons, tide_only, state):
        self.cons = cons
        self.state = state
        self.tide_only = tide_only
        self.active_station = station
        self.canvas_width = int(cons.TK_SCREEN_WIDTH)-25
        self.canvas_height = int(cons.TK_SCREEN_HEIGHT)-225
        self.y_start = 0
        self.y_plot_end = 30
        self.start_plot_x = 30
        self.last_baro = 0
        self.x_plot_start = 30
        self.y_plot_start = 30
        self.tide_turn_time = 0
        self.y_grid_size = (self.canvas_height-(self.y_plot_start+self.y_plot_end))/13
        self.master = tk.Tk()
        self.master.configure(background='LightBlue1')
        if int(cons.TK_FULLSCREEN) == 1:
            self.master.geometry(f"{int(cons.TK_SCREEN_WIDTH)}x{int(cons.TK_SCREEN_HEIGHT)}+0+0")
            self.master.attributes('-fullscreen', True)
            self.canvas_height = int(cons.TK_SCREEN_HEIGHT)-155
        else:
            self.master.geometry(f'{int(
              cons.TK_SCREEN_WIDTH)-20}x{int(cons.TK_SCREEN_HEIGHT)-40}+10+40')
        self.master.bind("<Escape>", lambda event: exit())
        if not self.tide_only:
            self.local_wx_time_tk_var = StringVar()
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
        self.title_bar_tk_var = StringVar()
        self.title_bar_tk_var.set(state.title_bar)
        self.tk_display_width_tk_var = StringVar()
        self.display_predicted_tide_tk_var = StringVar()
        self.station_battery_voltage_tk_var = StringVar()
        self.station_signal_strength_tk_var = StringVar()
        self.active_station_tk_var = StringVar()
        self.active_station_tk_var.set(str(self.active_station))
        self.tk_display_width_tk_var.set('1')
        self.display_predicted_tide_tk_var.set('1')
        #        self.master = tk.Tk()
        #self.master.configure(background='LightBlue1')
        #self.master.geometry('+10+40')
        #if int(cons.TK_FULLSCREEN) == 1:
        #    self.master.attributes('-fullscreen', True)
        #self.master.bind("<Escape>", lambda event: exit())

        # Create tkinter display format
        #
        proc_frame = tk.Frame(
          self.master,
          borderwidth = 2,
          highlightbackground = 'black',
          highlightthickness = 1,
          width = self.canvas_width,
          #height = self.canvas_height, pady=1)
          pady=1)
        proc_frame.pack(side='top', fill='x')
        proc_frame.pack_propagate(False)
        proc_frame.grid_columnconfigure(0, weight=2)
        proc_frame.grid_columnconfigure(1, weight=1)
        proc_frame.grid_columnconfigure(2, weight=1)
        proc_frame.grid_columnconfigure(3, weight=1)
        proc_frame.grid_columnconfigure(4, weight=1)
        proc_frame.grid_columnconfigure(5, weight=1)
        proc_frame.grid_columnconfigure(6, weight=1)
        proc_frame.grid_columnconfigure(7, weight=1)
        proc_frame.grid_columnconfigure(8, weight=2)

        proc_frame.grid_rowconfigure(0, weight=1)
        proc_frame.grid_rowconfigure(1, weight=1)
        proc_frame.grid_rowconfigure(2, weight=1)
        proc_frame.grid_rowconfigure(3, weight=1)
        proc_frame.grid_rowconfigure(4, weight=1)
        proc_frame.grid_rowconfigure(5, weight=1)
        if not self.tide_only:
            self.ndbc_title_tk_var.set(
              f'{self.cons.NDBC_TITLE}')
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Local Weather',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 0, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Air Temp',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 1, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Humidity',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 2, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Dew Pt',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 3, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Winds',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 4, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Gusts',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 5,sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Barometer',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 6, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Rain Rate',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 7, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Rain Today',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 0,
                    column = 8, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.local_wx_time_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 0, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.temperature_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 1, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.humidity_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 2, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.dew_point_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 3, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.wind_speed_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 4, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.wind_gust_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 5, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.baro_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 6, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.rain_rate_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 7, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.rain_today_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 1,
                    column = 8, sticky = tk.NSEW)
            tk.Label(proc_frame, fg='White', bg = 'DarkBlue',
                    textvariable = self.ndbc_title_tk_var,
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 2, column = 0,
                    columnspan = 9, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1',
                    text = 'Observation Time',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 0, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Air Temp',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 1, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Wave Hgt',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 2, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Wave Per',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 3, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Winds',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 4, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Gusts',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 5, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Barometer',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 6, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Water Temp',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 7, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'LightBlue1', text = 'Wave Direction',
                    font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 3,
                    column = 8, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_time_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 4,
                    column = 0, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_air_temperature_tk_var, font = ("Arial", 12,
                    'bold'), relief = tk.RIDGE).grid(row = 4,
                    column = 1, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_wave_height_tk_var, font = ("Arial", 12,
                    'bold'), relief = tk.RIDGE).grid(row = 4,
                    column = 2, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_wave_period_tk_var, font = ("Arial", 12,
                    'bold'), relief = tk.RIDGE).grid(row = 4,
                    column = 3, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_wind_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 4,
                    column = 4, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_gust_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 4,
                    column = 5, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_baro_tk_var, font = ("Arial", 12, 'bold'),
                    relief = tk.RIDGE).grid(row = 4,
                    column = 6, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable =
                    self.ndbc_water_temperature_tk_var,
                    font = ("Arial", 12, 'bold'), relief = tk.RIDGE).grid(
                    row = 4,
                    column = 7, sticky = tk.NSEW)
            tk.Label(proc_frame, bg = 'snow', textvariable = 
                    self.ndbc_wave_direction_tk_var,
                    font = ("Arial", 12, 'bold'), relief = tk.RIDGE).grid(
                    row = 4, column = 8, sticky = tk.NSEW)
                    
        sel_frame = tk.Frame(self.master,
          bg = 'LightBlue1', borderwidth = 2,
          highlightbackground='black', highlightthickness=1,
          height=45, pady=1)
        sel_frame.pack(side='top', fill='x')
        sel_frame.pack_propagate(False)

        tk.Label(sel_frame,bg = 'LightBlue1', textvariable =
                self.title_bar_tk_var, font = ("Arial", 12, 'bold'),
                relief = tk.RIDGE).grid(row = 1,
                column = 0, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text = " "+chr(8211)+' Active Sensor: ',
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
                borderwidth = 0, highlightthickness=0).grid(
                row = 1, column = 1, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'snow', textvariable =
                self.active_station_tk_var, font = ("Arial", 12,
                'bold'), relief = tk.RIDGE).grid(row = 1,
                column = 2, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text = " "+chr(8211)+' Bat Voltage: ',
            font = ("Arial", 12, 'bold'), relief = tk.RIDGE,
            borderwidth = 0, highlightthickness=0).grid(
            row = 1, column = 3, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'snow', textvariable =
                self.station_battery_voltage_tk_var,
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE
                ).grid(row = 1, column = 4,
                sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'LightBlue1', text = " "+chr(8211)+' Sig Strength: ',
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE
                ).grid(row = 1, column = 5, sticky = tk.NSEW)
        tk.Label(sel_frame,bg = 'snow', textvariable =
                self.station_signal_strength_tk_var,
                font = ("Arial", 12, 'bold'), relief = tk.RIDGE
                ).grid(row = 1, column = 6,
                sticky = tk.NSEW)
        self.plot_window = tk.Canvas(self.master, bg = "#E0F8F1",
                width = self.canvas_width, height=self.canvas_height)
        self.plot_window.pack(side='top', fill='both')
        
        logging.info('Tkinter display initialized')

    def update(self, weather, ndbc_data):
        """Update tkinter display"""
        self.title_bar_tk_var.set(self.state.title_bar)
        if weather:
            self.local_wx_time_tk_var.set(weather['obs_time'])
            wind_speed = weather['wind_speed']
            if wind_speed != 0 and wind_speed != '':
                self.wind_speed_tk_var.set(str(wind_speed)+ ' mph')
            else:
                self.wind_speed_tk_var.set('')
            self.temperature_tk_var.set(str(weather['temperature'])+'\u00b0 F')
            wind_gust = weather['wind_gust']
            if wind_gust != 0 and wind_gust != '':            
                self.wind_gust_tk_var.set(str(wind_gust)+ ' mph')
            else:
                self.wind_gust_tk_var.set('')
            self.humidity_tk_var.set(str(weather['humidity'])+ '%')
            self.dew_point_tk_var.set(str(weather['dewpoint'])+'\u00b0 F')
            rain_rate = weather['rain_rate']
            if rain_rate != 0 and rain_rate != '':
                self.rain_rate_tk_var.set(str(rain_rate)+' in/hr')
            else:
                self.rain_rate_tk_var.set('')
            rain_today = weather['rain_today']
            if rain_today != 0 and rain_today != '':
                self.rain_today_tk_var.set(str(rain_today)+' in')
            else:
                self.rain_today_tk_var.set('')
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
            air_temp_display = ''
            water_temp_display = ''
            self.ndbc_time_tk_var.set(ndbc_data['DateTime'])
            wind_display = ndbc_data['Wind Speed']
            if wind_display != 0 and wind_display != '' and wind_display != None:
                self.ndbc_wind_tk_var.set(wind_display+' kts')
            else:
                self.ndbc_wind_tk_var.set('')
            wind_gust_display = ndbc_data['Wind Gust']
            if wind_gust_display != 0 and wind_gust_display != '' and wind_gust_display != None:
                self.ndbc_gust_tk_var.set(wind_gust_display+' kts')
            else:
                self.ndbc_gust_tk_var.set('')
            wave_height_display = ndbc_data['Wave Height']
            if wave_height_display != '':
                self.ndbc_wave_height_tk_var.set(wave_height_display+' ft')
            else:
                self.ndbc_wave_height_tk_var.set('')
            wave_period_display = ndbc_data['Wave Period']
            if wave_period_display != '':
                self.ndbc_wave_period_tk_var.set(wave_period_display+' secs')
            else:
                self.ndbc_wave_period_tk_var.set('')
            air_temp_display = ndbc_data['Air Temperature']
            water_temp_display = ndbc_data['Water Temperature']
            if air_temp_display != '':
                air_temp_display = air_temp_display+'\u00b0 F' 
            if water_temp_display != '':
                water_temp_display = water_temp_display+'\u00b0 F' 
            self.ndbc_air_temperature_tk_var.set(air_temp_display)
            self.ndbc_water_temperature_tk_var.set(water_temp_display)
            self.ndbc_wave_direction_tk_var.set(ndbc_data['Wave Direction'])
            self.ndbc_baro_tk_var.set(ndbc_data['Atmospheric Pressure'])

    def tide(self, predicts, measurements):
        """Plot grid lines,  predicted tide level and annotation"""
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
        self.y_grid_size = (self.canvas_height-(self.y_plot_start+self.y_plot_end))/y_divs
        self.y_grid_size = round(self.y_grid_size, 2)
        #print (str(min_y), str(max_y), str(y_divs), str(self.y_grid_size))
        self.plot_window.delete("all")
        #
        # Draw grid lines
        #
        self.plot_window.create_line(
          self.x_plot_start, self.y_plot_start, self.x_plot_start,
          self.canvas_height-self.y_plot_end, fill="black")
        self.plot_window.create_line(
          self.canvas_width-1, self.y_plot_start, self.canvas_width-1,
          self.canvas_height-self.y_plot_end, fill="black")
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
              10,self.canvas_height-((x)*self.y_grid_size+self.y_plot_end),
              fill="black", text=str(x+min_y), font=("Arial", 10))
   
        mid_point = (self.canvas_width-30)/2+30
        self.plot_window.create_line(mid_point, self.y_plot_start, mid_point,
          self.canvas_height-self.y_plot_end, fill="RoyalBlue3", width=2)
        #
        # Plot Predicted tide and High and Low Tide Annotation
        #
        for pidx, entry in enumerate(predicts):
            if pidx == 0:
                start_plot_x = (self.x_plot_start+entry[1]*
                  (self.canvas_width-30)/86400/2)
                start_plot_y = self.y_plot_end+((entry[2]-min_y)*self.y_grid_size)
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
            end_plot_y = self.y_plot_end+((entry[2]-min_y)*self.y_grid_size)
            self.plot_window.create_line(
              start_plot_x, self.canvas_height-start_plot_y, end_plot_x, 
              self.canvas_height-end_plot_y, fill="snow4", width=3)  
            if this_time.minute == 0 and this_time.hour % 2 == 0:
                self.plot_window.create_line(
                  start_plot_x,self.y_plot_start, start_plot_x,
                  self.canvas_height-self.y_plot_end, fill="gray")
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
                end_plot_y = self.y_plot_end+((entry[1]-min_y)*self.y_grid_size)
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
        text_font = tkfont.Font(family="Arial", size=12, weight="bold")
        start_text = self.x_plot_start
        self.plot_window.create_line(
          start_text, 15, start_text+30, 15, fill="RoyalBlue3", width=3)
        text_field = "Actual Tide Trace"
        text_size = text_font.measure(text_field)
        self.plot_window.create_text(start_text+35,15,
           anchor="w", fill="RoyalBlue3", text=text_field,
           font=("Arial", 12, 'bold'))
        self.plot_window.create_line(
          start_text+40+text_size, 15, start_text+70+text_size,
          15, fill="RoyalBlue3", width=3)
        cdbox = self.plot_window.create_text(
           self.canvas_width/2-145, 18, fill="RoyalBlue3", text=" Current Tide "+
           tide_text+" ", font=("Arial", 14, 'bold'))
        tbox = self.plot_window.create_text(
          self.canvas_width/2+10,18, fill="black", text=" Time "+curhrmin+" ",
          font=("Arial", 14, 'bold'))
        cdboxcors = self.plot_window.bbox(cdbox)
        cdboxwid = self.plot_window.create_rectangle(
          cdboxcors, outline="RoyalBlue3", fill="white", width=2)
        self.plot_window.tag_lower(cdboxwid,cdbox)
        tboxcors = self.plot_window.bbox(tbox)
        tboxwid = self.plot_window.create_rectangle(
          tboxcors, outline="black", fill="white", width=2)
        self.plot_window.tag_lower(tboxwid,tbox)
        text_field = "Predicted Tide Trace"
        text_size = text_font.measure(text_field)
        start_text = self.canvas_width-(text_size+70)
        self.plot_window.create_line(start_text, 15, start_text+30, 15,
          fill="gray", width=3)
        self.plot_window.create_text(start_text+35,15,
          anchor="w", fill="gray", text=text_field,
          font=("Arial", 12, 'bold'))
        self.plot_window.create_line(start_text+40+text_size, 15,
          start_text+70+text_size, 15,
          fill="gray", width=3)

