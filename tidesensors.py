"""tidesensors.py

What tide.py needs to know about its up-to-three tide sensors ("slots"
1-3), and the one place readings from Notehub or InfluxDB Cloud are
turned into database rows and alert checks.

Slot types come from tide.env and are fixed for the life of tide.py:

    STATION<n>_TYPE='lora'    LoRa receiver on a serial port (SERIAL_PORTS)
    STATION<n>_TYPE='note'    Notecard, posted to tide.py by a Notehub route
    STATION<n>_TYPE='cloud'   any sensor already in InfluxDB Cloud, read by
                              tidecloud.CloudReader
    STATION<n>_TYPE=''        no sensor in this slot

A station reads either from Notehub or from the cloud, never both
(station_mode()). LoRa slots can sit beside either.

s<n>enable in the iparams table is a shut-off valve: a disabled slot's
readings are not stored and not checked for alerts, whatever the path.
It is re-read every minute, so a slot can be shut off without a restart.

Notecard and cloud readings name their sensor by its 3-character ID
("PRO"); STATION<n>_SENSOR_ID in tide.env says which slot that is.
"""
import logging
from datetime import datetime

VALID_TYPES = ('lora', 'note', 'cloud', '')
SLOTS = (1, 2, 3)


class StationConfigError(Exception):
    """tide.env (or the iparams fallback) describes a station tide.py
    can't run: an unknown type, Notehub and cloud slots together, or a
    slot missing the setting its type needs."""


def resolve_station_types(env_types, iparams):
    """Slot types from tide.env's STATION<n>_TYPE (env_types: {n: str or
    None}, None when the line is missing). A missing line falls back to
    the iparams s<n>type column, which held the types before they moved
    to tide.env, so an upgraded station keeps working until tide.env is
    updated. Returns (types, notes) where notes lists the fallbacks used.
    """
    types = {}
    notes = []
    for n in SLOTS:
        value = env_types.get(n)
        if value is None and f's{n}type' not in iparams:
            # iparams no longer has the column (drop_iparams_types.py).
            value = ''
            notes.append(
              f"tide.env has no STATION{n}_TYPE; treating slot {n} as "
              f"empty. Add STATION{n}_TYPE to tide.env.")
        elif value is None:
            value = (iparams.get(f's{n}type') or '')
            value = str(value).strip().lower()
            notes.append(
              f"tide.env has no STATION{n}_TYPE; using iparams s{n}type "
              f"'{value}'. Add STATION{n}_TYPE='{value}' to tide.env.")
        value = str(value).strip().strip('\'"').lower()
        if value not in VALID_TYPES:
            raise StationConfigError(
              f"STATION{n}_TYPE='{value}' is not one of lora, note, cloud "
              f"or blank")
        types[n] = value
    return types, notes


def station_mode(types):
    """'note' if any slot reads from Notehub, 'cloud' if any slot reads
    from InfluxDB Cloud, None if neither. Both at once is an error: a
    station uses one or the other."""
    kinds = set(types.values())
    if 'note' in kinds and 'cloud' in kinds:
        note = [n for n in SLOTS if types[n] == 'note']
        cloud = [n for n in SLOTS if types[n] == 'cloud']
        raise StationConfigError(
          f"slots {note} are 'note' and slots {cloud} are 'cloud'; a station "
          f"reads from Notehub or from InfluxDB Cloud, not both")
    if 'note' in kinds:
        return 'note'
    if 'cloud' in kinds:
        return 'cloud'
    return None


def check_station_config(types, cons):
    """Settings each type needs, checked once at startup. Raises
    StationConfigError naming what's missing."""
    ids = cons.STATION_SENSOR_IDS
    problems = []
    if any(t == 'lora' for t in types.values()) and not cons.SERIAL_PORTS:
        problems.append("a slot is 'lora' but SERIAL_PORTS is blank")
    if station_mode(types) == 'note' and not getattr(cons, 'NOTEHUB_SECRET', None):
        problems.append("a slot is 'note' but NOTEHUB_SECRET is not set in "
                        "tide_constants.json")
    cloud_ids = {}
    for n in SLOTS:
        if types[n] != 'cloud':
            continue
        sid = ids.get(n, '')
        if not sid:
            problems.append(f"slot {n} is 'cloud' but STATION{n}_SENSOR_ID "
                            f"is blank")
        elif not sid.isalnum():
            problems.append(f"STATION{n}_SENSOR_ID='{sid}' must be letters "
                            f"and digits only")
        elif sid in cloud_ids:
            problems.append(f"slots {cloud_ids[sid]} and {n} both read "
                            f"sensor {sid}")
        else:
            cloud_ids[sid] = n
    if types and station_mode(types) == 'cloud':
        for name in ('INFLUXDB_CLOUD_URL', 'INFLUXDB_CLOUD_BUCKET',
                     'INFLUXDB_CLOUD_TOKEN', 'INFLUXDB_MEASUREMENT'):
            if not getattr(cons, name, None):
                problems.append(f"a slot is 'cloud' but {name} is not set")
    if problems:
        raise StationConfigError('; '.join(problems))


class SensorContext:
    """Per-slot settings and the current state the readers need. tide.py
    creates one at startup and calls refresh() every 5-second pass, so
    the Notehub and cloud readers always see the current calibration,
    enable flags, active slot and weather without their own sqlite3
    access."""

    def __init__(self, cons, db, alerts, types):
        self.cons = cons
        self.db = db
        self.alerts = alerts
        self.types = dict(types)
        self.sensor_ids = dict(cons.STATION_SENSOR_IDS)
        self.cal = {n: None for n in SLOTS}
        self.enabled = {n: False for n in SLOTS}
        self.active_slot = None
        self.weather = {}
        self.ndbc_data = {}
        self.sunrise = None
        self.sunset = None
        self.debug = 0
        self._logged = set()

    def refresh(self, cal, enabled, active_slot, weather, ndbc_data,
                sunrise, sunset, debug):
        self.cal = dict(cal)
        self.enabled = {n: bool(enabled.get(n)) for n in SLOTS}
        self.active_slot = active_slot
        self.weather = weather
        self.ndbc_data = ndbc_data
        self.sunrise = sunrise
        self.sunset = sunset
        self.debug = debug

    def slots_of_type(self, kind):
        return [n for n in SLOTS if self.types.get(n) == kind]

    def log_once(self, key, message):
        """Warn once per distinct key, so a steady stream of readings for
        a misconfigured or shut-off slot doesn't flood newtide.log."""
        if key not in self._logged:
            self._logged.add(key)
            logging.warning(message)

    def accepts(self, slot, kind):
        """True if readings for this slot, arriving by this kind of path,
        should be stored: the slot exists, is that type, and is enabled."""
        if slot not in SLOTS:
            self.log_once(('noslot', kind, slot),
              f'Discarding {kind} reading for unknown slot {slot!r}')
            return False
        if self.types.get(slot) != kind:
            self.log_once(('type', kind, slot),
              f"Discarding {kind} reading for slot {slot}, which tide.env "
              f"sets as '{self.types.get(slot)}'")
            return False
        if not self.enabled.get(slot):
            self.log_once(('off', kind, slot),
              f'Discarding {kind} readings for slot {slot}: s{slot}enable '
              f'is off (logged once)')
            return False
        return True

    def slot_for_sensor_id(self, sensor_id, kind):
        """Slot of this type whose STATION<n>_SENSOR_ID matches. For a
        Notecard reading with no match, a station with exactly one 'note'
        slot and no sensor ID configured for it uses that slot -- how
        Notecard readings were assigned before slots were matched by ID.
        Returns None when no slot fits."""
        candidates = self.slots_of_type(kind)
        for n in candidates:
            if sensor_id and self.sensor_ids.get(n) == sensor_id:
                return n
        if (kind == 'note' and len(candidates) == 1 and
          not self.sensor_ids.get(candidates[0])):
            return candidates[0]
        self.log_once(('noid', kind, sensor_id),
          f"Discarding {kind} readings from sensor {sensor_id!r}: no "
          f"'{kind}' slot has STATION<n>_SENSOR_ID='{sensor_id}' in tide.env")
        return None


def ingest_records(ctx, records, kind):
    """Store Notecard or cloud readings and check alerts on each one.

    records: dicts in the Notecard record format ("T" epoch seconds,
    "R" mm, "S" slot, "I" sensor ID, "L" link type, "H" sensor height,
    "V" volts, ...), all for slots of this kind. Each accepted reading
    goes through db.insert_tide() (sqlite3 "sensors" table and local
    InfluxDB). Readings for the active slot are also checked against
    the alert table one at a time at their own time, so none in a batch
    is skipped. Returns the number passed to insert_tide() (which can
    still reject a reading as an outlier).
    """
    handled = 0
    for record in records:
        slot = record.get('S')
        if not ctx.accepts(slot, kind):
            continue
        ctx.db.insert_tide(record)
        handled += 1
        if (slot == ctx.active_slot and record.get('H') is not None and
          record.get('R') is not None and ctx.alerts is not None):
            tide_level = round(record['H'] - record['R']/304.8, 2)
            # Naive local time, matching datetime.now() and the LoRa
            # path, since both feed the same outlier tracker.
            candidate_time = datetime.fromtimestamp(record['T'])
            ctx.alerts.check_alerts(
              tide_level, ctx.weather, ctx.ndbc_data, ctx.sunrise,
              ctx.sunset, ctx.debug, slot, candidate_time)
    return handled
