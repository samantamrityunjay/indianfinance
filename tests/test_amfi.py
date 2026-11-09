"""Tests for indianfinance.amfi (httpx.MockTransport only; one live test)."""

import datetime as dt
import logging
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from indianfinance.amfi import _parse_isin, _split_category, latest_navs, schemes
from indianfinance.exceptions import SourceFormatError, SourceUnavailable
from indianfinance.models import NavRecord

FIXTURE = Path(__file__).parent / "fixtures" / "amfi" / "navall_20261106.txt"
URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
HEADER = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;"
    "Plan;Option;Net Asset Value;Date"
)
CAT = "Open Ended Schemes(Debt Scheme - Liquid Fund)"
CHILD = "Children\N{RIGHT SINGLE QUOTATION MARK}s Fund - Childrens' Fund"
CREDIT = "Debt Scheme - Credit Risk Fund"
OK = "1;INF846K01WS2;-;Fund;Direct Plan;Growth;1.5;06-Nov-2026"


def _text(*rows: str, category: str = CAT, amc: str = "X Mutual Fund") -> str:
    lines = [HEADER, " ", category, " ", amc, " ", *rows]
    return "\r\n".join(lines) + "\r\n"


def _row(**kw: str) -> str:
    f = {"code": "1", "name": "Fund", "nav": "1.5", "date": "06-Nov-2026"} | kw
    return f"{f['code']};-;-;{f['name']};P;O;{f['nav']};{f['date']}"


def _client(
    body: bytes, *, content_type: str = "text/plain", status: int = 200
) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            status, content=body, headers={"Content-Type": content_type}
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def _fixture_client() -> httpx.Client:
    return _client(FIXTURE.read_bytes())[0]


def _by_code() -> dict[str, NavRecord]:
    navs: list[NavRecord] = latest_navs(client=_fixture_client())
    return {n.amfi_code: n for n in navs}


def test_latest_navs_returns_fixture_rows_in_file_order() -> None:  # AC1
    navs = latest_navs(client=_fixture_client())
    assert len(navs) == 29
    assert navs[0].amfi_code == "135762"
    assert navs[-1].amfi_code == "130565"
    assert _by_code()["135763"] == NavRecord(
        amfi_code="135763",
        scheme_name="Axis Children's Fund",
        plan="Direct Plan",
        option="IDCW Option",
        isin="INF846K01WS2",
        isin_reinvestment="INF846K01WQ6",
        date=dt.date(2026, 11, 6),
        nav=Decimal("28.3978"),
    )


def test_latest_navs_keeps_each_rows_own_date() -> None:  # AC2
    by = _by_code()
    got = {c: by[c].date for c in ("151835", "123689", "108694")}
    assert got == {
        "151835": dt.date(2026, 11, 8),
        "123689": dt.date(2017, 9, 15),
        "108694": dt.date(2008, 10, 2),
    }
    assert len({n.date for n in by.values()}) == 9


def test_latest_navs_cleans_isin_values() -> None:  # AC3
    by = _by_code()
    assert by["109472"].isin is None
    nones = [by[c].isin_reinvestment for c in ("152713", "130565", "135762")]
    assert nones == [None, None, None]
    assert by["133786"].isin_reinvestment == "INF178L01BT0"


def test_latest_navs_keeps_zero_and_long_navs() -> None:  # AC4
    by = _by_code()
    assert (by["148239"].plan, by["148239"].option) == (None, None)
    navs = [str(by[c].nav) for c in ("148239", "148304", "146839", "130565")]
    assert navs == ["0", "0.0000", "10.0087785", "1680494.0463"]


def test_schemes_reads_amc_type_and_category_from_headers() -> None:  # AC5
    found = schemes(client=_fixture_client())
    assert len(found) == 29
    by = {s.amfi_code: s for s in found}
    got = {
        c: (by[c].amc, by[c].scheme_type, by[c].category)
        for c in ("135763", "148239", "146839", "130565")
    }
    assert got == {
        "135763": ("Axis Mutual Fund", "Open Ended Schemes", CHILD),
        "148239": ("UTI Mutual Fund", "Open Ended Schemes", CREDIT),
        "146839": ("Kotak Mahindra Mutual Fund", "Interval Fund Schemes", "Income"),
        "130565": ("IL&FS Mutual Fund (IDF)", "Close Ended Schemes", "Income"),
    }
    for code, rec in _by_code().items():
        sch = by[code]
        assert (sch.isin, sch.isin_reinvestment) == (rec.isin, rec.isin_reinvestment)
        assert (sch.plan, sch.option) == (rec.plan, rec.option)


def test_latest_navs_skips_missing_nav_but_schemes_keeps_it(
    caplog: pytest.LogCaptureFixture,
) -> None:  # AC6
    rows = [_row(code=str(i), nav=v) for i, v in enumerate(["N.A.", "-", ""])]
    body = _text(*rows, _row(code="9", nav="2.5")).encode()
    with caplog.at_level(logging.INFO, logger="indianfinance.amfi"):
        navs = latest_navs(client=_client(body)[0])
    assert [n.amfi_code for n in navs] == ["9"]
    assert sum("skipped 3" in r.getMessage() for r in caplog.records) == 1
    assert len(schemes(client=_client(body)[0])) == 4


BAD_ROWS = [
    ("Wrong header\r\n" + _text(OK), 1),
    ("", 1),
    (HEADER + "\r\n", None),
    (_text("1;-;-;Fund;P;O;1.5"), 7),
    (_text("1;-;-;Fund;P;O;1.5;06-Nov-2026;x"), 7),
    (_text(_row(code="12a")), 7),
    (_text(_row(name="")), 7),
    (_text(_row(nav="abc")), 7),
    (_text(_row(nav="NaN")), 7),
    (_text(_row(nav="-1")), 7),
    (_text(_row(date="31-Feb-2026")), 7),
    (_text(OK, _row(code="2", nav="bad")), 8),
    (HEADER + "\r\n \r\n" + OK + "\r\n", 3),
    (HEADER + "\r\n \r\n" + CAT + "\r\n \r\n" + OK + "\r\n", 5),
]


@pytest.mark.parametrize(("text", "line"), BAD_ROWS)
def test_parse_rejects_bad_format_with_line(text: str, line: int | None) -> None:  # AC7
    for call in (latest_navs, schemes):
        with pytest.raises(SourceFormatError) as err:
            call(client=_client(text.encode())[0])
        assert err.value.line == line


def test_latest_navs_accepts_lf_line_endings() -> None:  # AC8
    lf = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
    assert b"\r" not in lf
    navs = latest_navs(client=_client(lf)[0])
    assert navs == latest_navs(client=_fixture_client())
    assert len(navs) == 29


def test_latest_navs_requests_portal_url_and_keeps_caller_client() -> None:  # AC9
    client, seen = _client(FIXTURE.read_bytes())
    latest_navs(client=client)
    assert [str(r.url) for r in seen] == [URL]
    assert seen[0].headers["User-Agent"].startswith("indianfinance/")
    assert not client.is_closed
    client.close()


def test_latest_navs_rejects_html_and_404_as_unavailable() -> None:  # AC9
    html = _client(b"<html>", content_type="text/html; charset=utf-8")[0]
    for client, status in ((html, 200), (_client(b"x", status=404)[0], 404)):
        with pytest.raises(SourceUnavailable) as err:
            latest_navs(client=client)
        assert (err.value.status_code, err.value.url) == (status, URL)
        assert not client.is_closed


def test_latest_navs_rejects_invalid_utf8_as_format_error() -> None:  # AC9
    with pytest.raises(SourceFormatError):
        latest_navs(client=_client(b"\xff")[0])


@pytest.mark.parametrize(
    ("line", "want"),
    [
        (
            "Open Ended Schemes(Debt Scheme - Gilt Fund)",
            ("Open Ended Schemes", "Debt Scheme - Gilt Fund"),
        ),
        (
            "Open Ended Schemes ( Equity Scheme - Multi Cap Fund )",
            ("Open Ended Schemes", "Equity Scheme - Multi Cap Fund"),
        ),
        ("IL&FS Mutual Fund (IDF)", None),
        ("Axis Mutual Fund", None),
    ],
)
def test_split_category_handles_inner_spaces_and_amc_brackets(
    line: str, want: tuple[str, str] | None
) -> None:  # parsing rule 4
    assert _split_category(line) == want


@pytest.mark.parametrize("text", ["inf846k01ws2", "INF846K01WS", "INF846K01WSX", ""])
def test_parse_isin_rejects_wrong_shape(text: str) -> None:  # AC3
    assert _parse_isin(text) is None


def test_latest_navs_drops_utf8_bom() -> None:  # edge case: BOM
    navs = latest_navs(client=_client(("﻿" + _text(OK)).encode())[0])
    assert [n.amfi_code for n in navs] == ["1"]


@pytest.mark.live
def test_latest_navs_and_schemes_live() -> None:  # AC10
    navs = latest_navs()
    assert len(navs) > 10_000
    for n in navs:
        assert n.amfi_code.isdigit()
        for isin in (n.isin, n.isin_reinvestment):
            assert isin is None or len(isin) == 12
    found = schemes()
    assert len(found) >= len(navs)
    assert all(s.amc and s.scheme_type and s.category for s in found)
