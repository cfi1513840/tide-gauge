"""
visitor_diagnostic.py

Standalone, manually-run diagnostic tool. NOT part of tidehelper.py/tide.py
and not scheduled anywhere -- it's for investigating something you noticed
in a daily report (e.g. an unexpectedly high auto-refresh count) by breaking
that category down per host: how many hits, over what time span, whether it
looks like one continuous open tab or several separate visits, and roughly
where the IP address is from.

Requires: an internet connection at run time (for the geolocation lookups
against ipinfo.io) and the `daily_visit_report.py` module in the same
directory, since it reuses that module's log-parsing regexes and constants
rather than duplicating them.

Usage:
    python3 visitor_diagnostic.py [log_path] [category]

    log_path  defaults to /var/log/apache2/access.log.1
    category  defaults to "Tide & Weather" -- must match one of the labels
              in DailyVisitReport.CATEGORIES exactly (quote it if it has
              spaces, e.g. "Alert Login")

Example:
    python3 visitor_diagnostic.py /var/log/apache2/access.log.1 "Tide & Weather"

Notes on the geolocation lookups:
    - Uses ipinfo.io's free, unauthenticated endpoint. That's rate-limited
      (roughly 1,000 requests/day per source IP last we checked) -- plenty
      for occasional manual runs, but don't loop this over huge host lists.
    - Results are city/region/ISP level at best -- never a precise location,
      and can be well off for mobile carriers or VPN/proxy traffic.
    - If you hit rate limits or want higher accuracy, set an ipinfo.io API
      token in the IPINFO_TOKEN environment variable; the script will pick
      it up automatically and send it as a query parameter.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from daily_visit_report import DailyVisitReport

GEO_LOOKUP_TIMEOUT_SECONDS = 5


@dataclass
class HostActivity:
    host: str
    hit_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    # Each entry is (session_start, session_end, hits_in_session).
    sessions: list = field(default_factory=list)


def _parse_apache_time(report: DailyVisitReport, time_str: str) -> Optional[datetime]:
    return report._parse_apache_time(time_str)  # reuse, don't duplicate the format string


def collect_host_activity(
    log_path: str, category: str
) -> "tuple[Optional[datetime], dict[str, HostActivity]]":
    """
    Re-parses the log (independently of get_daily_report(), since we need
    per-host detail that the daily report intentionally doesn't track) and
    returns (report_date, {host: HostActivity}) for the requested category.
    """
    report = DailyVisitReport(log_path)

    if category not in report.CATEGORIES:
        valid = ", ".join(report.CATEGORIES)
        raise ValueError(f"Unknown category {category!r}. Valid categories: {valid}")

    try:
        lines = report.log_path.read_text(errors="replace").splitlines()
    except OSError as exc:
        raise SystemExit(f"Unable to read log at {log_path}: {exc}")

    activity: "dict[str, HostActivity]" = {}
    # Per-host running session state: (session_start_time, last_hit_time).
    open_sessions: "dict[str, tuple[datetime, datetime]]" = {}
    report_date: Optional[datetime] = None

    is_refresh_eligible = category == report.AUTO_REFRESH_CATEGORY

    for line in lines:
        if not line.strip():
            continue

        match = report.LOG_LINE_RE.match(line)
        if not match:
            continue

        line_time = _parse_apache_time(report, match.group("time"))
        if report_date is None:
            report_date = line_time

        status = int(match.group("status"))
        if status >= 400:
            continue

        path = report._extract_path(match.group("request"))
        if path is None:
            continue

        if report._path_to_category.get(path) != category:
            continue

        host = match.group("host")
        entry = activity.setdefault(host, HostActivity(host=host))
        entry.hit_count += 1
        if entry.first_seen is None or (line_time and line_time < entry.first_seen):
            entry.first_seen = line_time
        if line_time and (entry.last_seen is None or line_time > entry.last_seen):
            entry.last_seen = line_time

        if line_time is None:
            continue

        referer = match.group("referer")
        continues_session = False
        if host in open_sessions:
            session_start, last_hit = open_sessions[host]
            if is_refresh_eligible:
                continues_session = report._is_auto_refresh(
                    host, line_time, referer, {host: last_hit}
                )
            else:
                # No auto-refresh signature defined for this category --
                # just group hits within the same refresh interval window
                # as "the same visit" so a quick manual double-click
                # doesn't get logged as two separate sessions.
                gap = (line_time - last_hit).total_seconds()
                continues_session = gap <= report.AUTO_REFRESH_INTERVAL_SECONDS

        if continues_session:
            session_start, _ = open_sessions[host]
            open_sessions[host] = (session_start, line_time)
            # Extend the last session's end time and hit count.
            start, end, hits = entry.sessions[-1]
            entry.sessions[-1] = (start, line_time, hits + 1)
        else:
            open_sessions[host] = (line_time, line_time)
            entry.sessions.append((line_time, line_time, 1))

    return report_date, activity


def geolocate(host: str) -> str:
    """
    Best-effort IP geolocation via ipinfo.io. Returns a short human-readable
    string; never raises -- network failures just produce a fallback note,
    since this is a diagnostic convenience, not something worth crashing
    over. Reads an optional IPINFO_TOKEN environment variable for higher
    rate limits / accuracy.
    """
    token = os.environ.get("IPINFO_TOKEN", "").strip()
    url = f"https://ipinfo.io/{host}/json"
    if token:
        url += f"?token={token}"

    try:
        with urllib.request.urlopen(url, timeout=GEO_LOOKUP_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"(lookup failed: {exc})"

    if "bogon" in data:
        return "(private/reserved address, no geolocation available)"

    city = data.get("city", "")
    region = data.get("region", "")
    country = data.get("country", "")
    org = data.get("org", "")

    location = ", ".join(part for part in (city, region, country) if part) or "unknown location"
    return f"{location} ({org})" if org else location


def format_diagnostic(
    report_date: Optional[datetime], category: str, activity: "dict[str, HostActivity]"
) -> str:
    if report_date is not None:
        date_str = report_date.strftime(DailyVisitReport.REPORT_DATE_FORMAT)
    else:
        date_str = "Unknown Date"

    lines = [f"Visitor Diagnostic for {category} -- {date_str}", ""]

    if not activity:
        lines.append("No qualifying hits found for this category.")
        return "\n".join(lines)

    # Busiest host first.
    for host, entry in sorted(activity.items(), key=lambda kv: kv[1].hit_count, reverse=True):
        lines.append(f"Host: {host}")
        lines.append(f"  Total hits:    {entry.hit_count}")
        if entry.first_seen and entry.last_seen:
            span = entry.last_seen - entry.first_seen
            lines.append(f"  First seen:    {entry.first_seen.strftime('%H:%M:%S')}")
            lines.append(f"  Last seen:     {entry.last_seen.strftime('%H:%M:%S')}")
            lines.append(f"  Active span:   {span}")
        lines.append(f"  Session count: {len(entry.sessions)}")
        for i, (start, end, hits) in enumerate(entry.sessions, start=1):
            duration = end - start
            lines.append(
                f"    Session {i}: {start.strftime('%H:%M:%S')}-{end.strftime('%H:%M:%S')} "
                f"({duration}, {hits} hit{'s' if hits != 1 else ''})"
            )
        lines.append(f"  Location:      {geolocate(host)}")
        lines.append("")

    return "\n".join(lines).rstrip()


def main() -> None:
    log_path = sys.argv[1] if len(sys.argv) > 1 else "/var/log/apache2/access.log.1"
    category = sys.argv[2] if len(sys.argv) > 2 else DailyVisitReport.AUTO_REFRESH_CATEGORY

    report_date, activity = collect_host_activity(log_path, category)
    print(format_diagnostic(report_date, category, activity))


if __name__ == "__main__":
    main()
