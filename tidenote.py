#!/usr/bin/env python3
"""Standalone Notehub receiver — writes to sqlite3 and InfluxDB via existing modules."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

from tidehelper import Constants         
from tidedatabase import DbManage   

constants = Constants()
db = DbManage(constants)
SECRET = constants.NOTEHUB_SECRET      

HOST = "127.0.0.1"
PORT = 8088


class NotehubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.headers.get("X-Auth") != SECRET:
            self._reply(401, b"unauthorized")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            event = json.loads(self.rfile.read(length))
            records = self._normalize(event)
        except (ValueError, KeyError, TypeError):
            self._reply(400, b"bad request")
            return
        for record in records:
            #print (record)
            db.insert_tide(record)
        self._reply(200, b"ok")
    def _normalize(self, event):
        status = event.get("status", {})
        rssi = status.get("P")
        voltage = status.get("V")
        temp = status.get("t")
        station = 3
        records = []
        for m in event.get("measurements", []):
            records.append({
                "T": m["T"],          
                "R": m["D"],
                "M": m["M"],
                "P": rssi,
                "S": 3,
                "V": voltage,
                "t": temp
            })
        return records
        
    def _reply(self, code, body):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass                             # silence per-request stderr logging


def main():
    server = HTTPServer((HOST, PORT), NotehubHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()