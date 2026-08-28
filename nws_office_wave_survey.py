#!/usr/bin/env python3
"""Survey selected East Coast NWS offices for wave-height/period grid data.

This is a batch wrapper for nws_grid_search.py (or a locally renamed
nws_search_grid.py). Each office is tested from a representative coastal
location and seaward magnetic sector. Results are written to CSV and printed
as a compact table.

FOUND is conclusive for the tested office. NOT_FOUND means that no qualifying
cell was found within the tested rings and sector; it is not proof that the
office never supplies the layers anywhere in its forecast area.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SurveyTarget:
    office: str
    location: str
    heading: float
    sector: float


# Broad sectors are intentional: this survey favors avoiding false negatives
# over minimizing every possible request.
TARGETS = [
    SurveyTarget("CAR", "Bar Harbor, ME", 180, 240),
    SurveyTarget("GYX", "Portland, ME", 135, 180),
    SurveyTarget("BOX", "Boston, MA", 90, 180),
    SurveyTarget("OKX", "Montauk, NY", 180, 240),
    SurveyTarget("PHI", "Atlantic City, NJ", 135, 180),
    SurveyTarget("LWX", "Annapolis, MD", 180, 360),
    SurveyTarget("AKQ", "Virginia Beach, VA", 90, 180),
    SurveyTarget("MHX", "Morehead City, NC", 180, 180),
    SurveyTarget("ILM", "Wilmington, NC", 135, 180),
    SurveyTarget("CHS", "Charleston, SC", 135, 180),
    SurveyTarget("JAX", "Jacksonville, FL", 90, 180),
    SurveyTarget("MLB", "Melbourne, FL", 90, 180),
    SurveyTarget("MFL", "Miami, FL", 90, 180),
    SurveyTarget("KEY", "Key West, FL", 180, 360),
]


def find_utility(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"grid-search utility was not found: {path}")
        return path

    script_directory = Path(__file__).resolve().parent
    for name in ("nws_search_grid.py", "nws_grid_search.py"):
        candidate = script_directory / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "place nws_office_wave_survey.py beside nws_grid_search.py, "
        "or specify --utility PATH"
    )


def parse_resolved_office(stderr: str) -> str:
    match = re.search(r"Resolved target to ([A-Z]{3}) grid", stderr)
    return match.group(1) if match else ""


def parse_first_result(stdout: str) -> dict[str, str]:
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    if len(lines) < 3 or not lines[0].startswith("distance_nm"):
        return {}
    headers = re.split(r" {2,}", lines[0].strip())
    values = re.split(r" {2,}", lines[2].strip(), maxsplit=len(headers) - 1)
    if len(headers) != len(values):
        return {}
    return dict(zip(headers, values))


def run_target(
    utility: Path,
    target: SurveyTarget,
    args: argparse.Namespace,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(utility),
        target.location,
        "--fields",
        "waveHeight",
        "wavePeriod",
        "--positive-fields",
        "waveHeight",
        "wavePeriod",
        "--start-ring",
        str(args.start_ring),
        "--max-rings",
        str(args.max_rings),
        "--heading",
        str(target.heading),
        "--sector",
        str(target.sector),
        "--limit",
        "1",
        "--delay",
        str(args.delay),
        "--timeout",
        str(args.timeout),
        "--user-agent",
        args.user_agent,
    ]

    print(
        f"Testing {target.office}: {target.location} "
        f"({target.heading:.0f} magnetic / {target.sector:.0f}-degree sector)...",
        file=sys.stderr,
        flush=True,
    )
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if args.verbose and completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)

    resolved = parse_resolved_office(completed.stderr)
    first = parse_first_result(completed.stdout)

    if resolved and resolved != target.office:
        status = "WRONG_OFFICE"
    elif completed.returncode == 0 and first:
        status = "FOUND"
    elif completed.returncode == 2:
        status = "NOT_FOUND"
    else:
        status = "ERROR"

    error = ""
    if status == "ERROR":
        stderr_lines = [line.strip() for line in completed.stderr.splitlines() if line.strip()]
        error = stderr_lines[-1] if stderr_lines else f"utility exit code {completed.returncode}"
    elif status == "WRONG_OFFICE":
        error = f"representative location resolved to {resolved}"

    return {
        "office": target.office,
        "resolved_office": resolved,
        "status": status,
        "location": target.location,
        "heading_magnetic": target.heading,
        "sector_degrees": target.sector,
        "start_ring": args.start_ring,
        "max_rings": args.max_rings,
        "distance_nm": first.get("distance_nm", ""),
        "result_heading_magnetic": first.get("magnetic_heading", ""),
        "grid": first.get("grid", ""),
        "latitude": first.get("latitude", ""),
        "longitude": first.get("longitude", ""),
        "wave_height": first.get("waveHeight", ""),
        "wave_period": first.get("wavePeriod", ""),
        "url": first.get("url", ""),
        "note": error,
    }


def write_csv(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)


def print_summary(results: list[dict[str, Any]]) -> None:
    headers = ["office", "resolved", "status", "location", "grid", "distance_nm", "note"]
    rows = [
        [
            str(result["office"]),
            str(result["resolved_office"]),
            str(result["status"]),
            str(result["location"]),
            str(result["grid"]),
            str(result["distance_nm"]),
            str(result["note"]),
        ]
        for result in results
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(len(row))))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run nws_grid_search.py for CAR GYX BOX OKX PHI LWX AKQ MHX ILM "
            "CHS JAX MLB MFL and KEY, then produce a CSV office survey."
        )
    )
    parser.add_argument("--utility", help="path to nws_grid_search.py or nws_search_grid.py")
    parser.add_argument("--start-ring", type=int, default=0)
    parser.add_argument("--max-rings", type=int, default=16)
    parser.add_argument("--delay", type=float, default=0.10, help="delay passed to each grid search")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--user-agent",
        default="nws-office-wave-survey/1.0",
        help="identifying User-Agent; including an email or website is recommended",
    )
    parser.add_argument(
        "--output",
        default="nws_office_wave_survey.csv",
        help="CSV output filename",
    )
    parser.add_argument("--verbose", action="store_true", help="show each grid search's progress")
    args = parser.parse_args()
    if args.start_ring < 0 or args.max_rings < 0:
        parser.error("ring numbers cannot be negative")
    if args.start_ring > args.max_rings:
        parser.error("start-ring cannot exceed max-rings")
    if args.delay < 0 or args.timeout <= 0:
        parser.error("delay cannot be negative and timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    try:
        utility = find_utility(args.utility)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    results = [run_target(utility, target, args) for target in TARGETS]
    output_path = Path(args.output).expanduser().resolve()
    write_csv(output_path, results)
    print_summary(results)
    print(f"\nCSV report: {output_path}")

    return 1 if any(result["status"] in ("ERROR", "WRONG_OFFICE") for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
