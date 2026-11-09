"""Checks of the trimmed AMFI fixtures and of the live AMFI file headers."""

import datetime as dt
import re
from pathlib import Path
from typing import Final

import pytest

from indianfinance import _http
from indianfinance._dates import parse_amfi_date

FIXTURES: Final[Path] = Path(__file__).parent / "fixtures" / "amfi"
NAVALL: Final[Path] = FIXTURES / "navall_20261106.txt"
HISTORY: Final[Path] = FIXTURES / "nav_history_20261105_20261106.txt"
HISTORY_SUNDAY: Final[Path] = FIXTURES / "nav_history_20261108.txt"
ENCODING: Final[str] = "utf-8"
NAVALL_URL: Final[str] = "https://portal.amfiindia.com/spages/NAVAll.txt"
HISTORY_URL: Final[str] = (
    "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
)
NAVALL_HEADER: Final[str] = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;"
    "Plan;Option;Net Asset Value;Date"
)
HISTORY_HEADER: Final[str] = (
    "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;"
    "ISIN Div Reinvestment;Net Asset Value;Date"
)
D5, D6, D8 = dt.date(2026, 11, 5), dt.date(2026, 11, 6), dt.date(2026, 11, 8)


def _lines(path: Path) -> list[str]:
    return path.read_bytes().decode(ENCODING).splitlines()


def _rows(lines: list[str]) -> list[list[str]]:
    return [line.split(";") for line in lines[1:] if ";" in line]


@pytest.mark.parametrize(
    ("path", "cap"), [(NAVALL, 20_480), (HISTORY, 10_240), (HISTORY_SUNDAY, 10_240)]
)
def test_amfi_fixture_is_small_enough(path: Path, cap: int) -> None:
    # AC2
    assert 0 < path.stat().st_size <= cap


def test_navall_fixture_header_matches_documented() -> None:
    # AC3
    assert _lines(NAVALL)[0] == NAVALL_HEADER


def test_navall_fixture_rows_have_eight_fields_and_amfi_dates() -> None:
    # AC3
    rows = _rows(_lines(NAVALL))
    assert len(rows) >= 20
    for row in rows:
        assert len(row) == 8, row
        assert re.fullmatch(r"[0-9]+", row[0]), row
        assert re.fullmatch(r"[0-9]+(\.[0-9]+)?", row[6]), row
        parse_amfi_date(row[7])


def test_navall_fixture_contains_documented_quirks() -> None:
    # AC4
    lines = _lines(NAVALL)
    rows = _rows(lines)
    assert any("-" in (r[1], r[2]) for r in rows)
    assert any(r[4] == "" and r[5] == "" for r in rows)
    assert len({r[7] for r in rows}) >= 3
    assert any(not line.isascii() and ";" not in line for line in lines)
    assert any(r[6] in ("0", "0.0000") for r in rows)
    assert any(line.startswith("Close Ended Schemes(") for line in lines)
    assert any(line.startswith("Interval Fund Schemes(") for line in lines)
    assert any(r[2] == "Redeemed" for r in rows)
    assert any(r[2] != r[2].strip() for r in rows)
    assert any(r[2] == "HDFCNIVODG" for r in rows)


@pytest.mark.parametrize(
    ("path", "dates"), [(HISTORY, {D5, D6}), (HISTORY_SUNDAY, {D8})]
)
def test_nav_history_fixture_matches_documented_format(
    path: Path, dates: set[dt.date]
) -> None:
    # AC5
    lines = _lines(path)
    rows = _rows(lines)
    assert lines[0] == HISTORY_HEADER
    assert len(rows) >= 10
    assert all(len(row) == 8 for row in rows)
    assert {parse_amfi_date(row[7]) for row in rows} == dates
    if path == HISTORY:
        pairs = {(r[0], parse_amfi_date(r[7])) for r in rows}
        assert any((c, D5) in pairs and (c, D6) in pairs for c, _ in pairs)


def _download(url: str, params: dict[str, str] | None = None) -> list[str]:
    with _http.open_client() as client:
        content = _http.get(client, url, params=params).content
    return content.decode(ENCODING).splitlines()


@pytest.mark.live
def test_navall_live_header_and_rows_match_documented() -> None:
    # AC6
    lines = _download(NAVALL_URL)
    rows = _rows(lines)
    assert lines[0] == NAVALL_HEADER
    assert len(rows) > 1_000
    assert all(len(row) == 8 for row in rows)


@pytest.mark.live
def test_nav_history_live_header_matches_documented() -> None:
    # AC7
    lines = _download(HISTORY_URL, {"frmdt": "06-Nov-2026", "todt": "06-Nov-2026"})
    assert lines[0] == HISTORY_HEADER
    assert {parse_amfi_date(row[7]) for row in _rows(lines)} == {D6}
