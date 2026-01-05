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

        if Constants.SERIAL_PORTS != None:
            for port in Constants.SERIAL_PORTS:
                if port == 'USB0':
                    self.usb0_serial_input = serial.Serial(
                      '/dev/ttyUSB0',9600, 8, 'N', 1, timeout = 1000)
                    self.usb0_serial_input.reset_input_buffer()
                elif port == 'USB1':
                    self.usb1_serial_input = serial.Serial(
                      '/dev/ttyUSB1',9600, 8, 'N', 1, timeout = 1000)
                    self.usb1_serial_input.reset_input_buffer()
        self.tide_monitor()
        
    def tide_monitor(self):
        interval = 5.0
        next_time = time.monotonic()
        while True:
            print (str(datetime.now()))
            next_time += interval
            for port in Constants.SERIAL_PORTS:
                sensor_packet = self.get.read_sensor(port)
                if sensor_packet:
                    self.db.insert_tide(sensor_packet)
                    print (sensor_packet)
            delay = next_time - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                pass
#
#Start the ball rolling
#
tidemonitor = TideMonitor()

       