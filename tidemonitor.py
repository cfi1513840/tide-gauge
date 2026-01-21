import serial
import time
from datetime import datetime, timedelta
from tidehelper import Constants, ValType
from tideget import ReadSensor
from tidedatabase import DbManage

class TideMonitor:
    """Read sensor readings from serial ports and write to databases"""
    def __init__(self):
        self.db = DbManage(Constants)
        self.get = ReadSensor(Constants, ValType())
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

       