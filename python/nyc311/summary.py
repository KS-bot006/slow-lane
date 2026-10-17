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


MANIFEST = "data/MANIFEST.json"
ROW_COUNTS = "profile_row_counts.csv"


def row_counts(inputs: Inputs) -> dict[tuple[str, str], int]:
    """Return the profile row counts as a dict with the key (kind, name)."""
    frame = inputs.tables[ROW_COUNTS]
    return {(row.kind, row.name): int(row.rows) for row in frame.itertuples()}


def section_dataset(inputs: Inputs) -> list[str]:
    """Write the section about the data, the windows, and the dropped rows."""
    manifest = inputs.manifest
    counts = row_counts(inputs)
    data_lines = counts[("lines", "lines_read")] - counts[("lines", "header_lines")]
    rejected = sum(rows for (kind, _), rows in counts.items() if kind == "reject")
    drops = {name: rows for (kind, name), rows in counts.items() if kind == "drop"}
    clean = counts[("clean", "clean_rows")]
    if clean + sum(drops.values()) + rejected != manifest["total_rows"]:
        raise SummaryError("Clean, dropped, and rejected rows differ from the manifest")
    profile = source(ROW_COUNTS)
    rows = [
        ["Dataset ID", manifest["dataset_id"], MANIFEST],
        ["Download time (UTC)", manifest["downloaded_at_utc"], MANIFEST],
        ["Columns used", count(len(manifest["columns"])), MANIFEST],
        ["Requests downloaded", count(manifest["total_rows"]), MANIFEST],
        ["Lines rejected by the parser", count(rejected), profile],
        ["Clean rows", count(clean), profile],
    ]
    for window in ("history", "train", "test"):
        rows.append([f"Clean rows in the {window} window",
                     count(counts[("window", window)]), profile])
    for name in sorted(drops):
        rows.append([f"Rows dropped: {name}", count(drops[name]), profile])
    open_share = drops.get("open_no_closed_date", 0) / data_lines
    label = "Share of open requests (no closed date)"
    rows.append([label, percent(open_share, 2), profile])
    return [
        "## Dataset",
        "",
        f"The data is the NYC 311 service request dataset {manifest['dataset_id']} "
        f"from NYC Open Data. It holds {count(manifest['total_rows'])} requests that "
        f"were created in {manifest['year']}. Clean rows, dropped rows, and rejected "
        "lines add up to the number of requests.",
        "",
    ] + table(["Item", "Value", "Source"], rows)


def selected_threshold(inputs: Inputs) -> pd.Series:
    """Return the selected row of the threshold table. Check N in three files."""
    frame = inputs.tables["threshold_selection.csv"]
    chosen = frame[frame["selected"].astype(str).str.lower() == "true"]
    if len(chosen) != 1:
        raise SummaryError("The threshold table needs exactly one selected row.")
    days = int(chosen.iloc[0]["candidate_days"])
    if days != int(inputs.run_params["slow_threshold_days"]) or days != int(
        inputs.metrics["slow_threshold_days"]
    ):
        raise SummaryError("N differs between the threshold table and the run files.")
    return chosen.iloc[0]


def section_target(inputs: Inputs) -> list[str]:
    """Write the section about the target N and the slow share in each window."""
    chosen = selected_threshold(inputs)
    days = int(chosen["candidate_days"])
    frame = inputs.tables["threshold_selection.csv"]
    candidates = [
        [count(row.candidate_days), percent(row.slow_share, 2),
         "yes" if str(row.selected).lower() == "true" else "no"]
        for row in frame.itertuples()
    ]
    windows = [["history", count(chosen["history_rows"]), count(chosen["slow_rows"]),
                percent(chosen["slow_share"], 2), source("threshold_selection.csv")]]
    summary = inputs.tables["feature_summary.csv"].set_index("window")
    for window in ("train", "test"):
        row = summary.loc[window]
        windows.append([window, count(row["rows"]), count(row["slow_rows"]),
                        percent(row["slow_share"], 2), source("feature_summary.csv")])
    names = ", ".join(count(value) for value in frame["candidate_days"])
    return [
        "## Target",
        "",
        f"A request is slow when it takes more than {days} days to close. "
        f"ThresholdJob selected N = {days} from the history window. "
        f"The candidates were {names} days.",
        "",
        "Slow share of each candidate in the history window. "
        f"Source: {source('threshold_selection.csv')}.",
        "",
    ] + table(["N (days)", "Slow share", "Selected"], candidates) + [
        "",
        "Slow share of each window.",
        "",
    ] + table(["Window", "Rows", "Slow rows", "Slow share", "Source"], windows)


Section = Callable[[Inputs], list[str]]
SECTIONS: list[Section] = [section_dataset, section_target]


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
