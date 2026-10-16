"""Tests for the pure functions of the download and verify scripts."""
import sys
from array import array
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import download_data  # noqa: E402
import verify_download  # noqa: E402


def test_clean_value_replaces_separators_and_strips() -> None:
    """Check that tab, return, and newline become spaces and ends are stripped."""
    assert download_data.clean_value("  a\tb\r\nc  ") == "a b  c"


def test_month_windows_cover_the_year() -> None:
    """Check that the windows are contiguous and December ends in the next year."""
    windows = download_data.month_windows(2025)
    assert len(windows) == 12
    assert windows[0][1] == "2025-01-01T00:00:00"
    assert windows[2] == ("2025-03", "2025-03-01T00:00:00", "2025-04-01T00:00:00")
    assert windows[11][2] == "2026-01-01T00:00:00"
    assert all(windows[i][2] == windows[i + 1][1] for i in range(11))


def test_parse_page_cleans_values() -> None:
    """Check that a CSV page becomes cleaned rows."""
    header = ",".join(download_data.COLUMNS)
    row = "1,2025-01-01T00:00:00.000,,Open,NYPD,\"Noise\nLoud\",a,b,QUEENS,PHONE,11101"
    rows = download_data.parse_page(f"{header}\n{row}\n".encode())
    assert rows[0][5] == "Noise Loud"
    assert len(rows[0]) == 11


def test_parse_page_rejects_other_columns() -> None:
    """Check that other column names stop the download."""
    with pytest.raises(SystemExit):
        download_data.parse_page(b"a,b\n1,2\n")


def test_check_difference_limit() -> None:
    """Check the 0.1 percent limit on the count difference."""
    download_data.check_difference("2025-01", 100000, 100050)
    with pytest.raises(SystemExit):
        download_data.check_difference("2025-01", 100000, 100500)
    download_data.check_difference("2025-01", 0, 0)


def test_count_duplicates() -> None:
    """Check that repeated keys are counted."""
    assert verify_download.count_duplicates(array("Q", [3, 1, 2, 2, 3, 3])) == 3
    assert verify_download.count_duplicates(array("Q", [1, 2, 3])) == 0
