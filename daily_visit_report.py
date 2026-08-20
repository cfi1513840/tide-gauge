"""
daily_visit_report.py

Drop-in class for generating a daily website-visit summary from an Apache2
access log, suitable for sending by email or SMS.

Intended use:
    - Apache is configured to rotate its log at midnight, so
      /var/log/apache2/access.log.1 always holds the *previous* full
      day's traffic once rotation has happened.
    - Some scheduler (cron, systemd timer, APScheduler, etc.) calls
      DailyVisitReport().get_daily_report() once a day at 07:00, after
      logrotate has run, and sends the returned string by email/SMS.

Example:
    from daily_visit_report import DailyVisitReport

    report = DailyVisitReport()
    text = report.get_daily_report()
    send_email(subject="Daily Website Activity", body=text)
"""

from __future__ import annotations

import re
from collections import OrderedDict, defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class DailyVisitReport:
    """
    Parses an Apache2 "combined" format access log and produces a plain-text
    summary of visits to a fixed set of tracked pages.

    Counting rule: a line counts as a "visit" to a tracked page if the
    request path (query string ignored) matches one of the tracked paths
    AND the response status is < 400 (i.e. it was actually served, not a
    404/403/5xx). This filters out the constant background noise of bots
    probing for pages that don't exist, while still counting real page
    loads regardless of HTTP method (GET, POST, HEAD) -- which matters for
    pages like the alert form CGI that are visited via POST.
    """

    # Ordered so the report always lists categories in this sequence,
    # even when a category had zero visits.
    CATEGORIES: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
        [
            ("Tide & Weather", ("/tide.html",)),
            ("Alert Login", ("/alertlogin.html",)),
            ("Alert Form", ("/cgi-bin/alertform.cgi",)),
            ("Alert Request", ("/cgi-bin/processalerts.cgi",)),
            ("Historical Analysis", ("/tideplot.html", "/cgi-bin/tideplot.cgi")),
        ]
    )

    # Apache "combined" log format:
    # %h %l %u %t "%r" %>s %b "%{Referer}i" "%{User-Agent}i"
    LOG_LINE_RE = re.compile(
        r'^(?P<host>\S+) (?P<ident>\S+) (?P<user>\S+) '
        r'\[(?P<time>[^\]]+)\] '
        r'"(?P<request>[^"]*)" '
        r'(?P<status>\d{3}) (?P<size>\S+) '
        r'"(?P<referer>[^"]*)" "(?P<agent>[^"]*)"'
    )

    # First token of the quoted request line, e.g. GET /tide.html HTTP/1.1
    REQUEST_LINE_RE = re.compile(r'^(?P<method>\S+) (?P<path>\S+) (?P<protocol>\S+)$')

    APACHE_TIME_FORMAT = "%d/%b/%Y:%H:%M:%S %z"
    REPORT_DATE_FORMAT = "%B %d, %Y"

    # tide.html auto-refreshes itself every 5 minutes. A repeat hit from the
    # same host is treated as an auto refresh (rather than a fresh page load)
    # only if BOTH hold: its Referer is the tide page itself, AND it lands
    # within +/- AUTO_REFRESH_TOLERANCE_SECONDS of exactly
    # AUTO_REFRESH_INTERVAL_SECONDS after that host's last tide.html hit.
    # A manual reload landing by chance in that narrow window is considered
    # negligibly unlikely.
    AUTO_REFRESH_CATEGORY = "Tide & Weather"
    AUTO_REFRESH_SOURCE_PATH = "/tide.html"
    AUTO_REFRESH_INTERVAL_SECONDS = 300
    AUTO_REFRESH_TOLERANCE_SECONDS = 5
    # How many of a host's most recent tide.html hits to check a new hit
    # against (not just the single most recent). 3 comfortably covers a
    # visitor with two or three tabs/windows open at once without
    # growing unbounded for a host that's been hammering the page.
    AUTO_REFRESH_RECENT_HITS = 3

    def __init__(self, log_path: str = "/var/log/apache2/access.log.1"):
        self.log_path = Path(log_path)

        # Build a flat lookup of tracked path -> category label, so
        # categorizing a single request is an O(1) dict lookup.
        self._path_to_category: dict[str, str] = {}
        for label, paths in self.CATEGORIES.items():
            for path in paths:
                self._path_to_category[path] = label

    def get_daily_report(self) -> str:
        """
        Read the access log and return a plain-text visit summary.

        This is the method meant to be called once a day (e.g. by a 07:00
        cron job) to retrieve the previous day's visit counts.
        """
        try:
            lines = self.log_path.read_text(errors="replace").splitlines()
        except FileNotFoundError:
            return f"Website Activity: log file not found at {self.log_path}"
        except OSError as exc:
            return f"Website Activity: unable to read log ({exc})"

        counts = OrderedDict((label, 0) for label in self.CATEGORIES)
        visitors: "OrderedDict[str, set[str]]" = OrderedDict(
            (label, set()) for label in self.CATEGORIES
        )
        auto_refresh_counts = OrderedDict((label, 0) for label in self.CATEGORIES)
        report_date: Optional[datetime] = None

        # Recent hit timestamps per host (not just the single most recent),
        # for auto-refresh interval detection on the tide.html category.
        # A visitor with more than one tab/window open to the page runs
        # multiple independent 300-second refresh cycles under the same
        # host -- interleaved, those look nothing like a clean 300-second
        # gap against only the single most-recent hit, even though every
        # one of them is still a genuine auto refresh. Checking against
        # the last few hits (not just the last one) recognizes each
        # interleaved cycle independently.
        recent_seen: "dict[str, deque[datetime]]" = defaultdict(
          lambda: deque(maxlen=self.AUTO_REFRESH_RECENT_HITS))

        for line in lines:
            if not line.strip():
                continue

            match = self.LOG_LINE_RE.match(line)
            if not match:
                continue

            line_time = self._parse_apache_time(match.group("time"))
            if report_date is None:
                report_date = line_time

            status = int(match.group("status"))
            if status >= 400:
                continue

            path = self._extract_path(match.group("request"))
            if path is None:
                continue

            label = self._path_to_category.get(path)
            if label is None:
                continue

            host = match.group("host")
            counts[label] += 1
            visitors[label].add(host)

            if label == self.AUTO_REFRESH_CATEGORY:
                if self._is_auto_refresh(host, line_time, match.group("referer"), recent_seen):
                    auto_refresh_counts[label] += 1
                if line_time is not None:
                    recent_seen[host].append(line_time)

        return self._format_report(report_date, counts, visitors, auto_refresh_counts)

    def _is_auto_refresh(
        self,
        host: str,
        line_time: Optional[datetime],
        referer: str,
        recent_seen: "dict[str, deque[datetime]]",
    ) -> bool:
        """
        True if this hit looks like tide.html's self-triggered 5-minute
        refresh rather than a fresh page load: the Referer must be the tide
        page itself, and the gap since ANY of this host's recent tide.html
        hits (not just the most recent one) must fall within
        AUTO_REFRESH_TOLERANCE_SECONDS of exactly
        AUTO_REFRESH_INTERVAL_SECONDS. Checking multiple recent hits (see
        AUTO_REFRESH_RECENT_HITS) correctly recognizes a visitor running
        more than one independently-refreshing tab/window from the same
        host, which a single-last-seen-timestamp check cannot.
        """
        if line_time is None or host not in recent_seen:
            return False

        if urlparse(referer).path != self.AUTO_REFRESH_SOURCE_PATH:
            return False

        return any(
          abs((line_time - prior).total_seconds() - self.AUTO_REFRESH_INTERVAL_SECONDS)
          <= self.AUTO_REFRESH_TOLERANCE_SECONDS
          for prior in recent_seen[host]
        )

    def _extract_path(self, request_line: str) -> Optional[str]:
        """
        Pull the path (no query string) out of a request line such as
        'GET /tide.html?screenwidth=980 HTTP/1.1'. Returns None for
        malformed request lines (e.g. '-' from a timed-out connection).
        """
        match = self.REQUEST_LINE_RE.match(request_line)
        if not match:
            return None
        return match.group("path").split("?", 1)[0]

    def _parse_apache_time(self, time_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(time_str, self.APACHE_TIME_FORMAT)
        except ValueError:
            return None

    def _format_report(
        self,
        report_date: Optional[datetime],
        counts: "OrderedDict[str, int]",
        visitors: "OrderedDict[str, set[str]]",
        auto_refresh_counts: "OrderedDict[str, int]",
    ) -> str:
        if report_date is not None:
            date_str = report_date.strftime(self.REPORT_DATE_FORMAT)
        else:
            date_str = "Unknown Date"

        lines = [f"Website Activity for {date_str}"]
        for label, count in counts.items():
            unique = len(visitors[label])
            line = f"{label}: {unique} Visitor{'s' if unique != 1 else ''} requesting {count} page load{'s' if count != 1 else ''}"

            refreshes = auto_refresh_counts[label]
            if label == self.AUTO_REFRESH_CATEGORY:
                line += f" ({refreshes} auto refresh{'es' if refreshes != 1 else ''})"

            lines.append(line)

        total_hits = sum(counts.values())
        total_unique = len(set().union(*visitors.values())) if visitors else 0
        lines.append(
            f"Total: {total_unique} Visitor{'s' if total_unique != 1 else ''} "
            f"requesting {total_hits} page load{'s' if total_hits != 1 else ''}"
        )

        return "\n".join(lines)


if __name__ == "__main__":
    # Quick manual test: DailyVisitReport("/path/to/sample/access_log.1").get_daily_report()
    import sys

    log_path = sys.argv[1] if len(sys.argv) > 1 else "/var/log/apache2/access.log.1"
    print(DailyVisitReport(log_path).get_daily_report())
