"""Check the downloaded TSV file against data/MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from array import array
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "raw" / "311_2025.tsv"
MANIFEST_PATH = ROOT / "data" / "MANIFEST.json"
CREATED_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}$")
KNOWN_BOROUGHS = {"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND", "Unspecified"}
HASH_CHUNK_BYTES = 1024 * 1024


def sha256_of(path: Path) -> str:
    """Return the SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_duplicates(keys: array) -> int:
    """Count the unique_key values that appear more than once."""
    ordered = sorted(keys)
    return sum(1 for index in range(1, len(ordered)) if ordered[index] == ordered[index - 1])


def scan(path: Path, columns: list[str], year: int) -> tuple[dict, list[str]]:
    """Read the file once. Return the statistics and the list of problems."""
    problems: list[str] = []
    months: Counter = Counter()
    statuses: Counter = Counter()
    boroughs: Counter = Counter()
    keys = array("Q")
    open_rows = 0
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        header = handle.readline().rstrip("\n").split("\t")
        if header != columns:
            problems.append(f"Header differs from the manifest columns: {header}")
        for line_number, line in enumerate(handle, start=2):
            fields = line.rstrip("\n").split("\t")
            if len(fields) != len(columns):
                problems.append(f"Line {line_number} has {len(fields)} fields.")
                continue
            total += 1
            record = dict(zip(columns, fields))
            if record["unique_key"].isdigit():
                keys.append(int(record["unique_key"]))
            else:
                problems.append(f"Line {line_number}: unique_key is not a number.")
            created = record["created_date"]
            if not CREATED_DATE_PATTERN.match(created) or not created.startswith(str(year)):
                problems.append(f"Line {line_number}: bad created_date '{created}'.")
            months[created[:7]] += 1
            statuses[record["status"]] += 1
            boroughs[record["borough"]] += 1
            open_rows += record["closed_date"] == ""
            if len(problems) >= 20:
                problems.append("More than 20 problems. Stop reading.")
                break
    duplicates = count_duplicates(keys)
    if duplicates:
        problems.append(f"{duplicates} unique_key values appear more than once.")
    stats = {"total": total, "months": months, "statuses": statuses,
             "boroughs": boroughs, "open_rows": open_rows}
    return stats, problems


def main() -> int:
    """Verify the download and print the summary."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stats, problems = scan(DATA_PATH, manifest["columns"], manifest["year"])
    if dict(stats["months"]) != manifest["rows_per_month"]:
        problems.append("Rows per month differ from the manifest.")
    if stats["total"] != manifest["total_rows"]:
        problems.append(f"Total rows {stats['total']} differ from the manifest.")
    if sha256_of(DATA_PATH) != manifest["sha256"]:
        problems.append("The SHA-256 of the file differs from the manifest.")

    print(f"Total rows: {stats['total']}")
    print("Rows per month:")
    for month in sorted(stats["months"]):
        print(f"  {month}: {stats['months'][month]}")
    share = stats["open_rows"] / max(stats["total"], 1)
    print(f"Share of rows without closed_date: {share:.4%}")
    print("Status counts:")
    for value, count in stats["statuses"].most_common():
        print(f"  {value or '(empty)'}: {count}")
    print("Borough counts:")
    for value, count in stats["boroughs"].most_common():
        print(f"  {value or '(empty)'}: {count}")
        if value not in KNOWN_BOROUGHS:
            print(f"WARN new borough value: '{value}'")

    if problems:
        print("\n".join(problems))
        print("VERIFY FAILED")
        return 1
    print("VERIFY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
