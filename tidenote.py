#!/usr/bin/env python3
"""Non-blocking Notehub receiver.

Designed to be driven from the main tide.py loop instead of running as a
separate process. Folding it into the main process eliminates the SQLite
write-lock contention that occurs when two processes each hold their own
connection: there is now a single process and a single shared DbManage
instance, so all writes are serialized through one connection.

Usage from tide.py:

    from tidenote import NotehubReceiver

    # Reuse the SAME db instance the main loop already writes through.
    receiver = NotehubReceiver(constants, db)        # db = your DbManage

    while running:
        ...                                           # normal tide work
        receiver.poll()                               # returns immediately
        ...

    receiver.close()                                  # on shutdown
"""
import json
import select
import time
from http.server import HTTPServer, BaseHTTPRequestHandler


class NotehubHandler(BaseHTTPRequestHandler):
    # Bound the per-connection socket so a slow/stuck client cannot hang the
    # main loop. The connection socket inherits this timeout.
    timeout = 5

    def do_POST(self):
        if self.headers.get("X-Auth") != self.server.secret:
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
            # print(record)
            self.server.db.insert_tide(record)
        self._reply(200, b"ok")

    def _normalize(self, event):
        status = event.get("status", {})
        rssi = status.get("P")
        voltage = status.get("V")
        temp = status.get("t")
        # sensor_id is the Notecard firmware's own 3-char identity string
        # (e.g. "BEL", "PRO"), reported in the event's status.S field. This
        # is distinct from "S" below, which stays the numeric station
        # number (1-3) to preserve existing legacy processing.
        sensor_id = status.get("S")
        station = self.server.station
        # Sensor height above MLLW, from tide.py's already-cached
        # stationNcal values (set fresh each poll() call as
        # self.server.station_cal), not a fresh sqlite3 query per record.
        height_ft = getattr(self.server, 'station_cal', {}).get(station)
        records = []
        for m in event.get("measurements", []):
            records.append({
                "T": m["T"],
                "R": m["D"],
                "M": m["M"],
                "P": rssi,
                "S": station,
                "I": sensor_id,
                "H": height_ft,
                "V": voltage,
                "t": temp,
            })
        return records

    def _reply(self, code, body):
        try:
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass        # client (Notehub) already hung up; data was still written

    def log_message(self, *args):
        pass  # silence per-request stderr logging


class NotehubReceiver:
    """A pollable HTTP receiver. Does not block the caller."""

    def __init__(self, constants, db, host="127.0.0.1", port=8088):
        self.server = HTTPServer((host, port), NotehubHandler)
        # handle_request() will fall through via handle_timeout() instead of
        # blocking if (somehow) nothing is actually ready.
        self.server.timeout = 0
        # Make secret and the shared db available to every handler instance.
        self.server.secret = constants.NOTEHUB_SECRET
        self.server.db = db

    def poll(self, station, max_requests=50):
        """Handle every request currently queued, then return immediately.

        Returns the number of requests handled this call. If nothing is
        waiting, returns 0 without blocking. max_requests caps how many are
        drained per call so a flood cannot starve the main loop.
        """
        self.server.station = station
        handled = 0
        while handled < max_requests and self._has_pending():
            try:
                self.server.handle_request()
            except OSError:
                break
            handled += 1
        return handled

    def _has_pending(self):
        # timeout=0 -> pure poll, never blocks.
        readable, _, _ = select.select([self.server.fileno()], [], [], 0)
        return bool(readable)

    def close(self):
        self.server.server_close()


def main():
    """Standalone mode, retained for testing/back-compat.

    Polls in a tight loop with a short sleep instead of serve_forever().
    In production, prefer driving NotehubReceiver.poll() from tide.py and
    passing in the shared db instance.
    """
    import time
    from tidehelper import Constants
    from tidedatabase import DbManage

    constants = Constants()
    db = DbManage(constants)
    receiver = NotehubReceiver(constants, db)
    try:
        while True:
            if receiver.poll() == 0:
                time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.close()


if __name__ == "__main__":
    main()