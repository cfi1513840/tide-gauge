#!/usr/bin/env python3
"""Find nearby NWS forecast grid cells containing requested data layers.

The starting location may be a latitude/longitude pair or a city and state.
Place names are geocoded once through OpenStreetMap Nominatim and cached. The
script then resolves the coordinates through api.weather.gov/points and
searches neighboring cells in the same Weather Forecast Office grid. Wave
height and wave period qualify only when they contain a value greater than zero.
Distances and initial courses are calculated from the source location to each
matching cell. Magnetic headings use the current World Magnetic Model through
the ``pygeomag`` package (install with ``python3 -m pip install pygeomag``).

No third-party Python packages are required.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://api.weather.gov"
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"


@dataclass
class Match:
    office: str
    grid_x: int
    grid_y: int
    latitude: float | None
    longitude: float | None
    distance_km: float | None
    true_bearing: float | None
    magnetic_heading: float | None
    url: str
    fields: dict[str, dict[str, Any]]


def get_json(url: str, user_agent: str, timeout: float, retries: int = 3) -> dict[str, Any]:
    headers = {
        "Accept": "application/geo+json",
        "User-Agent": user_agent,
    }
    for attempt in range(retries + 1):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
            time.sleep(delay)
        except URLError:
            if attempt == retries:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("request retry loop ended unexpectedly")


def ring_offsets(radius: int) -> Iterable[tuple[int, int]]:
    """Yield the perimeter of a square ring, closest offsets first."""
    if radius == 0:
        yield 0, 0
        return

    offsets = [
        (dx, dy)
        for dx in range(-radius, radius + 1)
        for dy in range(-radius, radius + 1)
        if max(abs(dx), abs(dy)) == radius
    ]
    yield from sorted(offsets, key=lambda item: item[0] ** 2 + item[1] ** 2)


def coordinate_pairs(value: Any) -> Iterable[tuple[float, float]]:
    """Extract (longitude, latitude) pairs from nested GeoJSON coordinates."""
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
    elif isinstance(value, list):
        for child in value:
            yield from coordinate_pairs(child)


def geometry_center(document: dict[str, Any]) -> tuple[float | None, float | None]:
    geometry = document.get("geometry") or {}
    # GeoJSON polygon rings repeat the first corner at the end. Deduplicating
    # prevents that corner from slightly biasing the calculated cell center.
    pairs = list(dict.fromkeys(coordinate_pairs(geometry.get("coordinates"))))
    if not pairs:
        return None, None
    longitude = sum(pair[0] for pair in pairs) / len(pairs)
    latitude = sum(pair[1] for pair in pairs) / len(pairs)
    return latitude, longitude


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def initial_true_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the initial great-circle bearing clockwise from true north."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = (
        math.cos(phi1) * math.sin(phi2)
        - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    )
    return math.degrees(math.atan2(y, x)) % 360.0


def angular_difference(first: float, second: float) -> float:
    """Return the smallest absolute separation between two headings."""
    return abs((first - second + 180.0) % 360.0 - 180.0)


def grid_geometry_basis(
    office: str,
    grid_x: int,
    grid_y: int,
    user_agent: str,
    timeout: float,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Get centers for the origin, next-X, and next-Y NWS grid cells."""
    centers: list[tuple[float, float]] = []
    for x, y in ((grid_x, grid_y), (grid_x + 1, grid_y), (grid_x, grid_y + 1)):
        document = get_json(f"{API_ROOT}/gridpoints/{office}/{x},{y}", user_agent, timeout)
        latitude, longitude = geometry_center(document)
        if latitude is None or longitude is None:
            raise RuntimeError(f"NWS did not return geometry for {office}/{x},{y}")
        centers.append((latitude, longitude))
    return centers[0], centers[1], centers[2]


def estimated_grid_center(
    basis: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
    dx: int,
    dy: int,
) -> tuple[float, float]:
    """Estimate a nearby cell center from the local NWS grid geometry."""
    origin, next_x, next_y = basis
    latitude = origin[0] + dx * (next_x[0] - origin[0]) + dy * (next_y[0] - origin[0])
    longitude = origin[1] + dx * (next_x[1] - origin[1]) + dy * (next_y[1] - origin[1])
    return latitude, longitude


def current_decimal_year() -> float:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    return now.year + (now - start).total_seconds() / (end - start).total_seconds()


def magnetic_declination(latitude: float, longitude: float, override: float | None) -> float:
    """Return east-positive magnetic declination at the source coordinates."""
    if override is not None:
        return override
    try:
        from pygeomag import GeoMag
    except ImportError as exc:
        raise RuntimeError(
            "magnetic headings require pygeomag; install it with "
            "'python3 -m pip install pygeomag', or supply --declination DEGREES"
        ) from exc

    result = GeoMag().calculate(
        glat=latitude,
        glon=longitude,
        alt=0,
        time=current_decimal_year(),
    )
    return float(result.d)


def layer_summary(layer: Any, require_positive: bool = False) -> dict[str, Any] | None:
    if not isinstance(layer, dict):
        return None
    usable = []
    for item in layer.get("values", []):
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if value is None:
            continue
        if require_positive and not (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0
        ):
            continue
        usable.append(item)
    if not usable:
        return None
    return {
        "uom": layer.get("uom"),
        "value_count": len(usable),
        "first_valid_time": usable[0].get("validTime"),
        "first_value": usable[0].get("value"),
    }


def inspect_cell(
    office: str,
    grid_x: int,
    grid_y: int,
    fields: list[str],
    positive_fields: set[str],
    origin_lat: float,
    origin_lon: float,
    user_agent: str,
    timeout: float,
    declination: float,
) -> Match | None:
    url = f"{API_ROOT}/gridpoints/{office}/{grid_x},{grid_y}"
    document = get_json(url, user_agent, timeout)
    properties = document.get("properties", {})

    summaries: dict[str, dict[str, Any]] = {}
    for field in fields:
        summary = layer_summary(properties.get(field), field in positive_fields)
        if summary is None:
            return None
        summaries[field] = summary

    latitude, longitude = geometry_center(document)
    distance = None
    true_bearing = None
    magnetic_heading = None
    if latitude is not None and longitude is not None:
        distance = haversine_km(origin_lat, origin_lon, latitude, longitude)
        true_bearing = initial_true_bearing(origin_lat, origin_lon, latitude, longitude)
        # NOAA's convention is: true = magnetic + east-positive declination.
        magnetic_heading = (true_bearing - declination) % 360.0

    return Match(
        office=office,
        grid_x=grid_x,
        grid_y=grid_y,
        latitude=latitude,
        longitude=longitude,
        distance_km=distance,
        true_bearing=true_bearing,
        magnetic_heading=magnetic_heading,
        url=url,
        fields=summaries,
    )


def read_geocode_cache(path: Path) -> dict[str, dict[str, Any]]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
        return content if isinstance(content, dict) else {}
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}


def write_geocode_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        print(f"Warning: could not update geocode cache {path}: {exc}", file=sys.stderr)


def geocode_place(
    place: str,
    user_agent: str,
    timeout: float,
    cache_path: Path,
) -> tuple[float, float, str]:
    key = " ".join(place.lower().split())
    cache = read_geocode_cache(cache_path)
    cached = cache.get(key)
    if isinstance(cached, dict) and "latitude" in cached and "longitude" in cached:
        return float(cached["latitude"]), float(cached["longitude"]), str(cached["display_name"])

    query = urlencode(
        {
            "q": place,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "us",
        }
    )
    results = get_json(f"{GEOCODER_URL}?{query}", user_agent, timeout)
    if not isinstance(results, list) or not results:
        raise ValueError(f"location was not found: {place}")

    result = results[0]
    latitude = float(result["lat"])
    longitude = float(result["lon"])
    display_name = str(result.get("display_name", place))
    cache[key] = {
        "latitude": latitude,
        "longitude": longitude,
        "display_name": display_name,
    }
    write_geocode_cache(cache_path, cache)
    return latitude, longitude, display_name


def resolve_location(args: argparse.Namespace) -> tuple[float, float]:
    if len(args.location) == 2:
        try:
            return float(args.location[0]), float(args.location[1])
        except ValueError:
            pass

    place = " ".join(args.location)
    latitude, longitude, display_name = geocode_place(
        place,
        args.user_agent,
        args.timeout,
        Path(args.geocode_cache).expanduser(),
    )
    print(
        f"Geocoded {place!r} as {display_name}: {latitude:.5f}, {longitude:.5f} "
        "(OpenStreetMap/Nominatim).",
        file=sys.stderr,
    )
    return latitude, longitude


def search(args: argparse.Namespace) -> list[Match]:
    origin_lat, origin_lon = resolve_location(args)
    declination = magnetic_declination(origin_lat, origin_lon, args.declination)
    direction = "E" if declination >= 0 else "W"
    print(
        f"Source magnetic declination: {abs(declination):.2f} degrees {direction}.",
        file=sys.stderr,
    )
    point_url = f"{API_ROOT}/points/{origin_lat:.4f},{origin_lon:.4f}"
    point = get_json(point_url, args.user_agent, args.timeout)
    properties = point.get("properties", {})
    office = properties["gridId"]
    origin_x = int(properties["gridX"])
    origin_y = int(properties["gridY"])

    grid_basis = None
    sector_width = args.sector if args.sector is not None else 90.0
    if args.heading is not None:
        grid_basis = grid_geometry_basis(
            office,
            origin_x,
            origin_y,
            args.user_agent,
            args.timeout,
        )
        print(
            f"Directional filter: magnetic heading {args.heading:.1f} degrees, "
            f"sector width {sector_width:.1f} degrees.",
            file=sys.stderr,
        )

    print(
        f"Resolved target to {office} grid {origin_x},{origin_y}; "
        f"searching rings {args.start_ring} through {args.max_rings} "
        f"for {', '.join(args.fields)}.",
        file=sys.stderr,
    )

    matches: list[Match] = []
    first_match_ring: int | None = None
    skipped_by_sector = 0

    for radius in range(args.start_ring, args.max_rings + 1):
        for dx, dy in ring_offsets(radius):
            grid_x, grid_y = origin_x + dx, origin_y + dy
            if grid_x < 0 or grid_y < 0:
                continue
            if grid_basis is not None:
                estimated_lat, estimated_lon = estimated_grid_center(grid_basis, dx, dy)
                estimated_true = initial_true_bearing(
                    origin_lat,
                    origin_lon,
                    estimated_lat,
                    estimated_lon,
                )
                estimated_magnetic = (estimated_true - declination) % 360.0
                if angular_difference(estimated_magnetic, args.heading) > sector_width / 2.0:
                    skipped_by_sector += 1
                    continue
            try:
                match = inspect_cell(
                    office,
                    grid_x,
                    grid_y,
                    args.fields,
                    set(args.positive_fields),
                    origin_lat,
                    origin_lon,
                    args.user_agent,
                    args.timeout,
                    declination,
                )
            except HTTPError as exc:
                # Cells outside a WFO's valid grid commonly return 404.
                if exc.code not in (404,):
                    print(f"Warning: HTTP {exc.code} for {office}/{grid_x},{grid_y}", file=sys.stderr)
                match = None
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"Warning: could not read {office}/{grid_x},{grid_y}: {exc}", file=sys.stderr)
                match = None

            if match is not None:
                matches.append(match)
                if first_match_ring is None:
                    first_match_ring = radius

            if args.delay:
                time.sleep(args.delay)

        print(
            f"Completed ring {radius}; matches so far: {len(matches)}; "
            f"cells skipped by sector: {skipped_by_sector}",
            file=sys.stderr,
        )

        # One additional ring reduces the chance that a corner cell in the
        # first matching ring is reported ahead of a closer axial cell.
        if (
            not args.full_search
            and first_match_ring is not None
            and radius >= first_match_ring + 1
        ):
            break

    matches.sort(
        key=lambda item: item.distance_km if item.distance_km is not None else math.inf
    )
    return matches[: args.limit]


def print_table(matches: list[Match], fields: list[str]) -> None:
    if not matches:
        print("No matching grid cells were found within the search area.")
        return

    header = [
        "distance_nm",
        "magnetic_heading",
        "grid",
        "latitude",
        "longitude",
        *fields,
        "url",
    ]
    rows: list[list[str]] = []
    for match in matches:
        row = [
            f"{match.distance_km / 1.852:.2f}" if match.distance_km is not None else "",
            f"{match.magnetic_heading:.1f}" if match.magnetic_heading is not None else "",
            f"{match.office}/{match.grid_x},{match.grid_y}",
            f"{match.latitude:.5f}" if match.latitude is not None else "",
            f"{match.longitude:.5f}" if match.longitude is not None else "",
        ]
        for field in fields:
            info = match.fields[field]
            row.append(f"{info['first_value']} {info['uom'] or ''}".strip())
        row.append(match.url)
        rows.append(row)

    widths = [
        max(len(header[index]), *(len(row[index]) for row in rows))
        for index in range(len(header) - 1)
    ]

    def formatted(row: list[str]) -> str:
        fixed = "  ".join(row[index].ljust(widths[index]) for index in range(len(widths)))
        return f"{fixed}  {row[-1]}"

    print(formatted(header))
    print(formatted(["-" * width for width in widths] + ["---"]))
    for row in rows:
        print(formatted(row))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find nearby api.weather.gov forecast grid cells in the same WFO "
            "whose requested layers contain usable values. Wave height and "
            "wave period must be greater than zero by default."
        )
    )
    parser.add_argument(
        "location",
        nargs="+",
        help='latitude longitude, or a city and state such as "Atlantic City, NJ"',
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=["waveHeight", "wavePeriod"],
        help="NWS grid layers that must all contain usable values",
    )
    parser.add_argument(
        "--positive-fields",
        nargs="+",
        default=["waveHeight", "wavePeriod"],
        help="requested layers that must contain at least one value greater than zero",
    )
    parser.add_argument(
        "--start-ring",
        type=int,
        default=0,
        help="first grid-cell ring to examine; lower-numbered inner rings are skipped",
    )
    parser.add_argument(
        "--max-rings",
        type=int,
        default=8,
        help="maximum grid-cell rings to examine (one cell is roughly 2.5 km)",
    )
    parser.add_argument(
        "--heading",
        type=float,
        help="center of the search sector in magnetic degrees (0 through less than 360)",
    )
    parser.add_argument(
        "--sector",
        type=float,
        help="total angular width of the directional search sector; default is 90 degrees",
    )
    parser.add_argument("--limit", type=int, default=10, help="maximum matches to print")
    parser.add_argument(
        "--full-search",
        action="store_true",
        help="scan every ring instead of stopping one ring after the first match",
    )
    parser.add_argument("--delay", type=float, default=0.10, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=20.0, help="request timeout in seconds")
    parser.add_argument(
        "--user-agent",
        default="nws-grid-search/1.0",
        help="identifying User-Agent; including your email or website is recommended",
    )
    parser.add_argument(
        "--geocode-cache",
        default=".nws_grid_search_geocodes.json",
        help="local cache used for city/state geocoding results",
    )
    parser.add_argument(
        "--declination",
        type=float,
        help=(
            "override source magnetic declination in degrees, east positive and west negative; "
            "otherwise calculate it with the current World Magnetic Model"
        ),
    )
    args = parser.parse_args()
    if (
        args.start_ring < 0
        or args.max_rings < 0
        or args.limit < 1
        or args.delay < 0
        or args.timeout <= 0
    ):
        parser.error("ring numbers/delay cannot be negative; limit/timeout must be positive")
    if args.start_ring > args.max_rings:
        parser.error("start-ring cannot be greater than max-rings")
    if args.heading is not None and not 0 <= args.heading < 360:
        parser.error("heading must be at least 0 and less than 360 degrees")
    if args.sector is not None and not 0 < args.sector <= 360:
        parser.error("sector must be greater than 0 and no more than 360 degrees")
    if args.sector is not None and args.heading is None:
        parser.error("sector requires heading")
    return args


def main() -> int:
    args = parse_args()
    try:
        matches = search(args)
    except (
        HTTPError,
        URLError,
        TimeoutError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"Unable to resolve or search the requested location: {exc}", file=sys.stderr)
        return 1
    print_table(matches, args.fields)
    return 0 if matches else 2


if __name__ == "__main__":
    raise SystemExit(main())
