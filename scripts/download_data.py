"""Download the 2025 NYC 311 requests from the city API into one TSV file."""
from __future__ import annotations

import csv
import hashlib
import http.client
import io
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "project.properties"
RAW_DIR = ROOT / "data" / "raw"
PARTS_DIR = RAW_DIR / "parts"
OUTPUT_PATH = RAW_DIR / "311_2025.tsv"
MANIFEST_PATH = ROOT / "data" / "MANIFEST.json"

DATASET_ID = "erm2-nwe9"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}"
COLUMNS = [
    "unique_key", "created_date", "closed_date", "status", "agency",
    "complaint_type", "descriptor", "location_type", "borough",
    "open_data_channel_type", "incident_zip",
]
PAGE_SIZE = 50000
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_WAIT_SECONDS = (2, 4, 8, 16, 32)
REQUEST_PAUSE_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 180
MAX_COUNT_DIFFERENCE = 0.001
USER_AGENT = "nyc311-student-project"
HASH_CHUNK_BYTES = 1024 * 1024

LOGGER = logging.getLogger("download_data")


def read_year(config_path: Path) -> int:
    """Read the year from the properties file."""
    for line in config_path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "year":
            return int(value.strip())
    raise SystemExit(f"Key 'year' is missing in {config_path}.")


def clean_value(value: str) -> str:
    """Replace tab, carriage return, and newline with a space and strip the ends."""
    for character in ("\t", "\r", "\n"):
        value = value.replace(character, " ")
    return value.strip()


def month_windows(year: int) -> list[tuple[str, str, str]]:
    """Return (label, start, end) for each month. The end is exclusive."""
    windows = []
    for month in range(1, 13):
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        windows.append((
            f"{year}-{month:02d}",
            f"{year}-{month:02d}-01T00:00:00",
            f"{next_year}-{next_month:02d}-01T00:00:00",
        ))
    return windows


def where_clause(start: str, end: str) -> str:
    """Build the SoQL filter for one created_date window."""
    return f"created_date >= '{start}' AND created_date < '{end}'"


def build_url(suffix: str, params: dict[str, str]) -> str:
    """Build an API URL. The suffix is .csv or .json."""
    return f"{ENDPOINT}{suffix}?{urllib.parse.urlencode(params)}"


def request_headers() -> dict[str, str]:
    """Return the request headers. Add the app token if the variable is set."""
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token
    return headers


def fetch(url: str) -> bytes:
    """Get a URL. Retry on throttle, server errors, and network errors."""
    tries = len(RETRY_WAIT_SECONDS) + 1
    last_problem = ""
    for attempt in range(tries):
        try:
            request = urllib.request.Request(url, headers=request_headers())
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read()
            time.sleep(REQUEST_PAUSE_SECONDS)
            return body
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUS_CODES:
                raise SystemExit(f"Request failed with HTTP {error.code}: {url}") from error
            last_problem = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.HTTPException) as error:
            last_problem = f"network error: {error}"
        if attempt < tries - 1:
            wait = RETRY_WAIT_SECONDS[attempt]
            LOGGER.warning("Try %d of %d failed (%s). Wait %d seconds.",
                           attempt + 1, tries, last_problem, wait)
            time.sleep(wait)
    raise SystemExit(
        f"Download failed after {tries} tries. Last problem: {last_problem}. "
        "Set SOCRATA_APP_TOKEN and run the script again."
    )


def api_count(start: str, end: str) -> int:
    """Ask the API for the number of requests in one window."""
    url = build_url(".json", {"$select": "count(*)", "$where": where_clause(start, end)})
    return int(json.loads(fetch(url))[0]["count"])


def parse_page(body: bytes) -> list[list[str]]:
    """Parse one CSV page and return the cleaned data rows."""
    rows = list(csv.reader(io.StringIO(body.decode("utf-8"))))
    if not rows or rows[0] != COLUMNS:
        found = rows[0] if rows else "no header"
        raise SystemExit(f"The API returned other columns than expected: {found}")
    cleaned = []
    for row in rows[1:]:
        if len(row) != len(COLUMNS):
            raise SystemExit(f"A row has {len(row)} fields, expected {len(COLUMNS)}.")
        cleaned.append([clean_value(value) for value in row])
    return cleaned


def download_month(label: str, start: str, end: str, part_path: Path) -> int:
    """Download one month to a part file and return the row count."""
    temporary_path = part_path.with_suffix(".tmp")
    total = 0
    offset = 0
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("\t".join(COLUMNS) + "\n")
        while True:
            url = build_url(".csv", {
                "$select": ",".join(COLUMNS),
                "$where": where_clause(start, end),
                "$order": "created_date,unique_key",
                "$limit": str(PAGE_SIZE),
                "$offset": str(offset),
            })
            rows = parse_page(fetch(url))
            for row in rows:
                handle.write("\t".join(row) + "\n")
            total += len(rows)
            print(f"  {label}: {total} rows", flush=True)
            if len(rows) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
    os.replace(temporary_path, part_path)
    return total


def count_part_rows(part_path: Path) -> int:
    """Count the data rows of a part file."""
    with part_path.open("r", encoding="utf-8") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def check_difference(label: str, rows: int, expected: int) -> None:
    """Stop if the rows differ from the API count by more than 0.1 percent."""
    difference = abs(rows - expected) / max(expected, 1)
    if difference > MAX_COUNT_DIFFERENCE:
        raise SystemExit(
            f"Month {label} has {rows} rows. The API count is {expected}. "
            f"The difference is {difference:.4%}, above {MAX_COUNT_DIFFERENCE:.1%}."
        )


def join_parts(part_paths: list[Path], output_path: Path) -> tuple[int, str]:
    """Join the part files into one TSV file. Return the row count and SHA-256."""
    temporary_path = output_path.with_suffix(".tmp")
    digest = hashlib.sha256()
    total = 0
    with temporary_path.open("wb") as handle:
        for index, part_path in enumerate(part_paths):
            with part_path.open("rb") as part:
                if index > 0:
                    part.readline()
                for line in part:
                    handle.write(line)
                    digest.update(line)
                    total += 1
    total -= 1
    os.replace(temporary_path, output_path)
    return total, digest.hexdigest()


def write_manifest(year: int, rows_per_month: dict[str, int], total: int, sha256: str) -> None:
    """Write data/MANIFEST.json."""
    manifest = {
        "dataset_id": DATASET_ID,
        "endpoint": f"{ENDPOINT}.csv",
        "year": year,
        "downloaded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "columns": COLUMNS,
        "rows_per_month": rows_per_month,
        "total_rows": total,
        "sha256": sha256,
    }
    temporary_path = MANIFEST_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, MANIFEST_PATH)


def main() -> int:
    """Download all months, join them, and write the manifest."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    year = read_year(CONFIG_PATH)
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    rows_per_month: dict[str, int] = {}
    part_paths: list[Path] = []
    for label, start, end in month_windows(year):
        part_path = PARTS_DIR / f"{label}.tsv"
        expected = api_count(start, end)
        if part_path.exists() and count_part_rows(part_path) == expected:
            rows = expected
            print(f"Skip {label}: part file has {rows} rows.", flush=True)
        else:
            print(f"Download {label}: API count {expected}.", flush=True)
            rows = download_month(label, start, end, part_path)
        check_difference(label, rows, expected)
        rows_per_month[label] = rows
        part_paths.append(part_path)
    total, sha256 = join_parts(part_paths, OUTPUT_PATH)
    write_manifest(year, rows_per_month, total, sha256)
    print(f"DOWNLOAD OK: {total} rows in {OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
