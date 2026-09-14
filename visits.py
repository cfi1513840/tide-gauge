import re
from collections import defaultdict
from urllib.parse import urlsplit
from datetime import datetime

class Visitors:

    EVENTS = {
        "Tide & Weather": (
            "Tide",
            {"/tide.html"},
            {"GET", "POST"},
        ),
        "Alert Login": (
            "Login",
            {"/alertlogin.html"},
            {"GET"},
        ),
        "Alert Form Displayed": (
            "Form",
            {"/cgi-bin/alertform.cgi"},
            {"GET", "POST"},
        ),
        "Alert Request Processed": (
            "Alerts",
            {"/cgi-bin/processalerts.cgi"},
            {"POST"},
        ),
        "Historical Analysis": (
            "History",
            {"/tideplot.html"},
            {"GET", "POST"},
        ),
        "Historical Plot Generated": (
            "Plots",
            {"/cgi-bin/tideplot.cgi"},
            {"GET", "POST"},
        ),
    }

    BOT_PATTERN = re.compile(
        r"bot|spider|crawler|crawl|slurp|scan|scrapy|"
        r"wget|curl|python-requests|go-http-client|"
        r"headless|phantom|selenium|claude|bytespider|"
        r"applebot|oai-searchbot|mj12bot|domainscores|"
        r"petalbot|wp-safe-scanner",
        re.IGNORECASE,
    )

    LOG_PATTERN = re.compile(
        r'^(?P<ip>\S+) \S+ \S+ '
        r'\[(?P<time>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<url>\S+) [^"]*" '
        r'(?P<status>\d{3}) \S+ '
        r'"[^"]*" "(?P<agent>[^"]*)"'
    )

    def __init__(self, log_file):
        self.log_file = log_file
        
    def _initialize(self):
        self.report_date = None

        self.uses = defaultdict(int)
        self.visitors = defaultdict(set)

        self.bot_requests = 0
        self.unparsed_lines = 0

        self._path_lookup = self._create_path_lookup()

    def _create_path_lookup(self):
        """Create a lookup from a URL path to its report category."""

        path_lookup = {}

        for event_name, event_data in self.EVENTS.items():
            short_name, paths, methods = event_data

            for path in paths:
                path_lookup[path] = (event_name, methods)

        return path_lookup

    def _read_log(self):
        """Read and parse valid entries from the Apache log."""

        records = []

        with open(
            self.log_file,
            encoding="utf-8",
            errors="replace",
        ) as logfile:

            for line in logfile:
                match = self.LOG_PATTERN.match(line)

                if not match:
                    self.unparsed_lines += 1
                    continue

                request_time = datetime.strptime(
                    match.group("time"),
                    "%d/%b/%Y:%H:%M:%S %z",
                )

                records.append({
                    "date": request_time.date(),
                    "ip": match.group("ip"),
                    "method": match.group("method"),
                    "path": urlsplit(
                        match.group("url")
                    ).path,
                    "status": int(match.group("status")),
                    "agent": match.group("agent"),
                })

        return records

    def _analyze(self):
        """Analyze the most recent date contained in the log."""

        records = self._read_log()

        if not records:
            raise ValueError(
                f"No valid Apache entries found in {self.log_file}"
            )

        if self.report_date == None:
            self.report_date = records[0]["date"]

        for record in records:

            event = self._path_lookup.get(record["path"])

            if event is None:
                continue

            event_name, allowed_methods = event

            if record["method"] not in allowed_methods:
                continue

            # Count successful and cached responses
            if not 200 <= record["status"] < 400:
                continue

            agent = record["agent"]

            if (
                not agent
                or agent == "-"
                or self.BOT_PATTERN.search(agent)
            ):
                self.bot_requests += 1
                continue

            self.uses[event_name] += 1

            # Each IP/browser combination counts once per category
            visitor_id = (
                record["ip"],
                agent,
            )

            self.visitors[event_name].add(visitor_id)
       
    def email_report(self):
        """Return a plain-text report suitable for email."""

        date_text = self.report_date.strftime("%B %d, %Y")

        lines = [
            f"Website Activity Report — {date_text}",
            "",
        ]

        for event_name in self.EVENTS:
            use_count = self.uses[event_name]
            visitor_count = len(self.visitors[event_name])

            lines.append(
                f"{event_name}: "
                f"{use_count} uses, "
                f"{visitor_count} visitors"
            )

        lines.extend([
            "",
            f"Recognizable bot requests excluded: "
            f"{self.bot_requests}",
            "",
            "Uses: Total successful requests.",
            "Visitors: Distinct IP address/browser combinations.",
        ])

        if self.unparsed_lines:
            lines.append(
                f"Unrecognized log lines: {self.unparsed_lines}"
            )

        return "\n".join(lines)   
        

    def sms_report(self):
        """Return a compact report suitable for SMS."""

        date_text = self.report_date.strftime("%m/%d/%Y")
        parts = [f"Web {date_text}"]

        for event_name, event_data in self.EVENTS.items():
            short_name, paths, methods = event_data

            parts.append(
                f"{short_name} "
                f"{self.uses[event_name]}/"
                f"{len(self.visitors[event_name])}"
            )

        return "; ".join(parts) + ". Uses/visitors."

    def reports(self):
        """Return both email and SMS reports."""
        self._initialize()
        self._analyze()

        return self.email_report(), self.sms_report()
        
visits = Visitors("/var/log/apache2/access.log.1")
email_message, SMS_message = visits.reports()
print (email_message)
print (SMS_message)
