#!/usr/bin/env python3
"""Standalone Notehub receiver — writes to InfluxDB via existing modules."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# your existing modules
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
            record = self._normalize(event)
        except (ValueError, KeyError, TypeError):
            self._reply(400, b"bad request")
            return
        #db.insert_tide(record)              
        self._reply(200, b"ok")

    def _normalize(self, event):
        body = event.get("body", {})
        print(str(body))
        """
        return {                         # match what db.write() expects
            "measurement": "sensor",
            "tags": {"station": event.get("device", "unknown")},
            "timestamp": int(event["when"]),
            "fields": {
                "distance": float(body["distance"]),
                "raw_distance": float(body["raw_distance"]),
            },
        }
        """

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