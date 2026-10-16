"""Draw the figures for the slides and the report. This module does not use Spark."""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402

from nyc311.config import read_properties  # noqa: E402

DEFAULT_RESULTS = "results"
DEFAULT_PROCESSED = "data/processed"
FIGURE_SIZE = (10, 5.6)
DPI = 200
FONT_SIZE = 11
TITLE_SIZE = 13
TITLE_WIDTH = 82

BLUE, ORANGE, GREEN = "#0072B2", "#E69F00", "#009E73"
VERMILLION, BLACK = "#D55E00", "#000000"
GRAY = "#8C8C8C"

RANKING_XLABEL = "Share of requests slower than N days (%), with 95% interval"
SHORT_HOURS = 16
LONG_HOURS = 1024
TICK_HOURS = (6, 24, 72, 168, 720, 4380)
INSIDE_LABEL_SHARE = 0.1
TOP_TYPES = 15
HEATMAP_TYPES = 12
BOROUGHS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "STATEN ISLAND"]
WEEKDAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
]
MODEL_LABELS = {
    "majority": "Majority class",
    "history_rule": "History rule",
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "random_forest_no_history": "Random Forest\n(no history)",
}


def pretty(name: str) -> str:
    """Return a name in title case. Text in parentheses stays in capitals."""
    return re.sub(r"\(([^)]*)\)", lambda m: f"({m.group(1).upper()})", name.title())


def percent(value: float) -> str:
    """Format a share. Values under 10 percent keep one decimal."""
    return f"{value:.1%}" if value < 0.1 else f"{value:.0%}"


def read_table(tables: Path, name: str) -> pd.DataFrame:
    """Read a result table. The columns hour and month stay text."""
    return pd.read_csv(tables / name, dtype={"hour": str, "month": str})


def overall_slow_share(months: pd.DataFrame) -> float:
    """Return the slow share of all requests: slow requests divided by requests."""
    return float((months["n"] * months["slow_share"]).sum() / months["n"].sum())


def duration_label(hours: float) -> str:
    """Return a short label for a duration in hours."""
    return f"{hours:g} h" if hours < 24 else f"{hours / 24:.0f} d"


def apply_style() -> None:
    """Set the font sizes of the figure rules and hide the top and right lines."""
    plt.rcParams.update({
        "font.size": FONT_SIZE, "axes.labelsize": FONT_SIZE,
        "xtick.labelsize": FONT_SIZE, "ytick.labelsize": FONT_SIZE,
        "legend.fontsize": FONT_SIZE,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def new_figure(rows: int = 1, columns: int = 1, **kwargs):
    """Create a figure of 10 by 5.6 inches with the font sizes of the rules."""
    apply_style()
    return plt.subplots(rows, columns, figsize=FIGURE_SIZE, **kwargs)


def save_figure(fig, title: str, source: str, n_days: int, path: Path) -> Path:
    """Add the title and the footer, then save the figure as a PNG file."""
    lines = [
        f"Source: NYC 311 requests created in 2025 ({source}).",
        f"Slow means more than {n_days} days to close.",
    ]
    fig.suptitle(
        textwrap.fill(title, TITLE_WIDTH), x=0.01, ha="left", fontsize=TITLE_SIZE,
        fontweight="bold",
    )
    fig.text(0.01, 0.012, "\n".join(lines), ha="left", fontsize=FONT_SIZE,
             color="#444444")
    fig.tight_layout(rect=(0, 0.03 * len(lines) + 0.015, 1, 0.9))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, format="png")
    plt.close(fig)
    return path


def pct_axis(axis, which: str = "x") -> None:
    """Show an axis as percent, starting at zero."""
    formatter = PercentFormatter(1.0, decimals=0)
    if which == "x":
        axis.xaxis.set_major_formatter(formatter)
        axis.set_xlim(left=0)
    else:
        axis.yaxis.set_major_formatter(formatter)
        axis.set_ylim(bottom=0)


# Figure 1: how long requests take to close.

def histogram_shares(hist: pd.DataFrame) -> tuple[float, float]:
    """Return the share closed within SHORT_HOURS and the share above LONG_HOURS."""
    total = hist["rows"].sum()
    short = hist.loc[hist["upper_hours"] <= SHORT_HOURS, "rows"].sum() / total
    long = hist.loc[hist["lower_hours"] >= LONG_HOURS, "rows"].sum() / total
    return float(short), float(long)


def title_histogram(hist: pd.DataFrame) -> str:
    """Build the title of figure 1 from the histogram table."""
    short, long = histogram_shares(hist)
    return (
        f"{short:.0%} of requests close within {SHORT_HOURS} hours, "
        f"but {long:.0%} take longer than {LONG_HOURS / 24:.0f} days"
    )


def plot_duration_histogram(hist: pd.DataFrame, n_days: int, path: Path) -> Path:
    """Draw figure 1: bars of the time to close with a line at N days."""
    fig, axis = new_figure()
    total = hist["rows"].sum()
    left = hist["lower_hours"].map(lambda h: math.log2(h) if h > 0 else -1.0)
    n_position = math.log2(n_days * 24)
    axis.bar(left, hist["rows"] / total, width=1.0, align="edge", color=BLUE,
             edgecolor="white")
    axis.axvline(n_position, color=VERMILLION, linestyle="--", linewidth=2)
    axis.text(n_position + 0.15, axis.get_ylim()[1] * 0.95, f"N = {n_days} days",
              color=VERMILLION, fontweight="bold", va="top")
    axis.set_xticks([-0.5] + [math.log2(hours) for hours in TICK_HOURS])
    axis.set_xticklabels(["< 1 h"] + [duration_label(hours) for hours in TICK_HOURS])
    axis.set_xlabel("Time from filing to closing (hours or days, log scale)")
    axis.set_ylabel("Share of requests (%)")
    pct_axis(axis, "y")
    title = title_histogram(hist)
    return save_figure(fig, title, "profile_duration_hist.csv", n_days, path)


# Figure 2: the problem types with the highest slow share.

def slowest_types(types: pd.DataFrame) -> pd.DataFrame:
    """Return the TOP_TYPES rows with the highest slow share."""
    return types.sort_values(["slow_share", "n"], ascending=False).head(TOP_TYPES)


def title_slowest_types(types: pd.DataFrame, overall: float, n_days: int) -> str:
    """Build the title of figure 2."""
    top = slowest_types(types)
    return (
        f"The {len(top)} slowest problem types take longer than {n_days} days in "
        f"at least {top['slow_share'].min():.0%} of requests. "
        f"For all requests it is {overall:.0%}"
    )


def draw_ranking(axis, table: pd.DataFrame, labels: list[str], overall: float) -> None:
    """Draw horizontal bars with Wilson intervals, the highest slow share on top.

    Bars above the share of all requests are blue. The other bars are gray.
    """
    positions = list(range(len(table)))
    errors = [
        (table["slow_share"] - table["wilson_low"]).clip(lower=0),
        (table["wilson_high"] - table["slow_share"]).clip(lower=0),
    ]
    colors = [BLUE if share >= overall else GRAY for share in table["slow_share"]]
    axis.barh(positions, table["slow_share"], xerr=errors, color=colors,
              error_kw={"ecolor": BLACK, "capsize": 3, "linewidth": 1.2})
    axis.set_yticks(positions)
    axis.set_yticklabels(labels)
    axis.set_ylim(len(table) - 0.4, -1.2)
    axis.axvline(overall, color=VERMILLION, linestyle="--", linewidth=1.5)
    axis.text(overall + 0.008, -0.85, f"All requests {overall:.0%}", color=VERMILLION,
              va="center")
    for position, row in zip(positions, table.itertuples()):
        label = percent(row.slow_share)
        axis.text(row.wilson_high + 0.012, position, label, va="center",
                  bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
    pct_axis(axis, "x")
    axis.set_xlim(right=1.12)


def plot_slowest_types(
    types: pd.DataFrame, overall: float, n_days: int, path: Path
) -> Path:
    """Draw figure 2: the problem types with the highest slow share."""
    fig, axis = new_figure()
    top = slowest_types(types)
    names = zip(top["complaint_type"], top["n"])
    labels = [f"{pretty(name)} ({count:,})" for name, count in names]
    draw_ranking(axis, top, labels, overall)
    axis.set_xlabel(RANKING_XLABEL)
    axis.set_ylabel("Problem type (number of requests)")
    title = title_slowest_types(types, overall, n_days)
    return save_figure(fig, title, "rank_complaint_type.csv", n_days, path)


# Figure 3: the slow share of each agency.

def title_agency(agencies: pd.DataFrame) -> str:
    """Build the title of figure 3."""
    ordered = agencies.sort_values("slow_share", ascending=False)
    first, last = ordered.iloc[0], ordered.iloc[-1]
    return (
        f"Slow share runs from {percent(last['slow_share'])} for {last['agency']} to "
        f"{percent(first['slow_share'])} for {first['agency']} "
        f"across {len(ordered)} agencies"
    )


def plot_agency_slowness(
    agencies: pd.DataFrame, overall: float, n_days: int, path: Path
) -> Path:
    """Draw figure 3: sorted bars of the slow share of each agency."""
    fig, axis = new_figure()
    ordered = agencies.sort_values("slow_share", ascending=False)
    labels = [
        f"{name} ({count:,})" for name, count in zip(ordered["agency"], ordered["n"])
    ]
    draw_ranking(axis, ordered, labels, overall)
    axis.set_xlabel(RANKING_XLABEL)
    axis.set_ylabel("Agency (number of requests)")
    return save_figure(fig, title_agency(agencies), "rank_agency.csv", n_days, path)


# Figure 4: slow share of the most frequent types in each borough.

def frequent_types(type_borough: pd.DataFrame) -> list[str]:
    """Return the HEATMAP_TYPES problem types with the most requests."""
    totals = type_borough.groupby("complaint_type")["n"].sum()
    return list(totals.sort_values(ascending=False).head(HEATMAP_TYPES).index)


def heatmap_matrix(type_borough: pd.DataFrame) -> pd.DataFrame:
    """Return the slow share by frequent type (rows) and borough (columns)."""
    order = frequent_types(type_borough)
    chosen = type_borough[type_borough["complaint_type"].isin(order)]
    matrix = chosen.pivot(
        index="complaint_type", columns="borough", values="slow_share"
    )
    return matrix.reindex(index=order, columns=BOROUGHS)


def title_heatmap(matrix: pd.DataFrame) -> str:
    """Build the title of figure 4 from the type with the widest borough gap."""
    spread = (matrix.max(axis=1) - matrix.min(axis=1)).dropna()
    name = spread.idxmax()
    row = matrix.loc[name].dropna()
    return (
        f"The same problem type is slower in some boroughs: {name.title()} runs from "
        f"{percent(row.min())} in {row.idxmin().title()} to {percent(row.max())} "
        f"in {row.idxmax().title()}"
    )


def plot_type_borough_heatmap(
    type_borough: pd.DataFrame, n_days: int, path: Path
) -> Path:
    """Draw figure 4: a heatmap of the slow share by problem type and borough."""
    fig, axis = new_figure()
    matrix = heatmap_matrix(type_borough)
    image = axis.imshow(matrix.to_numpy(dtype=float), cmap="Blues", vmin=0, vmax=1,
                        aspect="auto")
    axis.set_xticks(range(len(BOROUGHS)))
    axis.set_xticklabels([name.title() for name in BOROUGHS])
    axis.set_yticks(range(len(matrix)))
    axis.set_yticklabels([name.title() for name in matrix.index])
    for row_index, name in enumerate(matrix.index):
        for column_index, borough in enumerate(BOROUGHS):
            value = matrix.loc[name, borough]
            if pd.isna(value):
                axis.text(column_index, row_index, "n < 500", ha="center", va="center",
                          color=GRAY)
            else:
                color = "white" if value > 0.55 else BLACK
                axis.text(column_index, row_index, percent(value), ha="center",
                          va="center", color=color)
    axis.spines[:].set_visible(False)
    axis.set_xlabel("Borough of the request")
    axis.set_ylabel("Problem type (12 with the most requests)")
    colorbar = fig.colorbar(image, ax=axis, format=PercentFormatter(1.0, decimals=0))
    colorbar.set_label("Share of requests that take longer than N days (%)")
    title = title_heatmap(matrix)
    return save_figure(fig, title, "rank_type_borough.csv", n_days, path)


# Figure 5: slow share by hour, weekday, and month of filing.

def title_time_patterns(hours: pd.DataFrame, days: pd.DataFrame) -> str:
    """Build the title of figure 5."""
    best = days.loc[days["slow_share"].idxmin()]
    worst = days.loc[days["slow_share"].idxmax()]
    peak = hours.loc[hours["slow_share"].idxmax()]
    worst_day = WEEKDAYS[int(worst["day_of_week"]) - 1]
    best_day = WEEKDAYS[int(best["day_of_week"]) - 1]
    return (
        f"Slow share by filing time: highest on {worst_day} "
        f"({worst['slow_share']:.0%}), lowest on {best_day} "
        f"({best['slow_share']:.0%}), and highest at {int(peak['hour'])}:00 "
        f"({peak['slow_share']:.0%})"
    )


def draw_pattern(axis, labels: list[str], values: pd.Series, overall: float) -> None:
    """Draw one panel of bars. The tallest bar is blue. The others are gray."""
    positions = list(range(len(values)))
    colors = [BLUE if value == values.max() else GRAY for value in values]
    axis.bar(positions, values, color=colors)
    axis.axhline(overall, color=VERMILLION, linestyle="--", linewidth=1.5)
    axis.set_xticks(positions)
    axis.set_xticklabels(labels)
    pct_axis(axis, "y")


def plot_time_patterns(
    hours: pd.DataFrame, days: pd.DataFrame, months: pd.DataFrame, n_days: int,
    path: Path,
) -> Path:
    """Draw figure 5: three panels for the hour, the weekday, and the month."""
    apply_style()
    fig = plt.figure(figsize=FIGURE_SIZE)
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1])
    top = fig.add_subplot(grid[0, :])
    left = fig.add_subplot(grid[1, 0], sharey=top)
    right = fig.add_subplot(grid[1, 1], sharey=top)
    overall = overall_slow_share(months)
    hour_labels = [str(int(h)) if int(h) % 3 == 0 else "" for h in hours["hour"]]
    draw_pattern(top, hour_labels, hours["slow_share"], overall)
    draw_pattern(left, [name[:3] for name in WEEKDAYS], days["slow_share"], overall)
    month_labels = [str(int(m)) for m in months["month"]]
    draw_pattern(right, month_labels, months["slow_share"], overall)
    top.set_xlabel("Hour of day filed (0 to 23)")
    left.set_xlabel("Weekday filed")
    right.set_xlabel("Month filed (1 = January)")
    for axis in (top, left):
        axis.set_ylabel("Slow share (%)")
    top.text(-0.4, overall + 0.008, f"All requests {overall:.0%}", color=VERMILLION,
             ha="left", va="bottom")
    source = "pattern_hour.csv, pattern_dow.csv, pattern_month.csv"
    return save_figure(fig, title_time_patterns(hours, days), source, n_days, path)


# Figure 6: precision, recall, and F1 of the five models.

def title_model_comparison(models: pd.DataFrame) -> str:
    """Build the title of figure 6 from the F1 of the models."""
    f1 = models.set_index("model")["f1"]
    best = f1.idxmax()
    name = MODEL_LABELS[best].replace("\n", " ")
    return (
        f"{name} has the highest F1 ({f1[best]:.3f}). The Random Forest scores "
        f"{f1['random_forest']:.3f} and the history rule {f1['history_rule']:.3f}"
    )


def plot_model_comparison(models: pd.DataFrame, n_days: int, path: Path) -> Path:
    """Draw figure 6: grouped bars of recall, precision, and F1 for each model."""
    fig, axis = new_figure()
    width = 0.26
    series = (("recall", "Recall", ORANGE), ("precision", "Precision", GREEN),
              ("f1", "F1", BLUE))
    positions = list(range(len(models)))
    for offset, (column, label, color) in zip((-width, 0, width), series):
        bars = axis.bar([x + offset for x in positions], models[column], width,
                        label=label, color=color)
        for bar, value in zip(bars, models[column]):
            axis.text(bar.get_x() + bar.get_width() / 2, value + 0.012, f"{value:.2f}",
                      ha="center", va="bottom")
    axis.set_xticks(positions)
    axis.set_xticklabels([MODEL_LABELS[name] for name in models["model"]])
    axis.set_ylim(0, 1.12)
    axis.set_ylabel("Score of the slow class (0 to 1)")
    axis.set_xlabel("Model (test window, decision threshold 0.5)")
    axis.legend(ncol=3, frameon=False, loc="upper left")
    title = title_model_comparison(models)
    return save_figure(fig, title, "metrics_by_model.csv", n_days, path)


# Figure 7: precision against recall.

def precision_at_recall(curve: pd.DataFrame, target: float) -> float:
    """Return the precision at the highest threshold that keeps the target recall."""
    kept = curve[curve["recall"] >= target]
    return float(kept.sort_values("threshold").iloc[-1]["precision"])


def title_pr_curves(curves: pd.DataFrame, rule: dict) -> str:
    """Build the title of figure 7."""
    recall = rule["recall"]
    by_model = {name: rows for name, rows in curves.groupby("model")}
    forest = precision_at_recall(by_model["random_forest"], recall)
    logistic = precision_at_recall(by_model["logistic_regression"], recall)
    return (
        f"At the recall of the history rule ({recall:.0%}), precision is "
        f"{rule['precision']:.0%} for the rule, {logistic:.0%} for Logistic "
        f"Regression, and {forest:.0%} for the Random Forest"
    )


def plot_pr_curves(
    curves: pd.DataFrame, metrics: dict, n_days: int, path: Path
) -> Path:
    """Draw figure 7: precision and recall for both models, with the baselines."""
    fig, axis = new_figure()
    styles = {"random_forest": ("Random Forest", BLUE),
              "logistic_regression": ("Logistic Regression", ORANGE)}
    for name, (label, color) in styles.items():
        rows = curves[curves["model"] == name].sort_values("threshold")
        rows = rows[rows["recall"] > 0]
        axis.plot(rows["recall"], rows["precision"], color=color, linewidth=2.5,
                  label=label)
        point = metrics[name]
        axis.scatter([point["recall"]], [point["precision"]], color=color, s=70,
                     edgecolor=BLACK, zorder=3)
    rule = metrics["history_rule"]
    axis.scatter([rule["recall"]], [rule["precision"]], marker="s", s=90, color=BLACK,
                 zorder=3, label="History rule")
    axis.scatter([0], [0], marker="x", s=90, color=GRAY, zorder=3,
                 label="Majority class (finds no slow request)")
    share = metrics["test_slow_share"]
    axis.axhline(share, color=GRAY, linestyle=":", linewidth=1.5)
    axis.text(0.98, share + 0.012, "Share of slow requests in the test window",
              color="#444444", ha="right")
    axis.text(0.02, 0.30, "Circles mark the threshold 0.5", color="#444444")
    axis.set_xlim(0, 1.0)
    axis.set_ylim(0, 1.05)
    axis.set_xlabel("Recall of the slow class (share of slow requests found)")
    axis.set_ylabel("Precision of the slow class (share of alerts that are right)")
    axis.legend(frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0))
    title = title_pr_curves(curves, rule)
    return save_figure(fig, title, "pr_curve.csv, metrics.json", n_days, path)


# Figure 8: slow requests in each risk decile.

def title_deciles(deciles: pd.DataFrame) -> str:
    """Build the title of figure 8."""
    top = 2
    share = deciles.sort_values("decile").iloc[top - 1]["cumulative_share"]
    percent_of_requests = top * 100 // len(deciles)
    return (
        f"The riskiest {percent_of_requests}% of requests hold {share:.0%} "
        "of all slow requests"
    )


def plot_decile_capture(deciles: pd.DataFrame, n_days: int, path: Path) -> Path:
    """Draw figure 8: bars of the slow share in each decile and a cumulative line."""
    fig, axis = new_figure()
    table = deciles.sort_values("decile")
    axis.bar(table["decile"], table["share_of_all_slow"], color=BLUE,
             label="Share of all slow requests in the decile")
    axis.plot(table["decile"], table["cumulative_share"], color=VERMILLION, marker="o",
              linewidth=2.5, label="Cumulative share")
    for decile, value in zip(table["decile"], table["share_of_all_slow"]):
        if value >= INSIDE_LABEL_SHARE:
            axis.text(decile, value - 0.02, percent(value), ha="center", va="top",
                      color="white", fontweight="bold")
        else:
            axis.text(decile, value + 0.012, percent(value), ha="center", va="bottom")
    for decile, value in zip(table["decile"][1:3], table["cumulative_share"][1:3]):
        axis.text(decile + 0.12, value - 0.045, f"{value:.0%} cumulative", ha="left",
                  va="top", color=VERMILLION)
    axis.set_xticks(list(table["decile"]))
    axis.set_xlabel("Risk decile of the Random Forest (1 = riskiest 10% of requests)")
    axis.set_ylabel("Share of all slow requests (%)")
    pct_axis(axis, "y")
    axis.set_ylim(top=1.08)
    axis.legend(frameon=False, loc="center right")
    title = title_deciles(table)
    return save_figure(fig, title, "decile_capture_rf.csv", n_days, path)


# Figure 9: the feature groups of the Random Forest.

GROUP_LABELS = {
    "h1": "History: agency, type, descriptor (h1)",
    "h2": "History: type, borough (h2)",
    "h3": "History: ZIP code (h3)",
    "agency": "Agency",
    "complaint_type": "Problem type",
    "descriptor_g": "Problem detail",
    "location_type_g": "Location type",
    "borough": "Borough",
    "channel": "Filing channel",
    "hour": "Hour of day",
    "dow": "Weekday",
    "is_weekend": "Weekend flag",
}
HISTORY_GROUPS = ("h1", "h2", "h3")


def title_importance(groups: pd.DataFrame) -> str:
    """Build the title of figure 9."""
    ordered = groups.sort_values("importance", ascending=False)
    history = groups.loc[groups["group"].isin(HISTORY_GROUPS), "importance"].sum()
    top = ordered.iloc[0]
    return (
        f"History features hold {history:.0%} of the Random Forest importance. "
        f"The group {top['group']} alone holds {top['importance']:.0%}"
    )


def plot_feature_importance(groups: pd.DataFrame, n_days: int, path: Path) -> Path:
    """Draw figure 9: horizontal bars of the importance of each feature group."""
    fig, axis = new_figure()
    ordered = groups.sort_values("importance", ascending=False).reset_index(drop=True)
    colors = [BLUE if name in HISTORY_GROUPS else GRAY for name in ordered["group"]]
    positions = list(range(len(ordered)))
    axis.barh(positions, ordered["importance"], color=colors)
    axis.set_yticks(positions)
    axis.set_yticklabels([GROUP_LABELS.get(name, name) for name in ordered["group"]])
    axis.invert_yaxis()
    for position, value in zip(positions, ordered["importance"]):
        axis.text(value + 0.006, position, percent(value), va="center")
    pct_axis(axis, "x")
    axis.set_xlim(right=ordered["importance"].max() * 1.15)
    axis.set_xlabel("Share of Random Forest importance (%), blue = history features")
    axis.set_ylabel("Feature group")
    title = title_importance(groups)
    return save_figure(fig, title, "feature_importance_groups_rf.csv", n_days, path)


# Figure 10: right and wrong predictions of the Random Forest.

def confusion_cells(matrix: pd.DataFrame) -> dict[str, int]:
    """Return the four counts from the confusion matrix table."""
    rows = matrix.set_index("actual")
    return {
        "tn": int(rows.loc["not_slow", "predicted_not_slow"]),
        "fp": int(rows.loc["not_slow", "predicted_slow"]),
        "fn": int(rows.loc["slow", "predicted_not_slow"]),
        "tp": int(rows.loc["slow", "predicted_slow"]),
    }


def title_confusion(matrix: pd.DataFrame) -> str:
    """Build the title of figure 10."""
    cells = confusion_cells(matrix)
    recall = cells["tp"] / (cells["tp"] + cells["fn"])
    precision = cells["tp"] / (cells["tp"] + cells["fp"])
    return (
        f"The Random Forest finds {recall:.0%} of slow requests. "
        f"{precision:.0%} of its slow alerts are right"
    )


def plot_confusion_matrix(matrix: pd.DataFrame, n_days: int, path: Path) -> Path:
    """Draw figure 10: an annotated 2 by 2 grid of counts and shares."""
    fig, axis = new_figure()
    cells = confusion_cells(matrix)
    total = sum(cells.values())
    layout = {(0, 0): ("tn", "Right: not slow"), (0, 1): ("fp", "Wrong: false alarm"),
              (1, 0): ("fn", "Wrong: missed slow"), (1, 1): ("tp", "Right: slow found")}
    for (row, column), (key, label) in layout.items():
        share = cells[key] / total
        color = BLUE if row == column else VERMILLION
        axis.add_patch(plt.Rectangle((column, 1 - row), 1, 1, facecolor=color,
                                     alpha=0.15 + 0.85 * share, edgecolor="white",
                                     linewidth=3))
        text_color = "white" if share > 0.35 else BLACK
        text = f"{cells[key]:,}\n{share:.1%} of requests\n{label}"
        axis.text(column + 0.5, 1.5 - row, text, ha="center", va="center",
                  color=text_color, fontsize=FONT_SIZE + 2)
    axis.set_xlim(0, 2)
    axis.set_ylim(0, 2)
    axis.set_xticks([0.5, 1.5])
    axis.set_xticklabels(["Predicted not slow", "Predicted slow"])
    axis.set_yticks([0.5, 1.5])
    axis.set_yticklabels(["Actually slow", "Actually not slow"])
    axis.set_xlabel("Prediction of the Random Forest (threshold 0.5)")
    axis.set_ylabel("What happened")
    axis.spines[:].set_visible(False)
    axis.tick_params(length=0)
    title = title_confusion(matrix)
    return save_figure(fig, title, "confusion_matrix_rf.csv", n_days, path)


def read_threshold(processed: Path) -> int:
    """Read N from run_params.properties."""
    values = read_properties(processed / "run_params.properties")
    return int(values["slow_threshold_days"])


def draw_descriptive(tables: Path, figures: Path, n_days: int) -> list[Path]:
    """Draw figures 1 to 5 from the profile, ranking, and pattern tables."""
    months = read_table(tables, "pattern_month.csv")
    overall = overall_slow_share(months)
    return [
        plot_duration_histogram(read_table(tables, "profile_duration_hist.csv"), n_days,
                                figures / "fig01_duration_histogram.png"),
        plot_slowest_types(read_table(tables, "rank_complaint_type.csv"), overall,
                           n_days, figures / "fig02_slowest_types.png"),
        plot_agency_slowness(read_table(tables, "rank_agency.csv"), overall, n_days,
                             figures / "fig03_agency_slowness.png"),
        plot_type_borough_heatmap(read_table(tables, "rank_type_borough.csv"), n_days,
                                  figures / "fig04_type_borough_heatmap.png"),
        plot_time_patterns(read_table(tables, "pattern_hour.csv"),
                           read_table(tables, "pattern_dow.csv"), months, n_days,
                           figures / "fig05_time_patterns.png"),
    ]


def draw_evaluation(results: Path, figures: Path, n_days: int) -> list[Path]:
    """Draw figures 6 to 10 from the model tables and metrics.json."""
    tables = results / "tables"
    metrics = json.loads((results / "metrics.json").read_text(encoding="utf-8"))
    return [
        plot_model_comparison(read_table(tables, "metrics_by_model.csv"), n_days,
                              figures / "fig06_model_comparison.png"),
        plot_pr_curves(read_table(tables, "pr_curve.csv"), metrics, n_days,
                       figures / "fig07_pr_curves.png"),
        plot_decile_capture(read_table(tables, "decile_capture_rf.csv"), n_days,
                            figures / "fig08_decile_capture.png"),
        plot_feature_importance(read_table(tables, "feature_importance_groups_rf.csv"),
                                n_days, figures / "fig09_feature_importance.png"),
        plot_confusion_matrix(read_table(tables, "confusion_matrix_rf.csv"), n_days,
                              figures / "fig10_confusion_matrix.png"),
    ]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--processed", default=DEFAULT_PROCESSED)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Draw every figure and write the PNG files to results/figures."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    results = Path(args.results)
    n_days = read_threshold(Path(args.processed))
    figures = results / "figures"
    written = draw_descriptive(results / "tables", figures, n_days)
    written += draw_evaluation(results, figures, n_days)
    for path in written:
        print(f"wrote {path}")
    print("PLOTS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
