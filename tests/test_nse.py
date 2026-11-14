"""Tests for the private NSE bhavcopy parser (one live test)."""

import datetime as dt
import io
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from indianfinance import _http, nse
from indianfinance.exceptions import SourceFormatError
from indianfinance.models import EodPrice
from indianfinance.nse import _parse_bhavcopy, _read_bhavcopy

BHAVCOPY: Final[Path] = Path(__file__).parent / "fixtures/nse/bhavcopy_20261106.csv.zip"
D6: Final[dt.date] = dt.date(2026, 11, 6)
HEADER_LINE: Final[str] = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,"
    "FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,"
    "LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,"
    "TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,"
    "Rsvd3,Rsvd4"
)
HEADER: Final[list[str]] = HEADER_LINE.split(",")
INFY_ROW: Final[str] = (
    "2026-11-06,2026-11-06,CM,NSE,STK,1594,INE009A01021,INFY,EQ,,,,,INFOSYS LIMITED,"
    "1182.80,1198.80,1163.00,1181.40,1181.40,1167.40,,1181.38,,,15301109,18005126629.60,"
    "229030,F1,1,,,,,"
)
INFY: Final = EodPrice(
    symbol="INFY",
    series="EQ",
    isin="INE009A01021",
    date=D6,
    open=Decimal("1182.80"),
    high=Decimal("1198.80"),
    low=Decimal("1163.00"),
    close=Decimal("1181.40"),
    prev_close=Decimal("1167.40"),
    volume=15301109,
    traded_value=Decimal("18005126629.60"),
)
URL: Final[str] = (
    "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261106_F_0000.csv.zip"
)


def _csv(*rows: str, header: str = HEADER_LINE) -> str:
    return "\n".join([header, *rows]) + "\n"


def _row(**changes: str) -> str:
    fields = INFY_ROW.split(",")
    for name, value in changes.items():
        fields[HEADER.index(name)] = value
    return ",".join(fields)


def _zip(*members: tuple[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in members:
            zf.writestr(name, content)
    return buf.getvalue()


def _fixture_text() -> str:
    with zipfile.ZipFile(BHAVCOPY) as zf:
        return zf.read(zf.namelist()[0]).decode("utf-8")


def _by_symbol(rows: list[EodPrice]) -> dict[str, EodPrice]:
    return {r.symbol: r for r in rows}


BAD_TEXT: Final = [
    pytest.param("", 1, id="empty-text"),
    pytest.param(
        _csv(INFY_ROW, header=HEADER_LINE.replace("ClsPric,", "")), 1, id="no-ClsPric"
    ),
    pytest.param(_csv(), None, id="header-only"),
    pytest.param(_csv(INFY_ROW.rsplit(",", 1)[0]), 2, id="33-fields"),
    pytest.param(_csv(INFY_ROW + ",x"), 2, id="35-fields"),
    pytest.param(_csv(_row(TradDt="06-11-2026")), 2, id="TradDt-format"),
    pytest.param(_csv(_row(TradDt="2026-11-05")), 2, id="TradDt-other-day"),
    pytest.param(_csv(_row(OpnPric="")), 2, id="OpnPric-empty"),
    pytest.param(_csv(_row(ClsPric="abc")), 2, id="ClsPric-text"),
    pytest.param(_csv(_row(HghPric="-1")), 2, id="HghPric-negative"),
    pytest.param(_csv(_row(LwPric="NaN")), 2, id="LwPric-nan"),
    pytest.param(_csv(_row(TtlTrfVal='"1,234.50"')), 2, id="TtlTrfVal-comma"),
    pytest.param(_csv(_row(TtlTradgVol="1.5")), 2, id="volume-fraction"),
    pytest.param(_csv(_row(TckrSymb="")), 2, id="symbol-empty"),
    pytest.param(_csv(_row(ISIN="")), 2, id="isin-empty"),
    pytest.param(_csv(_row(SctySrs="")), 2, id="series-empty"),
    pytest.param(_csv(_row(PrvsClsgPric="")), 2, id="prev-close-empty"),
    pytest.param(_csv(_row(TtlTradgVol="-")), 2, id="volume-dash"),
    pytest.param(_csv(_row(OpnPric="1e3")), 2, id="OpnPric-exponent"),
    pytest.param(_csv("", _row(ClsPric="abc")), 3, id="line-after-blank"),
    pytest.param(
        _csv(INFY_ROW, INFY_ROW, _row(ClsPric="abc")), 4, id="bad-row-after-good"
    ),
]
BAD_ZIP: Final = [
    pytest.param(b"", id="empty-bytes"),
    pytest.param(b"not a zip", id="not-a-zip"),
    pytest.param(_zip(), id="zero-members"),
    pytest.param(_zip(("a.csv", b"x"), ("b.csv", b"y")), id="two-members"),
    pytest.param(_zip(("a.csv", b"\xff\xfe")), id="not-utf8"),
]


def test_read_bhavcopy_returns_fixture_rows_in_file_order() -> None:
    # AC1
    rows: list[EodPrice] = _read_bhavcopy(BHAVCOPY.read_bytes(), day=D6)
    assert len(rows) == 26
    assert (rows[0].symbol, rows[0].series, rows[0].isin) == (
        "SGBJUN28",
        "GB",
        "IN0020200104",
    )
    assert rows[-1].symbol == "ZYDUSWELL"
    assert {r.date for r in rows} == {D6}
    assert all(type(r.volume) is int for r in rows)


def test_read_bhavcopy_maps_columns_exactly() -> None:
    # AC2
    rec = _by_symbol(_read_bhavcopy(BHAVCOPY.read_bytes(), day=D6))["INFY"]
    assert rec == INFY
    assert (str(rec.open), str(rec.low)) == ("1182.80", "1163.00")


def test_read_bhavcopy_close_is_official_close_not_last_price() -> None:
    # AC3
    by = _by_symbol(_read_bhavcopy(BHAVCOPY.read_bytes(), day=D6))
    nifty = by["NIFTYBEES"]
    assert (nifty.close, nifty.isin, nifty.series) == (
        Decimal("284.22"),
        "INF204KB14I2",
        "EQ",
    )
    assert nifty.value == nifty.close
    assert by["ARE&M"].close == Decimal("728.25")


def test_read_bhavcopy_keeps_every_series_and_symbol() -> None:
    # AC4
    rows = _read_bhavcopy(BHAVCOPY.read_bytes(), day=D6)
    assert len({r.series for r in rows}) == 16
    assert {"EQ", "GB", "SM", "BE", "TB"} <= {r.series for r in rows}
    assert {"ARE&M", "BAJAJ-AUTO", "RELIANCE", "GOLDBEES"} <= {r.symbol for r in rows}


def test_parse_bhavcopy_finds_columns_by_name() -> None:
    # AC5
    cols = [*HEADER, "NewCol"][::-1]
    values = [*INFY_ROW.split(","), "x"][::-1]
    text = ",".join(cols) + "\n" + ",".join(values) + "\n"
    assert _parse_bhavcopy(text, day=D6) == [INFY]


@pytest.mark.parametrize(("text", "line"), BAD_TEXT)
def test_parse_bhavcopy_rejects_bad_text_with_line(text: str, line: int | None) -> None:
    # AC6
    with pytest.raises(SourceFormatError) as exc:
        _parse_bhavcopy(text, day=D6)
    assert exc.value.line == line


@pytest.mark.parametrize("data", BAD_ZIP)
def test_read_bhavcopy_rejects_bad_zip(data: bytes) -> None:
    # AC7
    with pytest.raises(SourceFormatError) as exc:
        _read_bhavcopy(data, day=D6)
    assert exc.value.line is None


def test_read_bhavcopy_rejects_oversized_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AC7
    monkeypatch.setattr(nse, "_MAX_CSV_BYTES", 10)
    with pytest.raises(SourceFormatError) as exc:
        _read_bhavcopy(_zip(("a.csv", b"x" * 11)), day=D6)
    assert exc.value.line is None


@pytest.mark.parametrize(
    "text",
    [
        _csv("", INFY_ROW, "", ""),
        _csv(_row(TckrSymb=" INFY ", OpnPric=" 1182.80", TtlTradgVol="15301109 ")),
        _csv(_row(FinInstrmNm='"INFOSYS, LTD"')),
    ],
    ids=["blank-lines", "padded-fields", "quoted-comma"],
)
def test_parse_bhavcopy_tolerates_blank_lines_padding_and_quotes(text: str) -> None:
    # Edge cases: rules 2, 4
    assert _parse_bhavcopy(text, day=D6) == [INFY]


def test_parse_bhavcopy_accepts_zero_price() -> None:
    # Edge case: rule 5, 0 accepted
    rec = _parse_bhavcopy(_csv(_row(OpnPric="0", TtlTrfVal="0.00")), day=D6)[0]
    assert (rec.open, rec.traded_value) == (Decimal("0"), Decimal("0.00"))


@pytest.mark.parametrize("prefix", ["", "﻿"], ids=["crlf", "bom"])
def test_parse_bhavcopy_accepts_crlf_and_bom(prefix: str) -> None:
    # AC8
    text = prefix + _fixture_text()
    if not prefix:
        text = text.replace("\n", "\r\n")
    rows = _parse_bhavcopy(text, day=D6)
    assert len(rows) == 26
    assert _by_symbol(rows)["INFY"] == INFY
    assert rows[-1].symbol == "ZYDUSWELL"


@pytest.mark.live
def test_read_bhavcopy_live() -> None:
    # AC9
    with _http.open_client() as client:
        content = _http.get(client, URL).content
    rows = _read_bhavcopy(content, day=D6)
    assert len(rows) > 1_000
    assert {r.date for r in rows} == {D6}
    assert any((r.symbol, r.series) == ("INFY", "EQ") for r in rows)


def test_nse_has_no_public_api_yet() -> None:
    # AC10
    assert nse.__all__ == []
