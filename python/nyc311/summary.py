"""Write docs/results_summary.md from the result files. Code fills every number."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from nyc311.config import read_properties

LOGGER = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path("data/MANIFEST.json")
METRICS_PATH = Path("results/metrics.json")
TABLES_DIR = Path("results/tables")
SPARK_DIR = Path("results/spark")
RUN_PARAMS_PATH = Path("data/processed/run_params.properties")
SUMMARY_PATH = Path("docs/results_summary.md")
TABLE_FILES = (
    "profile_row_counts.csv", "threshold_selection.csv", "feature_summary.csv",
    "rank_complaint_type.csv", "rank_agency.csv", "rank_borough.csv", "rank_zip.csv",
    "type_owner.csv", "metrics_by_model.csv",
)
SPARK_FILES = (
    "partitions.csv", "cache_timing.csv", "cache_storage.csv", "fault_tolerance.csv",
    "spark_context.csv",
)
TEXT_COLUMNS = {"zip": str, "hour": str, "month": str}


class SummaryError(Exception):
    """An input file is missing or a check failed."""


@dataclass(frozen=True)
class Inputs:
    """All files that the summary reads."""

    manifest: dict
    metrics: dict
    run_params: dict[str, str]
    tables: dict[str, pd.DataFrame]
    spark: dict[str, pd.DataFrame]
    lineage: str


def read_file(root: Path, relative: Path) -> Path:
    """Return the full path of an input file. Stop if the file is missing."""
    path = root / relative
    if not path.is_file():
        raise SummaryError(f"Input file not found: {relative}")
    return path


def read_csv(root: Path, relative: Path) -> pd.DataFrame:
    """Read one result table. The columns zip, hour, and month stay text."""
    return pd.read_csv(read_file(root, relative), dtype=TEXT_COLUMNS)


def load_inputs(root: Path) -> Inputs:
    """Read the manifest, the metrics, the result tables, and the Spark files."""
    manifest = json.loads(read_file(root, MANIFEST_PATH).read_text(encoding="utf-8"))
    metrics = json.loads(read_file(root, METRICS_PATH).read_text(encoding="utf-8"))
    lineage = read_file(root, SPARK_DIR / "lineage.txt").read_text(encoding="utf-8")
    return Inputs(
        manifest=manifest,
        metrics=metrics,
        run_params=read_properties(read_file(root, RUN_PARAMS_PATH)),
        tables={name: read_csv(root, TABLES_DIR / name) for name in TABLE_FILES},
        spark={name: read_csv(root, SPARK_DIR / name) for name in SPARK_FILES},
        lineage=lineage,
    )


def count(value: float) -> str:
    """Format a count without a thousands separator."""
    return str(int(round(value)))


def percent(value: float, digits: int = 1) -> str:
    """Format a share as a percent."""
    return f"{value * 100:.{digits}f}%"


def source(name: str) -> str:
    """Return the path of a source file as it appears in the repository."""
    if name == "data/MANIFEST.json" or name.startswith(("results/", "docs/")):
        return name
    folder = TABLES_DIR if name in TABLE_FILES else SPARK_DIR
    return (folder / name).as_posix()


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    """Return the lines of a Markdown table."""
    divider = ["---"] * len(header)
    lines = ["| " + " | ".join(row) + " |" for row in [header, divider] + rows]
    return lines


Section = Callable[[Inputs], list[str]]
SECTIONS: list[Section] = []


def render(inputs: Inputs) -> str:
    """Build the text of the summary from the sections."""
    lines = [
        "# Results summary",
        "",
        "Python code writes this file from the result files. "
        "Every number comes from a file in results/ or from data/MANIFEST.json. "
        "The source column or the source line names the file.",
        "",
    ]
    for section in SECTIONS:
        lines += section(inputs) + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="Repository root.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Write docs/results_summary.md and print SUMMARY OK."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    root = Path(args.root)
    try:
        text = render(load_inputs(root))
    except SummaryError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    output = root / SUMMARY_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"wrote {SUMMARY_PATH}")
    print("SUMMARY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
