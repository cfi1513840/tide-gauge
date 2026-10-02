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
from datetime import datetime

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
