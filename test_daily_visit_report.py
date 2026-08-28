"""
test_daily_visit_report.py

Standalone smoke test for DailyVisitReport. Run this on its own, before
wiring the class into your existing module, to confirm it parses your
log correctly and produces the expected text output.

Usage:
    python3 test_daily_visit_report.py [path_to_log]

If no path is given, it defaults to /var/log/apache2/access.log.1
(the real location on the server). Point it at a sample log file to
test without touching production, e.g.:

    python3 test_daily_visit_report.py /path/to/access_log.1
"""

import sys

from daily_visit_report import DailyVisitReport


def main() -> None:
    log_path = sys.argv[1] if len(sys.argv) > 1 else "/var/log/apache2/access.log.1"

    print(f"Testing DailyVisitReport against: {log_path}\n")

    report = DailyVisitReport(log_path)
    text = report.get_daily_report()

    print("--- Report output ---")
    print(text)
    print("--- End of report ---\n")

    # A couple of basic sanity checks so a broken parse fails loudly
    # rather than silently producing a plausible-looking but wrong report.
    assert text.startswith("Website Activity for"), "Missing expected first line"
    assert "Total:" in text, "Missing Total line"

    print("Sanity checks passed.")


if __name__ == "__main__":
    main()
