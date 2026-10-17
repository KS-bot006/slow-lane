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


def open_share(inputs: Inputs) -> float:
    """Return the share of requests without a closed date."""
    counts = row_counts(inputs)
    data_lines = counts[("lines", "lines_read")] - counts[("lines", "header_lines")]
    return counts.get(("drop", "open_no_closed_date"), 0) / data_lines


def section_dataset(inputs: Inputs) -> list[str]:
    """Write the section about the data, the windows, and the dropped rows."""
    manifest = inputs.manifest
    counts = row_counts(inputs)
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
    label = "Share of open requests (no closed date)"
    rows.append([label, percent(open_share(inputs), 2), profile])
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


def plural(number: int, singular: str, many: str) -> str:
    """Return the number with the singular or the plural word."""
    return f"{number} {singular if number == 1 else many}"


def spark_partitions(inputs: Inputs) -> list[str]:
    """Write the partition table and the Spark context sentence."""
    frame = inputs.spark["partitions.csv"]
    groups = frame.groupby("rdd_name", sort=False)["rows"].agg(["count", "sum"])
    rows = [[name, count(row["count"]), count(row["sum"]), source("partitions.csv")]
            for name, row in groups.iterrows()]
    context = inputs.spark["spark_context.csv"].iloc[0]
    return [
        f"The master is {context['master']}. The default parallelism is "
        f"{context['default_parallelism']} and the computer has {context['cores']} "
        f"cores. Source: {source('spark_context.csv')}.",
        "",
    ] + table(["RDD", "Partitions", "Rows", "Source"], rows)


def spark_lineage(inputs: Inputs) -> list[str]:
    """Write the sentence about the dependency types of the lineage."""
    narrow = inputs.lineage.count("(narrow)")
    shuffle = inputs.lineage.count("(shuffle)")
    return [
        "The lineage lists "
        f"{plural(narrow, 'narrow dependency', 'narrow dependencies')} and "
        f"{plural(shuffle, 'shuffle dependency', 'shuffle dependencies')}. "
        "Source: results/spark/lineage.txt."
    ]


def spark_cache(inputs: Inputs) -> list[str]:
    """Write the cache timing table and the cache storage sentence."""
    timing = inputs.spark["cache_timing.csv"]
    by_variant = {name: group.sort_values("run")["seconds"].tolist()
                  for name, group in timing.groupby("variant")}
    rows = [[name, *[f"{value:.3f}" for value in values],
             f"{sum(values) / len(values):.3f}"]
            for name, values in by_variant.items()]
    header = ["Variant"] + [f"Run {i + 1} (s)" for i in range(len(rows[0]) - 2)]
    cached = by_variant["cache"]
    later = sum(cached[1:]) / len(cached[1:])
    plain = sum(by_variant["no_cache"]) / len(by_variant["no_cache"])
    storage = inputs.spark["cache_storage.csv"].iloc[0]
    return [
        "Seconds for one count of the clean rows. "
        f"Source: {source('cache_timing.csv')}.",
        "",
    ] + table(header + ["Mean (s)"], rows) + [
        "",
        f"The first cached run takes {cached[0]:.3f} seconds, because it fills the "
        f"cache. The mean of the next cached runs is {later:.3f} seconds. "
        f"The mean without the cache is {plain:.3f} seconds.",
        "",
        f"The cache holds {storage['cached_partitions']} of "
        f"{storage['total_partitions']} partitions, with "
        f"{count(storage['memory_bytes'])} bytes in memory and "
        f"{count(storage['disk_bytes'])} bytes on disk. "
        f"Source: {source('cache_storage.csv')}.",
    ]


def spark_fault(inputs: Inputs) -> list[str]:
    """Write the sentence about the fault tolerance check."""
    frame = inputs.spark["fault_tolerance.csv"]
    same = bool(frame["equal"].astype(str).str.lower().eq("true").all())
    result = "are the same" if same else "differ"
    seconds = float(frame["recompute_seconds"].iloc[0])
    return [
        f"After unpersist, Spark recomputes the clean rows in {seconds:.3f} seconds. "
        f"The count and the sum of the days {result} before and after. "
        "This is a simulation, because a local run has no executor that can fail. "
        f"Source: {source('fault_tolerance.csv')}."
    ]


def section_spark(inputs: Inputs) -> list[str]:
    """Write the section about the Spark processing."""
    lines = ["## Spark processing", ""]
    for part in (spark_partitions, spark_lineage, spark_cache, spark_fault):
        lines += part(inputs) + [""]
    return lines[:-1]


RANKINGS = (
    ("Problem types", "rank_complaint_type.csv", "complaint_type"),
    ("Agencies", "rank_agency.csv", "agency"),
    ("Boroughs", "rank_borough.csv", "borough"),
    ("ZIP codes", "rank_zip.csv", "zip"),
)
TOP = 5


def interval(row: pd.Series) -> str:
    """Return the 95 percent interval of a row as text."""
    return f"{percent(row['wilson_low'])} to {percent(row['wilson_high'])}"


def top_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the rows with the highest slow share."""
    return frame.sort_values(["slow_share", "n"], ascending=False).head(TOP)


def dominant_agencies(inputs: Inputs, types: pd.Series) -> dict[str, str]:
    """Return the dominant agency of each problem type."""
    owner = inputs.tables["type_owner.csv"].set_index("complaint_type")
    return {name: owner.loc[name, "dominant_agency"] for name in types}


def owner_sentence(owners: dict[str, str]) -> str:
    """Name the agency or agencies that own most of the slowest problem types."""
    tally: dict[str, int] = {}
    for agency in owners.values():
        tally[agency] = tally.get(agency, 0) + 1
    most = max(tally.values())
    leaders = sorted(name for name, number in tally.items() if number == most)
    total = len(owners)
    if len(leaders) == 1:
        text = f"Agency {leaders[0]} is the dominant agency of {most} of the {total}"
    else:
        names = ", ".join(leaders[:-1]) + f" and {leaders[-1]}"
        text = f"Agencies {names} are each the dominant agency of {most} of the {total}"
    return f"{text} slowest problem types. Source: {source('type_owner.csv')}."


def section_slowness(inputs: Inputs) -> list[str]:
    """Write the five slowest groups of each ranking, with their intervals."""
    lines = ["## Slowness findings", ""]
    owners: dict[str, str] = {}
    for title, name, column in RANKINGS:
        top = top_rows(inputs.tables[name])
        if column == "complaint_type":
            owners = dominant_agencies(inputs, top[column])
        rows = [[str(row[column]), count(row["n"]), percent(row["slow_share"]),
                 interval(row)] + ([owners[row[column]]] if owners and
                                   column == "complaint_type" else [])
                for _, row in top.iterrows()]
        header = [title, "Requests", "Slow share", "95% interval"]
        if column == "complaint_type":
            header.append("Dominant agency")
        lines += [f"The {TOP} slowest groups. Source: {source(name)}.", ""]
        lines += table(header, rows) + [""]
    return lines + [owner_sentence(owners)]


MODEL_NAMES = {
    "majority": "the majority class",
    "history_rule": "the history rule",
    "logistic_regression": "Logistic Regression",
    "random_forest": "the Random Forest",
    "random_forest_no_history": "the Random Forest without history features",
}
TABLE_NAMES = {
    "majority": "Majority class",
    "history_rule": "History rule",
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "random_forest_no_history": "Random Forest without history",
}
COMPARED = (("f1", "F1"), ("auc_roc", "AUC ROC"), ("auc_pr", "AUC PR"))
BASELINES = ("majority", "history_rule", "logistic_regression")
EQUAL_TOLERANCE = 0.0005


def compare(value: float, other: float) -> str:
    """Return better, equal, or worse for a value against another value."""
    if abs(value - other) <= EQUAL_TOLERANCE:
        return "equal"
    return "better" if value > other else "worse"


def comparison_lines(models: pd.DataFrame) -> list[str]:
    """Write one sentence for each metric and each baseline of the Random Forest."""
    forest = models.loc["random_forest"]
    lines = []
    for baseline in BASELINES:
        for column, label in COMPARED:
            other = models.loc[baseline, column]
            word = compare(forest[column], other)
            tail = "to" if word == "equal" else "than"
            lines.append(
                f"- On {label}, the Random Forest is {word} {tail} "
                f"{MODEL_NAMES[baseline]} ({forest[column]:.3f} against {other:.3f})."
            )
    return lines


def section_models(inputs: Inputs) -> list[str]:
    """Write the model metrics and the comparison of the Random Forest."""
    models = inputs.tables["metrics_by_model.csv"].set_index("model")
    rows = [[TABLE_NAMES[name]] + [f"{row[column]:.3f}" for column in (
        "accuracy", "precision", "recall", "f1", "auc_roc", "auc_pr")]
        for name, row in models.iterrows()]
    best = models["f1"].idxmax()
    without = models.loc["random_forest_no_history", "f1"]
    forest = models.loc["random_forest", "f1"]
    return [
        "## Model results",
        "",
        "Metrics of the slow class on the test window at the threshold 0.5. "
        f"Source: {source('metrics_by_model.csv')}.",
        "",
    ] + table(["Model", "Accuracy", "Precision", "Recall", "F1", "AUC ROC", "AUC PR"],
              rows) + [
        "",
        f"The model with the highest F1 is {MODEL_NAMES[best]} "
        f"({models.loc[best, 'f1']:.3f}).",
        "",
        "The Random Forest against each baseline:",
        "",
    ] + comparison_lines(models) + [
        "",
        f"Without the history features, the F1 of the Random Forest is {without:.3f}. "
        f"With them it is {forest:.3f}.",
    ]


def section_limits(inputs: Inputs) -> list[str]:
    """Write the section about the limits of the results."""
    models = inputs.tables["metrics_by_model.csv"].set_index("model")
    precision = models["precision"]
    return [
        "## Limits",
        "",
        f"- Open requests are left out. They are {percent(open_share(inputs), 2)} "
        "of the requests. This favors fast closures.",
        f"- The data covers {inputs.manifest['year']}. "
        "The test window is the last quarter.",
        "- A closed request is not always a fixed problem.",
        "- N is the same for all problem types. "
        "Agencies have different service targets.",
        "- The class weights make precision lower at the threshold 0.5. "
        f"The precision of the Random Forest is {precision['random_forest']:.3f}. "
        f"The precision of the history rule is {precision['history_rule']:.3f}.",
        "",
        f"Source of the precision values: {source('metrics_by_model.csv')}.",
    ]


Section = Callable[[Inputs], list[str]]
SECTIONS: list[Section] = [
    section_dataset, section_target, section_spark, section_slowness,
    section_models, section_limits,
]


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
