"""Tests for amfi.navs_as_of (httpx.MockTransport only; one live test)."""

import datetime as dt
from decimal import Decimal as Dec
from pathlib import Path
from typing import Any

import httpx
import pytest

import indianfinance._http as _http
from indianfinance import amfi
from indianfinance.exceptions import (
    NoDataForDate,
    SourceFormatError,
    SourceUnavailable,
    SymbolNotFound,
)
from indianfinance.models import NavRecord

FIXTURES = Path(__file__).parent / "fixtures" / "amfi"
TWO_DAYS = FIXTURES / "nav_history_20261105_20261106.txt"
SUNDAY = FIXTURES / "nav_history_20261108.txt"
URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
HEADER = (
    "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;"
    "ISIN Div Reinvestment;Net Asset Value;Date"
)
NO_DATA = b"<html>No data found on the basis of selected parameters</html>"
D = dt.date
NOV5, NOV6, NOV8 = D(2026, 11, 5), D(2026, 11, 6), D(2026, 11, 8)
MISTAKES: list[tuple[dict[str, Any], type[Exception]]] = [
    ({"day": dt.datetime(2026, 11, 8)}, TypeError),  # noqa: DTZ001
    ({"day": "2026-11-08"}, TypeError),
    ({"lookback_days": 0}, ValueError),
    ({"lookback_days": 91}, ValueError),
    ({"lookback_days": -1}, ValueError),
    ({"lookback_days": True}, TypeError),
    ({"lookback_days": 7.0}, TypeError),
    ({"codes": "148921"}, TypeError),
    ({"codes": ["abc"]}, ValueError),
    ({"codes": ["148921"], "name": "Aditya"}, ValueError),
    ({"name": " "}, ValueError),
    ({"day": "x", "lookback_days": 0}, TypeError),  # day is checked first
]


def _file(path: Path) -> str:
    return path.read_bytes().decode("utf-8")  # read_text would turn CRLF into LF


def _week() -> str:  # 05/06-Nov file + the 08-Nov body (its header line dropped)
    return _file(TWO_DAYS) + _file(SUNDAY).split("\r\n", 1)[1]


def _text(*rows: str) -> str:  # header + 5 filler lines, so the first row is line 7
    head = [HEADER, "", "Open Ended Schemes ( Equity )", "", "", "Some Mutual Fund"]
    return "\r\n".join([*head, *rows]) + "\r\n"


def _row(code: str, nav: str, date: str) -> str:
    return f"{code};Fund {code};Direct Plan;GROWTH;;;{nav};{date}"


def _serve(
    body: str | bytes, content_type: str = "text/plain"
) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body, headers={"Content-Type": content_type})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def _codes(navs: list[NavRecord]) -> list[str]:
    return [n.amfi_code for n in navs]


def test_navs_as_of_returns_last_nav_per_scheme_with_real_date() -> None:  # AC1
    navs: list[NavRecord] = amfi.navs_as_of(NOV8, client=_serve(_week())[0])
    by_code = {n.amfi_code: n for n in navs}
    assert len(navs) == len(by_code) == 18
    first8 = ["148921", "148920", "148918", "151233"]
    first8 += ["151236", "151835", "151838", "145399"]
    assert _codes(navs)[:8] == first8
    assert by_code["148921"] == NavRecord(
        amfi_code="148921",
        scheme_name="Aditya Birla Sun Life Multi-Cap Fund-Direct Growth",
        plan="Direct Plan",
        option="GROWTH",
        isin="INF209KB1Y49",
        isin_reinvestment=None,
        date=NOV6,
        nav=Dec("22.83"),
    )
    assert (by_code["145486"].date, by_code["145486"].nav) == (NOV8, Dec("1502.8108"))
    assert {n.date for n in navs[:8]} == {NOV6}
    assert {n.date for n in navs[8:]} == {NOV8}


@pytest.mark.parametrize(
    ("kwargs", "frmdt", "todt"),
    [
        ({}, "02-Nov-2026", "08-Nov-2026"),
        ({"lookback_days": 1}, "08-Nov-2026", "08-Nov-2026"),
        ({"lookback_days": 90}, "11-Aug-2026", "08-Nov-2026"),
    ],
)
def test_navs_as_of_sends_one_request_for_the_window(
    kwargs: dict[str, Any], frmdt: str, todt: str
) -> None:  # AC2
    client, seen = _serve(_file(SUNDAY))
    amfi.navs_as_of(NOV8, client=client, **kwargs)
    assert len(seen) == 1
    assert str(seen[0].url).split("?")[0] == URL
    assert dict(seen[0].url.params) == {"frmdt": frmdt, "todt": todt}


def test_navs_as_of_picks_latest_date_and_first_row_on_tie() -> None:  # AC3
    rows = [
        _row("1", "1.6", "06-Nov-2026"),
        _row("1", "1.5", "05-Nov-2026"),
        _row("2", "2.1", "06-Nov-2026"),
        _row("2", "2.2", "06-Nov-2026"),
    ]
    navs = amfi.navs_as_of(NOV6, client=_serve(_text(*rows))[0])
    assert [(n.amfi_code, n.date, n.nav) for n in navs] == [
        ("1", NOV6, Dec("1.6")),
        ("2", NOV6, Dec("2.1")),
    ]


def test_navs_as_of_skips_missing_nav_to_earlier_date() -> None:  # AC4
    text = _text(
        _row("1", "1.5", "05-Nov-2026"),
        _row("1", "N.A.", "06-Nov-2026"),
        _row("2", "N.A.", "06-Nov-2026"),
    )
    navs = amfi.navs_as_of(NOV6, client=_serve(text)[0])
    assert [(n.amfi_code, n.date, n.nav) for n in navs] == [("1", NOV5, Dec("1.5"))]
    with pytest.raises(SymbolNotFound) as err:
        amfi.navs_as_of(NOV6, codes=["2"], client=_serve(text)[0])
    assert err.value.symbol == "2"


OVERNIGHT = "aditya birla sun life overnight fund"
BAJAJ = "Bajaj Finserv Liquid Fund"
SUNLIFE = {"name": "Sun Life Overnight", "plan": "Regular", "option": "Growth"}


@pytest.mark.parametrize(
    ("kwargs", "want", "dates"),
    [
        ({"codes": ["145486", "INF277KA1687"]}, ["151233", "145486"], None),  # a
        ({"name": OVERNIGHT, "plan": "direct", "option": "growth"}, ["145486"], None),
        ({"plan": "Regular", "option": "growth"}, ["148918", "145481"], None),  # c
        (SUNLIFE, [], None),  # d: AMFI writes SUNLIFE for 145481
        ({"name": BAJAJ}, ["151835", "151838"], [NOV6, NOV6]),  # e
    ],
)
def test_navs_as_of_filters_history_rows(
    kwargs: dict[str, Any], want: list[str], dates: list[dt.date] | None
) -> None:  # AC5
    client, seen = _serve(_week())
    navs = amfi.navs_as_of(NOV8, client=client, **kwargs)
    assert _codes(navs) == want
    assert len(seen) == 1
    if dates is not None:
        assert [n.date for n in navs] == dates


def test_navs_as_of_raises_symbol_not_found_for_missing_codes() -> None:  # AC6
    codes = ["148921", "999999", "INF000000000"]
    with pytest.raises(SymbolNotFound) as err:
        amfi.navs_as_of(NOV8, codes=codes, client=_serve(_week())[0])
    assert err.value.symbol == "999999"
    assert "999999" in str(err.value)
    assert "INF000000000" in str(err.value)


@pytest.mark.parametrize("day", [NOV8, D(2099, 1, 1)])
def test_navs_as_of_raises_no_data_for_day(day: dt.date) -> None:  # AC7
    client, seen = _serve(NO_DATA, "text/html; charset=utf-8")
    with pytest.raises(NoDataForDate) as err:
        amfi.navs_as_of(day, client=client)
    assert err.value.day == day
    assert len(seen) == 1
    assert seen[0].url.params["todt"] == day.strftime("%d-%b-%Y")
    assert client.is_closed is False


@pytest.mark.parametrize(("kwargs", "exc"), MISTAKES)
def test_navs_as_of_rejects_caller_mistakes_without_request(
    kwargs: dict[str, Any], exc: type[Exception]
) -> None:  # AC8
    client, seen = _serve(_week())
    with pytest.raises(exc):
        amfi.navs_as_of(**{"day": NOV8, "client": client, **kwargs})
    assert seen == []


def test_navs_as_of_empty_codes_returns_empty_without_request() -> None:  # AC8
    client, seen = _serve(_week())
    assert amfi.navs_as_of(NOV8, codes=[], client=client) == []
    assert seen == []


def test_navs_as_of_rejects_row_after_day() -> None:  # AC9
    client, _ = _serve(_file(TWO_DAYS))
    with pytest.raises(SourceFormatError) as err:
        amfi.navs_as_of(NOV5, client=client)
    assert err.value.line == 8  # first 06-Nov row


def test_navs_as_of_rejects_html_reply() -> None:  # AC10
    client, _ = _serve(b"<html>Maintenance</html>", "text/html")
    with pytest.raises(SourceUnavailable):
        amfi.navs_as_of(NOV8, client=client)


def test_navs_as_of_uses_history_timeout_unless_client_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # AC11
    used: list[httpx.Timeout] = []

    def fake_make_client(
        *, timeout: httpx.Timeout = _http.DEFAULT_TIMEOUT
    ) -> httpx.Client:
        used.append(timeout)
        return _serve(_file(SUNDAY))[0]

    monkeypatch.setattr(_http, "make_client", fake_make_client)
    amfi.navs_as_of(NOV8)
    assert used == [amfi.HISTORY_TIMEOUT]
    mine, _ = _serve(_file(SUNDAY))
    amfi.navs_as_of(NOV8, client=mine)
    assert mine.is_closed is False
    assert len(used) == 1  # no second client was made


def test_navs_as_of_window_start_crosses_year_boundary() -> None:  # AC2
    client, seen = _serve(_file(SUNDAY))
    with pytest.raises(SourceFormatError):  # fixture rows are Nov; only the URL matters
        amfi.navs_as_of(D(2026, 1, 3), client=client)
    assert seen[0].url.params["frmdt"] == "28-Dec-2025"


def test_navs_as_of_filters_the_chosen_row_not_an_older_one() -> None:  # rule 4
    old = "1;Alpha Fund;Direct Plan;GROWTH;INF000000001;;1.5;05-Nov-2026"
    new = "1;Beta Fund;Direct Plan;GROWTH;;;1.6;06-Nov-2026"
    text = _text(old, new)
    assert amfi.navs_as_of(NOV6, name="alpha", client=_serve(text)[0]) == []
    with pytest.raises(SymbolNotFound):  # ISIN is only on the older row
        amfi.navs_as_of(NOV6, codes=["INF000000001"], client=_serve(text)[0])
    beta = amfi.navs_as_of(NOV6, name="beta", client=_serve(text)[0])
    assert [(n.scheme_name, n.date) for n in beta] == [("Beta Fund", NOV6)]


@pytest.mark.live
def test_navs_as_of_live() -> None:  # AC13
    navs = amfi.navs_as_of(NOV8, codes=["148921", "145486"])
    by_code = {n.amfi_code: n for n in navs}
    assert set(by_code) == {"148921", "145486"}
    assert (by_code["148921"].date, by_code["148921"].nav) == (NOV6, Dec("22.83"))
    assert by_code["145486"].date == NOV8
