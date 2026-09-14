"""tidemonitor.py

Headless alternative to tide.py: reads LoRa sensor packets and writes
them to the databases (via the same ReadSensor/DbManage classes
tide.py uses) on a 5-second loop, with none of tide.py's Tk display,
web/CGI generation, or alert logic. Intended for a collector-only
deployment where local display isn't needed.

Runs directly at import time (no `if __name__ == "__main__"` guard --
this module is meant to be executed as a script, not imported), and
refuses to start if tide.py is already running (scans /proc for it),
since both processes writing to the same sqlite3/InfluxDB databases
concurrently would conflict.
"""
import serial
import time
import os
from datetime import datetime, timedelta
from tidehelper import Constants, ValType
from tideget import ReadSensor
from tidedatabase import DbManage

class TideMonitor:
    """Read sensor readings from serial ports and write to databases"""
    def __init__(self):
        self.db = DbManage(Constants)
        self.get = ReadSensor(Constants, ValType())

        for pid in os.listdir('/proc'):
            if not pid.isdigit():
                continue

            with open(f'/proc/{pid}/cmdline', 'r') as f:
                cmdline = f.read()

            if 'tide.py' in cmdline:
                print ('tidemonitor.py cannot be run concurrently with tide.py')
                exit()
        
        self.tide_monitor()
        
    def tide_monitor(self):
        interval = 5.0
        next_time = time.monotonic()
        while True:
            #print (str(datetime.now()))
            next_time += interval
            for port in Constants.SERIAL_PORTS:
                sensor_packet = self.get.read_sensor(port)
                if sensor_packet:
                    self.db.insert_tide(sensor_packet)
                    #print (sensor_packet)
            delay = next_time - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                pass

#
#Start the ball rolling
#
tidemonitor = TideMonitor()

       