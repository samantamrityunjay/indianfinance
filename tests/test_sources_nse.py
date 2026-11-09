"""Checks of the trimmed NSE bhavcopy fixture and of the live NSE file header."""

import csv
import datetime as dt
import io
import re
import zipfile
from pathlib import Path
from typing import Final

import pytest

from indianfinance import _http
from indianfinance._dates import format_compact_date, parse_iso_date

BHAVCOPY: Final[Path] = Path(__file__).parent / "fixtures/nse/bhavcopy_20261106.csv.zip"
D6: Final[dt.date] = dt.date(2026, 11, 6)
DAY: Final[str] = format_compact_date(D6)
ENCODING: Final[str] = "utf-8"
URL: Final[str] = (
    "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{day}_F_0000.csv.zip"
)
MEMBER: Final[str] = "BhavCopy_NSE_CM_0_0_0_{day}_F_0000.csv"
_COLUMNS: Final[str] = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
    "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,"
    "LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,"
    "TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,"
    "Rsvd3,Rsvd4"
)
HEADER: Final[tuple[str, ...]] = tuple(_COLUMNS.split(","))


def _read_csv(data: bytes) -> tuple[str, list[dict[str, str]]]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        (info,) = zf.infolist()
        text = zf.read(info).decode(ENCODING)
    rows = [r for r in csv.reader(io.StringIO(text)) if r]
    assert tuple(rows.pop(0)) == HEADER
    return info.filename, [dict(zip(HEADER, r, strict=True)) for r in rows]


def test_bhavcopy_fixture_is_small_enough() -> None:
    # AC2
    (size,) = (i.file_size for i in zipfile.ZipFile(BHAVCOPY).infolist())
    assert BHAVCOPY.stat().st_size <= 10_240
    assert 0 < size <= 20_480


def test_bhavcopy_fixture_names_match_documented_pattern() -> None:
    # AC3
    assert _read_csv(BHAVCOPY.read_bytes())[0] == MEMBER.format(day=DAY)
    assert URL.format(day=DAY) == (
        "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261106_F_0000.csv.zip"
    )


def test_bhavcopy_fixture_rows_match_documented_format() -> None:
    # AC4, AC5
    rows = _read_csv(BHAVCOPY.read_bytes())[1]
    assert len(rows) >= 20
    for row in rows:
        assert parse_iso_date(row["TradDt"]) == D6 == parse_iso_date(row["BizDt"])
        for col in (*HEADER[14:20], "SttlmPric", "TtlTrfVal"):  # never blank
            assert re.fullmatch(r"\d+\.\d{2}", row[col]), row
        assert re.fullmatch(r"[0-9]+", row["TtlTradgVol"]), row
        assert re.fullmatch(r"IN[A-Z0-9]{10}", row["ISIN"]), row


def test_bhavcopy_fixture_contains_documented_rows() -> None:
    # AC6
    rows = _read_csv(BHAVCOPY.read_bytes())[1]
    pairs = {(r["TckrSymb"], r["SctySrs"]) for r in rows}
    i = {r["TckrSymb"]: r["ISIN"] for r in rows}
    assert {("RELIANCE", "EQ"), ("INFY", "EQ")} <= pairs
    assert {"NIFTYBEES", "GOLDBEES", "ARE&M", "BAJAJ-AUTO"} <= i.keys()
    assert all(i[s].startswith("INF") for s in ("NIFTYBEES", "GOLDBEES"))  # ETFs
    assert all(i[s].startswith("INE") for s in ("INFY", "RELIANCE"))  # companies
    assert len({s for _, s in pairs if s != "EQ"}) >= 10


@pytest.mark.live
def test_bhavcopy_live_header_and_date_match_documented() -> None:
    # AC7
    with _http.open_client() as client:
        content = _http.get(client, URL.format(day=DAY)).content
    name, rows = _read_csv(content)
    assert name == MEMBER.format(day=DAY)
    assert len(rows) > 1_000
    assert {parse_iso_date(r["TradDt"]) for r in rows} == {D6}
