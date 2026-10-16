"""Tests for the plot functions and the title builders. Tables hold fixture rows."""
from pathlib import Path

import pandas as pd
import pytest

from nyc311 import plots

MIN_PNG_BYTES = 5 * 1024
N_DAYS = 3


def assert_png(path: Path) -> None:
    """Check that the figure file exists and is larger than 5 KB."""
    assert path.exists()
    assert path.stat().st_size > MIN_PNG_BYTES
    assert path.read_bytes()[:4] == b"\x89PNG"


def histogram() -> pd.DataFrame:
    """Return a fixture duration histogram with 7 buckets."""
    rows = [(0, 0, 1, 400), (1, 1, 2, 200), (2, 2, 4, 150), (3, 4, 8, 100),
            (4, 8, 16, 80), (5, 16, 32, 50), (6, 1024, 2048, 20)]
    return pd.DataFrame(rows, columns=["bucket", "lower_hours", "upper_hours", "rows"])


def ranking(names: list[str], column: str) -> pd.DataFrame:
    """Return a fixture ranking table. The first name has the highest slow share."""
    shares = [0.95 - 0.05 * index for index in range(len(names))]
    return pd.DataFrame({
        column: names, "n": [1000 + 10 * i for i in range(len(names))],
        "mean_days": 5.0, "slow_share": shares,
        "wilson_low": [s - 0.02 for s in shares],
        "wilson_high": [min(s + 0.02, 1.0) for s in shares],
    })


def type_borough() -> pd.DataFrame:
    """Return a fixture table of 3 types in 5 boroughs, with one missing pair."""
    rows = []
    for type_index, name in enumerate(["PARKING", "HEAT", "WATER"]):
        for borough_index, borough in enumerate(plots.BOROUGHS):
            if (name, borough) == ("WATER", "BRONX"):
                continue
            rows.append((name, borough, 5000 - 1000 * type_index, 1.0,
                         0.1 * type_index + 0.02 * borough_index, 0.0, 0.0))
    columns = ["complaint_type", "borough", "n", "mean_days", "slow_share",
               "wilson_low", "wilson_high"]
    return pd.DataFrame(rows, columns=columns)


def pattern(column: str, labels: list[str]) -> pd.DataFrame:
    """Return a fixture pattern table with a rising slow share."""
    count = len(labels)
    shares = [0.1 + 0.2 * index / count for index in range(count)]
    return pd.DataFrame({column: labels, "n": 1000, "mean_days": 2.0,
                         "slow_share": shares, "wilson_low": shares,
                         "wilson_high": shares})


def models() -> pd.DataFrame:
    """Return a fixture metrics table of the five models."""
    names = list(plots.MODEL_LABELS)
    return pd.DataFrame({
        "model": names, "precision": [0.0, 0.8, 0.7, 0.7, 0.4],
        "recall": [0.0, 0.75, 0.9, 0.89, 0.99], "f1": [0.0, 0.77, 0.79, 0.78, 0.6],
    })


def curves() -> pd.DataFrame:
    """Return a fixture precision-recall table for two models."""
    rows = []
    for name in ("random_forest", "logistic_regression"):
        for threshold, precision, recall in [(0.0, 0.23, 1.0), (0.5, 0.7, 0.89),
                                             (0.9, 0.9, 0.5), (1.0, 0.0, 0.0)]:
            rows.append((name, threshold, precision, recall))
    return pd.DataFrame(rows, columns=["model", "threshold", "precision", "recall"])


def metrics() -> dict:
    """Return fixture metrics for the baselines and the two models."""
    return {
        "test_slow_share": 0.23,
        "history_rule": {"precision": 0.81, "recall": 0.75},
        "random_forest": {"precision": 0.7, "recall": 0.89},
        "logistic_regression": {"precision": 0.71, "recall": 0.89},
    }


def deciles() -> pd.DataFrame:
    """Return a fixture decile table with 10 rows."""
    shares = [0.4, 0.3, 0.15, 0.1, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0]
    cumulative = [sum(shares[: i + 1]) for i in range(10)]
    return pd.DataFrame({"decile": range(1, 11), "rows": 100, "slow_rows": 10,
                         "share_of_all_slow": shares, "cumulative_share": cumulative,
                         "lift": 1.0})


def importance() -> pd.DataFrame:
    """Return a fixture table of feature group importances."""
    return pd.DataFrame({"group": ["h1", "agency", "h2", "hour"],
                         "importance": [0.5, 0.3, 0.15, 0.05]})


def confusion() -> pd.DataFrame:
    """Return a fixture confusion matrix table."""
    return pd.DataFrame({"actual": ["not_slow", "slow"],
                         "predicted_not_slow": [700, 25], "predicted_slow": [80, 195]})


def test_every_figure_is_a_png_larger_than_5_kb(tmp_path: Path) -> None:
    """Call each plot function with a fixture table and check the file."""
    months = pattern("month", [f"{m:02d}" for m in range(1, 13)])
    overall = plots.overall_slow_share(months)
    calls = [
        plots.plot_duration_histogram(histogram(), N_DAYS, tmp_path / "1.png"),
        plots.plot_slowest_types(
            ranking([f"TYPE {i}" for i in range(20)], "complaint_type"), overall,
            N_DAYS, tmp_path / "2.png"),
        plots.plot_agency_slowness(
            ranking(["NYPD", "HPD", "DOT", "DEP"], "agency"), overall, N_DAYS,
            tmp_path / "3.png"),
        plots.plot_type_borough_heatmap(type_borough(), N_DAYS, tmp_path / "4.png"),
        plots.plot_time_patterns(
            pattern("hour", [f"{h:02d}" for h in range(24)]),
            pattern("day_of_week", [str(d) for d in range(1, 8)]), months, N_DAYS,
            tmp_path / "5.png"),
        plots.plot_model_comparison(models(), N_DAYS, tmp_path / "6.png"),
        plots.plot_pr_curves(curves(), metrics(), N_DAYS, tmp_path / "7.png"),
        plots.plot_decile_capture(deciles(), N_DAYS, tmp_path / "8.png"),
        plots.plot_feature_importance(importance(), N_DAYS, tmp_path / "9.png"),
        plots.plot_confusion_matrix(confusion(), N_DAYS, tmp_path / "10.png"),
    ]
    assert len(calls) == 10
    for path in calls:
        assert_png(path)


def test_histogram_title_uses_the_table() -> None:
    """Check that the share numbers in the title come from the table."""
    short, long = plots.histogram_shares(histogram())
    assert short == pytest.approx(930 / 1000)
    assert long == pytest.approx(20 / 1000)
    title = plots.title_histogram(histogram())
    assert "93%" in title and "2%" in title


def test_ranking_titles_use_the_table() -> None:
    """Check the titles of the type and agency figures."""
    types = ranking([f"TYPE {i}" for i in range(20)], "complaint_type")
    title = plots.title_slowest_types(types, 0.24, N_DAYS)
    assert "15 slowest" in title and "at least 25%" in title and "24%" in title
    agency = plots.title_agency(ranking(["NYPD", "HPD", "DOT"], "agency"))
    assert "HPD" not in agency and "NYPD" in agency and "DOT" in agency


def test_heatmap_title_names_the_widest_gap() -> None:
    """Check that the title names the type with the widest gap between boroughs."""
    matrix = plots.heatmap_matrix(type_borough())
    assert list(matrix.columns) == plots.BOROUGHS
    assert pd.isna(matrix.loc["WATER", "BRONX"])
    title = plots.title_heatmap(matrix)
    assert "Parking" in title or "Heat" in title or "Water" in title
    assert "Bronx" in title or "Staten Island" in title


def test_time_pattern_title_names_the_extremes() -> None:
    """Check the weekday names in the title of figure 5."""
    hours = pattern("hour", [f"{h:02d}" for h in range(24)])
    days = pattern("day_of_week", [str(d) for d in range(1, 8)])
    title = plots.title_time_patterns(hours, days)
    assert "highest on Sunday" in title and "lowest on Monday" in title
    assert "23:00" in title


def test_overall_slow_share_weights_by_requests() -> None:
    """Check the sum of slow requests divided by the sum of requests."""
    months = pd.DataFrame({"n": [100, 300], "slow_share": [0.5, 0.1]})
    assert plots.overall_slow_share(months) == pytest.approx(80 / 400)


def test_model_titles_use_the_f1_values() -> None:
    """Check that the best model and the F1 values come from the table."""
    title = plots.title_model_comparison(models())
    assert title.startswith("Logistic Regression has the highest F1 (0.790)")
    assert "0.780" in title and "0.770" in title


def test_precision_at_recall_and_pr_title() -> None:
    """Check the precision at a target recall and the title of figure 7."""
    rows = curves()
    forest = rows[rows["model"] == "random_forest"]
    assert plots.precision_at_recall(forest, 0.75) == pytest.approx(0.7)
    title = plots.title_pr_curves(rows, metrics()["history_rule"])
    assert "75%" in title and "81% for the rule" in title


def test_decile_importance_and_confusion_titles() -> None:
    """Check the titles of figures 8, 9, and 10."""
    assert plots.title_deciles(deciles()) == (
        "The riskiest 20% of requests hold 70% of all slow requests")
    assert "History features hold 65%" in plots.title_importance(importance())
    assert "The group h1 alone holds 50%" in plots.title_importance(importance())
    expected = (
        "The Random Forest finds 89% of slow requests. 71% of its slow alerts are right"
    )
    assert plots.title_confusion(confusion()) == expected


def test_pretty_keeps_acronyms_in_parentheses() -> None:
    """Check the name format of the problem types."""
    assert plots.pretty("SPECIAL TEAM (SPIT)") == "Special Team (SPIT)"
    assert plots.percent(0.0123) == "1.2%" and plots.percent(0.5) == "50%"
