"""tidetime.py

One place that turns a datetime into the clock time shown to people:
the Tk display, tide.html, tideplot.html, the weather page, the
sunrise/sunset title bar and alert messages all call format_time().

The clock is chosen by tide.env's 12H_TIME setting:
    12H_TIME=true    2:05 PM   (the default, also used when it's missing)
    12H_TIME=false   14:05

Kept free of other project imports (only os and datetime) so tideplot.py, which also
runs as a CGI script under Apache, can import it without pulling in
tidehelper.py and its credentials.

format_obs_time() does the same for the weather and NDBC observation
times, which tideget.py hands over as text ("Oct 02, 2026 13:47").

Log files, database timestamps, file names and anything parsed back
with strptime() keep their fixed 24-hour formats and must not use this.
"""
import os
from datetime import datetime, timedelta

_FALSE_WORDS = ('false', '0', 'no', 'off')


def use_12_hour():
    """True unless tide.env sets 12H_TIME to false/0/no/off. Read on each
    call, from the environment the caller's load_dotenv() filled in."""
    value = os.getenv('12H_TIME', 'true').strip().strip('\'"').lower()
    return value not in _FALSE_WORDS


def format_time(when, style='time'):
    """Format a datetime for display.

    style      12-hour          24-hour
    'time'     2:05 PM          14:05
    'hour'     2 PM             14:00   (bottom timeline labels on the hour)
    'datetime' 2026-10-02 2:05 PM   2026-10-02 14:05   (alert messages)
    """
    if style == 'datetime':
        return when.strftime('%Y-%m-%d') + ' ' + format_time(when, 'time')
    if not use_12_hour():
        return when.strftime('%H:00' if style == 'hour' else '%H:%M')
    hour = when.hour % 12 or 12
    suffix = 'AM' if when.hour < 12 else 'PM'
    if style == 'hour':
        return f'{hour} {suffix}'
    return f'{hour}:{when.minute:02d} {suffix}'


# A measured tide reading older than this is shown as "Last Measured ...
# at <time>" instead of "Measured Tide ...". Matches the 5-minute
# reporting gap the outlier filter and the plots treat as a break.
MEASURED_STALE_AFTER = timedelta(minutes=5)


def measured_tide_label(tide_text, reading_time, now=None):
    """Label for the measured tide box on tide.html and the Tk display.

    Returns (text, stale). A reading no more than MEASURED_STALE_AFTER
    old is "Measured Tide 7.82 ft"; an older one -- a sensor gap, a run
    of dropped phantom readings, or a Notecard between its reports -- is
    "Last Measured 4.43 ft at 10:28 AM", with the date added when the
    reading is from an earlier day. reading_time None: the plain label.
    """
    if now is None:
        now = datetime.now()
    if reading_time is None or now - reading_time <= MEASURED_STALE_AFTER:
        return f'Measured Tide {tide_text}', False
    when = format_time(reading_time)
    if reading_time.date() != now.date():
        when = reading_time.strftime('%b %d ') + when
    return f'Last Measured {tide_text} at {when}', True


# How tideget.py stores the local weather obs_time and the NDBC DateTime.
# tidedisplay.py and tidehtml.py also parse this back to check how old
# the data is, so the stored text keeps this format; only what's shown
# is converted.
OBS_TIME_FORMAT = '%b %d, %Y %H:%M'


def format_obs_time(text):
    """Show an observation time string ("Oct 02, 2026 13:47") with the
    date unchanged and the time per 12H_TIME ("Oct 02, 2026 1:47 PM").
    Anything that isn't in that format ('', 'Not Reporting') is
    returned as it is."""
    try:
        when = datetime.strptime(text, OBS_TIME_FORMAT)
    except (TypeError, ValueError):
        return text
    return when.strftime('%b %d, %Y ') + format_time(when)
