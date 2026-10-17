"""Tests for the results summary and its check command. Files hold fixture values."""
import json
from pathlib import Path

import pandas as pd
import pytest

from nyc311 import summary

MODELS = {
    "majority": (0.77, 0.0, 0.0, 0.0, 0.5, 0.23),
    "history_rule": (0.90, 0.81, 0.75, 0.78, 0.95, 0.84),
    "logistic_regression": (0.89, 0.71, 0.89, 0.79, 0.96, 0.86),
    "random_forest": (0.89, 0.70, 0.89, 0.784, 0.949, 0.81),
    "random_forest_no_history": (0.71, 0.44, 0.99, 0.61, 0.93, 0.77),
}


def write_csv(path: Path, columns: list[str], rows: list[list]) -> None:
    """Write a fixture CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)


def ranking_rows(names: list[str]) -> list[list]:
    """Return fixture ranking rows. The first name has the highest slow share."""
    return [[name, 1000 - index, 5.0, 0.9 - 0.1 * index, 0.8 - 0.1 * index,
             0.95 - 0.1 * index] for index, name in enumerate(names)]


def make_root(root: Path) -> Path:
    """Write a small and consistent set of result files under a fixture root."""
    tables, spark = root / "results/tables", root / "results/spark"
    rank = ["n", "mean_days", "slow_share", "wilson_low", "wilson_high"]
    for folder in ("data/processed", "results"):
        (root / folder).mkdir(parents=True)
    manifest = {
        "dataset_id": "abcd-1234", "year": 2025,
        "downloaded_at_utc": "2026-01-01T00:00:00Z", "columns": ["a", "b", "c"],
        "total_rows": 100,
    }
    (root / "data/MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "results/metrics.json").write_text(
        json.dumps({"slow_threshold_days": 3}), encoding="utf-8")
    (root / "data/processed/run_params.properties").write_text(
        "slow_threshold_days=3\n", encoding="utf-8")
    write_csv(tables / "profile_row_counts.csv", ["kind", "name", "rows"], [
        ["info", "partitions", 4], ["lines", "lines_read", 101],
        ["lines", "header_lines", 1], ["drop", "open_no_closed_date", 10],
        ["drop", "status_not_closed", 5], ["clean", "clean_rows", 85],
        ["window", "history", 40], ["window", "test", 25], ["window", "train", 20]])
    write_csv(tables / "threshold_selection.csv",
              ["candidate_days", "history_rows", "slow_rows", "slow_share", "selected"],
              [[1, 40, 16, 0.4, False], [3, 40, 8, 0.2, True], [7, 40, 4, 0.1, False]])
    write_csv(tables / "feature_summary.csv",
              ["window", "rows", "slow_rows", "slow_share"],
              [["test", 25, 5, 0.2], ["train", 20, 4, 0.2]])
    names = [f"TYPE {letter}" for letter in "ABCDEFG"]
    write_csv(tables / "rank_complaint_type.csv", ["complaint_type"] + rank,
              ranking_rows(names))
    write_csv(tables / "rank_agency.csv", ["agency"] + rank,
              ranking_rows(["X", "Y", "Z"]))
    write_csv(tables / "rank_borough.csv", ["borough"] + rank,
              ranking_rows(["B1", "B2"]))
    write_csv(tables / "rank_zip.csv", ["zip"] + rank,
              ranking_rows(["10001", "10002"]))
    owners = [[name, "AGENCY_" + ("ONE" if index < 3 else "TWO"), 1.0, 1000,
               0.5, 0.4, 0.6] for index, name in enumerate(names)]
    write_csv(tables / "type_owner.csv", ["complaint_type", "dominant_agency",
              "dominant_share", "n", "slow_share", "wilson_low", "wilson_high"], owners)
    write_csv(tables / "metrics_by_model.csv",
              ["model", "accuracy", "precision", "recall", "f1", "auc_roc", "auc_pr"],
              [[name, *values] for name, values in MODELS.items()])
    write_csv(spark / "partitions.csv", ["rdd_name", "partition_index", "rows"],
              [["base", 0, 50], ["base", 1, 51], ["coalesce_1", 0, 101]])
    write_csv(spark / "cache_timing.csv", ["variant", "run", "seconds"],
              [["no_cache", 1, 2.0], ["no_cache", 2, 2.0], ["cache", 1, 5.0],
               ["cache", 2, 0.1]])
    write_csv(spark / "cache_storage.csv", ["rdd_id", "name", "storage_level",
              "cached_partitions", "total_partitions", "memory_bytes", "disk_bytes"],
              [[1, "RDD", "Memory", 2, 2, 1000, 0]])
    write_csv(spark / "fault_tolerance.csv",
              ["check", "before", "after", "equal", "recompute_seconds"],
              [["row_count", 85, 85, True, 1.5], ["sum_days", 9.0, 9.0, True, 1.5]])
    write_csv(spark / "spark_context.csv", ["master", "default_parallelism", "cores"],
              [["local[*]", 4, 4]])
    (spark / "lineage.txt").write_text(
        "a (narrow)\nb (narrow)\nc (shuffle)\n", encoding="utf-8")
    return root


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """Return a fixture repository root."""
    return make_root(tmp_path)


def test_load_inputs_reads_every_file(root: Path) -> None:
    """Check that the loader reads the tables, the Spark files, and the lineage."""
    inputs = summary.load_inputs(root)
    assert inputs.manifest["dataset_id"] == "abcd-1234"
    assert set(inputs.tables) == set(summary.TABLE_FILES)
    assert set(inputs.spark) == set(summary.SPARK_FILES)
    assert inputs.lineage.count("(narrow)") == 2


def test_missing_input_names_the_file(root: Path) -> None:
    """Check that a missing file stops the run with its path."""
    (root / "results/tables/rank_zip.csv").unlink()
    with pytest.raises(summary.SummaryError, match="rank_zip.csv"):
        summary.load_inputs(root)


def test_dataset_section_has_the_counts_and_the_open_share(root: Path) -> None:
    """Check the clean rows, the drop reasons, and the share of open requests."""
    text = "\n".join(summary.section_dataset(summary.load_inputs(root)))
    assert "| Clean rows | 85 |" in text
    assert "| Rows dropped: open_no_closed_date | 10 |" in text
    assert "| Share of open requests (no closed date) | 10.00% |" in text
    assert "abcd-1234" in text


def test_dataset_section_stops_when_the_rows_do_not_add_up(root: Path) -> None:
    """Check that a row count that differs from the manifest stops the run."""
    manifest = json.loads((root / "data/MANIFEST.json").read_text(encoding="utf-8"))
    manifest["total_rows"] = 99
    (root / "data/MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(summary.SummaryError, match="differ from the manifest"):
        summary.section_dataset(summary.load_inputs(root))


def test_target_section_checks_n_in_three_files(root: Path) -> None:
    """Check the selected N and the stop when the run parameters differ."""
    text = "\n".join(summary.section_target(summary.load_inputs(root)))
    assert "more than 3 days" in text and "| 3 | 20.00% | yes |" in text
    (root / "data/processed/run_params.properties").write_text(
        "slow_threshold_days=7\n", encoding="utf-8")
    with pytest.raises(summary.SummaryError, match="N differs"):
        summary.section_target(summary.load_inputs(root))


def test_spark_sections_use_the_files(root: Path) -> None:
    """Check the partition table, the lineage counts, the cache times, and recovery."""
    inputs = summary.load_inputs(root)
    text = "\n".join(summary.section_spark(inputs))
    assert "| base | 2 | 101 |" in text and "| coalesce_1 | 1 | 101 |" in text
    assert "2 narrow dependencies and 1 shuffle dependency" in text
    assert "first cached run takes 5.000 seconds" in text
    assert "mean without the cache is 2.000 seconds" in text
    assert "are the same before and after" in text


def test_spark_fault_sentence_reports_a_difference(root: Path) -> None:
    """Check that an equal value of false changes the sentence."""
    write_csv(root / "results/spark/fault_tolerance.csv",
              ["check", "before", "after", "equal", "recompute_seconds"],
              [["row_count", 85, 84, False, 1.5]])
    text = "\n".join(summary.spark_fault(summary.load_inputs(root)))
    assert "differ before and after" in text


def test_slowness_section_lists_the_top_five_with_the_owner(root: Path) -> None:
    """Check the top five rows and the dominant agency sentence."""
    text = "\n".join(summary.section_slowness(summary.load_inputs(root)))
    assert "| TYPE A | 1000 | 90.0% | 80.0% to 95.0% | AGENCY_ONE |" in text
    assert "TYPE F" not in text and "| TYPE E |" in text
    assert "Agency AGENCY_ONE is the dominant agency of 3 of the 5" in text


def test_owner_sentence_names_every_agency_in_a_tie() -> None:
    """Check the sentence for one leader and for two agencies with the same count."""
    one = summary.owner_sentence({"a": "X", "b": "X", "c": "Y"})
    assert one.startswith("Agency X is the dominant agency of 2 of the 3")
    tie = summary.owner_sentence({"a": "X", "b": "Y"})
    assert tie.startswith("Agencies X and Y are each the dominant agency of 1 of the 2")


def test_compare_words_and_boundaries() -> None:
    """Check better, equal, and worse, with the tolerance."""
    assert summary.compare(0.80, 0.70) == "better"
    assert summary.compare(0.70, 0.80) == "worse"
    assert summary.compare(0.7000, 0.7004) == "equal"
    assert summary.compare(0.7000, 0.7010) == "worse"


def test_model_section_compares_with_each_baseline(root: Path) -> None:
    """Check the nine sentences and the words that the numbers give."""
    text = "\n".join(summary.section_models(summary.load_inputs(root)))
    sentences = [line for line in text.splitlines() if line.startswith("- On ")]
    assert len(sentences) == 9
    assert ("- On F1, the Random Forest is better than the history rule "
            "(0.784 against 0.780).") in text
    assert "On F1, the Random Forest is worse than Logistic Regression" in text
    assert "The model with the highest F1 is Logistic Regression (0.790)." in text


def test_limits_section_uses_the_precision_values(root: Path) -> None:
    """Check the numbers in the limits."""
    text = "\n".join(summary.section_limits(summary.load_inputs(root)))
    assert "They are 10.00% of the requests." in text
    assert "precision of the Random Forest is 0.700" in text
    assert "precision of the history rule is 0.810" in text


def test_render_and_main_write_a_clean_file(root: Path, capsys) -> None:
    """Check that the file has every section and no forbidden word."""
    assert summary.main(["--root", str(root)]) == 0
    text = (root / summary.SUMMARY_PATH).read_text(encoding="utf-8")
    for title in ("Dataset", "Target", "Spark processing", "Slowness findings",
                  "Model results", "Limits"):
        assert f"## {title}" in text
    assert not summary.FORBIDDEN_WORDS.search(text)
    assert "SUMMARY OK" in capsys.readouterr().out


def test_evidence_paths_parse_backticks_and_escapes() -> None:
    """Check that the path column is read, with escaped underscores."""
    text = ("| Item | Evidence path |\n| --- | --- |\n"
            "| A | `results/tables/rank\\_*.csv`, `docs/a.md` |\n| B | text |\n")
    assert summary.evidence_paths(text) == [
        (3, "results/tables/rank_*.csv"), (3, "docs/a.md"), (4, "")]
    with pytest.raises(summary.SummaryError, match="Evidence path"):
        summary.evidence_paths("| Item | Other |\n| --- | --- |\n")


def test_check_stops_for_a_missing_path(root: Path, capsys) -> None:
    """Check that --check reports a missing path and an empty row, then passes."""
    summary.main(["--root", str(root)])
    rubric = root / summary.RUBRIC_PATH
    rubric.write_text(
        "| Item | Evidence path |\n| --- | --- |\n| A | `results/spark/lineage.txt` |\n"
        "| B | `results/missing.csv` |\n| C | no path |\n", encoding="utf-8")
    assert summary.main(["--root", str(root), "--check"]) == 1
    errors = capsys.readouterr().err
    assert "path not found: results/missing.csv" in errors
    assert "the row has no evidence path" in errors
    rubric.write_text(
        "| Item | Evidence path |\n| --- | --- |\n"
        "| A | `results/spark/lineage.txt`, `results/tables/rank\\_*.csv` |\n",
        encoding="utf-8")
    assert summary.main(["--root", str(root), "--check"]) == 0
    assert "SUMMARY OK" in capsys.readouterr().out


def test_check_finds_forbidden_words_in_the_summary(root: Path) -> None:
    """Check that TODO, TBD, nan, and None in the summary stop the check."""
    path = root / summary.SUMMARY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("A value of nan and None.\nTODO later\nNo problem here.\n",
                    encoding="utf-8")
    errors = summary.check_summary(root)
    assert len(errors) == 3 and "forbidden word 'nan'" in errors[0]
