"""Tests for amfi.nav_history (httpx.MockTransport only; one live test)."""

import datetime as dt
import logging
from decimal import Decimal as Dec
from pathlib import Path
from typing import Any

import httpx
import pytest

import indianfinance._http as _http
from indianfinance.amfi import HISTORY_TIMEOUT, nav_history
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
NAVALL = "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name"
NO_DATA = b"<html>No data found on the basis of selected parameters</html>"
HTML = {"Content-Type": "text/html; charset=utf-8"}
LOC = "https://www.amfiindia.com/net-asset-value/nav-download"
D = dt.date
NOV5, NOV6 = D(2026, 11, 5), D(2026, 11, 6)


def _row(
    code: str = "1", nav: str = "1.5", date: str = "06-Nov-2026", name: str = "Fund"
) -> str:
    return f"{code};{name};Direct Plan;GROWTH;;;{nav};{date}"


def _text(*rows: str) -> str:  # header + 5 filler lines, so the first row is line 7
    head = [HEADER, "", "Open Ended Schemes ( Equity )", "", "", "Some Mutual Fund"]
    return "\r\n".join([*head, *rows]) + "\r\n"


def _serve(*replies: Any) -> tuple[httpx.Client, list[httpx.Request]]:
    """Client answering in order (last reply repeats); records the requests."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        reply = replies[min(len(seen), len(replies) - 1)]
        seen.append(request)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, bytes):
            return httpx.Response(200, content=reply, headers=HTML)
        if isinstance(reply, httpx.Response):
            return reply
        return httpx.Response(200, text=reply)

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def _file(path: Path) -> str:
    return path.read_bytes().decode("utf-8")  # read_text would turn CRLF into LF


def _two_days(**kw: Any) -> list[NavRecord]:
    navs: list[NavRecord] = nav_history(
        NOV5, NOV6, client=_serve(_file(TWO_DAYS))[0], **kw
    )
    return navs


def test_nav_history_returns_fixture_rows_in_file_order() -> None:  # AC1
    navs = _two_days()
    assert len(navs) == 16
    assert navs[0] == NavRecord(
        amfi_code="148921",
        scheme_name="Aditya Birla Sun Life Multi-Cap Fund-Direct Growth",
        plan="Direct Plan",
        option="GROWTH",
        isin="INF209KB1Y49",
        isin_reinvestment=None,
        date=NOV5,
        nav=Dec("22.77"),
    )
    assert (navs[1].date, navs[1].nav) == (NOV6, Dec("22.83"))
    codes = [148921, 148920, 148918, 151233, 151236, 151835, 151838, 145399]
    assert [n.amfi_code for n in navs] == [str(c) for c in codes for _ in (0, 1)]


def test_nav_history_cleans_empty_and_dash_isins() -> None:  # AC2
    by = {n.amfi_code: (n.isin, n.isin_reinvestment) for n in _two_days()}
    assert by["151233"] == (None, "INF277KA1687")
    assert by["145399"] == (None, "INF109KC1ND7")
    assert by["151838"] == ("INF0QA701078", "INF0QA701045")


def test_nav_history_reads_sunday_file() -> None:  # AC3
    client, _ = _serve(_file(SUNDAY))
    navs = nav_history(D(2026, 11, 8), D(2026, 11, 8), client=client)
    assert len(navs) == 10
    assert {n.date for n in navs} == {D(2026, 11, 8)}
    name = "ADITYA BIRLA SUN LIFE OVERNIGHT FUND-  Direct - Monthly Payout of IDCW"
    assert [navs[0].amfi_code, navs[0].scheme_name] == ["145488", name]
    assert navs[0].option == "Monthly IDCW"


def test_nav_history_filters_by_amfi_code() -> None:  # AC4
    navs = _two_days(amfi_code="151835")
    assert [n.date for n in navs] == [NOV5, NOV6]
    assert [n.nav for n in navs] == [Dec("1034.6939")] * 2


def test_nav_history_raises_symbol_not_found_for_unknown_code() -> None:  # AC4
    with pytest.raises(SymbolNotFound) as err:
        _two_days(amfi_code="999999")
    assert err.value.symbol == "999999"


P91 = ["08-Aug-2026..05-Nov-2026", "06-Nov-2026..06-Nov-2026"]
P182 = [
    "01-Jan-2026..31-Mar-2026",
    "01-Apr-2026..29-Jun-2026",
    "30-Jun-2026..01-Jul-2026",
]


@pytest.mark.parametrize(
    ("start", "end", "pieces"),
    [(D(2026, 8, 8), NOV6, P91), (D(2026, 1, 1), D(2026, 7, 1), P182)],
)
def test_nav_history_splits_range_into_90_day_requests(
    start: dt.date, end: dt.date, pieces: list[str]
) -> None:  # AC5
    # One row per piece, dated with the piece's last day; code = piece number.
    replies = [_text(_row(str(i), date=p[-11:])) for i, p in enumerate(pieces)]
    client, seen = _serve(*replies)
    navs = nav_history(start, end, client=client)
    want = [f"{URL}?frmdt={p[:11]}&todt={p[-11:]}" for p in pieces]
    assert [str(r.url) for r in seen] == want
    assert all(r.headers["User-Agent"].startswith("indianfinance/") for r in seen)
    assert [n.amfi_code for n in navs] == [str(i) for i in range(len(pieces))]
    assert not client.is_closed


@pytest.mark.parametrize(
    ("replies", "end", "code"),
    [([NO_DATA], D(2026, 1, 1), None), ([NO_DATA] * 2, D(2026, 5, 1), "1")],
)
def test_nav_history_raises_no_data_when_every_piece_is_empty(
    replies: list[bytes], end: dt.date, code: str | None
) -> None:  # AC6
    client, _ = _serve(*replies)
    with pytest.raises(NoDataForDate) as err:
        nav_history(D(2026, 1, 1), end, amfi_code=code, client=client)
    assert err.value.day == D(2026, 1, 1)


def test_nav_history_skips_empty_piece_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:  # AC6
    caplog.set_level(logging.INFO, logger="indianfinance.amfi")
    client, seen = _serve(NO_DATA, _text(_row(date="01-Apr-2026")))
    navs = nav_history(D(2026, 1, 1), D(2026, 5, 1), client=client)
    assert [(n.amfi_code, n.date) for n in navs] == [("1", D(2026, 4, 1))]
    assert len(seen) == 2
    assert sum("no data" in r.getMessage() for r in caplog.records) == 1


HTML_OK = httpx.Response(200, text="<html>Oops</html>", headers=HTML)
REDIRECT = [httpx.Response(302, headers={"Location": LOC}), HTML_OK]


@pytest.mark.parametrize(
    ("replies", "status", "text"),
    [
        (REDIRECT, 200, "redirected"),
        ([HTML_OK], 200, ""),
        ([httpx.Response(404)], 404, ""),
    ],
)
def test_nav_history_rejects_bad_reply(
    replies: list[Any], status: int, text: str
) -> None:  # AC7
    client, _ = _serve(*replies)
    with pytest.raises(SourceUnavailable, match=text or None) as err:
        nav_history(NOV5, NOV6, client=client)
    assert err.value.status_code == status
    if text:
        assert err.value.url.startswith(URL)
        assert "frmdt=" in err.value.url


def test_nav_history_retries_timeout_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # AC7
    monkeypatch.setattr(_http, "BACKOFF_BASE", 0.0)
    client, seen = _serve(httpx.ReadTimeout("slow"))
    with pytest.raises(SourceUnavailable):
        nav_history(NOV5, NOV6, client=client)
    assert len(seen) == 2


BAD = [  # (file text, expected .line); the bad row is line 8, after one good row
    (NAVALL + "\r\n", 1),
    ("", 1),
    (HEADER + "\r\n", None),
    (_text(_row(), "1;Fund;Direct Plan;GROWTH;;1.5;06-Nov-2026"), 8),
    (_text(_row(), _row() + ";x"), 8),
    (_text(_row(), _row(code="12a")), 8),
    (_text(_row(), _row(name="")), 8),
    (_text(_row(), _row(nav="abc")), 8),
    (_text(_row(), _row(date="31-Feb-2026")), 8),
    (_text(_row(), _row(date="07-Nov-2026")), 8),
]


@pytest.mark.parametrize(("text", "line"), BAD)
def test_nav_history_rejects_bad_format_with_line(
    text: str, line: int | None
) -> None:  # AC8
    with pytest.raises(SourceFormatError) as err:
        nav_history(NOV5, NOV6, client=_serve(text)[0])
    assert err.value.line == line


def test_nav_history_skips_missing_nav_keeps_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:  # AC9
    caplog.set_level(logging.INFO, logger="indianfinance.amfi")
    rows = [_row(str(i), nav) for i, nav in enumerate(["N.A.", "-", "", "0", "1.5"])]
    navs = nav_history(NOV5, NOV6, client=_serve(_text(*rows))[0])
    assert [(n.amfi_code, n.nav) for n in navs] == [("3", Dec("0")), ("4", Dec("1.5"))]
    assert sum("skipped 3" in r.getMessage() for r in caplog.records) == 1


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        (NOV6, NOV5, None),
        (NOV5, NOV6, "abc"),
        (NOV5, NOV6, " 148921"),
        (NOV5, NOV6, ""),
    ],
)
def test_nav_history_rejects_caller_mistakes_without_request(
    start: dt.date, end: dt.date, code: str | None
) -> None:  # AC10
    client, seen = _serve(_file(TWO_DAYS))
    with pytest.raises(ValueError, match=r"start|amfi_code"):
        nav_history(start, end, amfi_code=code, client=client)
    assert seen == []


def test_nav_history_uses_history_timeout_unless_client_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # AC11
    used: list[httpx.Timeout] = []

    def fake_make_client(
        *, timeout: httpx.Timeout = _http.DEFAULT_TIMEOUT
    ) -> httpx.Client:
        used.append(timeout)
        return _serve(_text(_row()))[0]

    monkeypatch.setattr(_http, "make_client", fake_make_client)
    nav_history(NOV5, NOV6)
    assert used == [HISTORY_TIMEOUT]
    assert (HISTORY_TIMEOUT.read, HISTORY_TIMEOUT.connect) == (300.0, 10.0)
    mine, seen = _serve(_text(_row()))
    mine.timeout = httpx.Timeout(5.0)
    nav_history(NOV5, NOV6, client=mine)
    assert seen[0].extensions["timeout"]["read"] == 5.0
    assert len(used) == 1  # no second client was made


def test_nav_history_raises_when_later_piece_fails_without_partial_result() -> None:
    client, seen = _serve(_text(_row(date="31-Mar-2026")), httpx.Response(404))
    with pytest.raises(SourceUnavailable) as err:
        nav_history(D(2026, 1, 1), D(2026, 5, 1), client=client)
    assert (len(seen), err.value.status_code) == (2, 404)  # spec: edge cases


def test_nav_history_amfi_code_skips_other_schemes_bad_rows() -> None:
    other = [
        _row("2", "abc"),
        _row("3", date="31-Feb-2026"),
        _row("4", date="01-Jan-2020"),
    ]
    navs = nav_history(
        NOV5, NOV6, amfi_code="1", client=_serve(_text(_row(), *other))[0]
    )
    assert [n.amfi_code for n in navs] == ["1"]
    # rows were seen, none match: not a format error
    with pytest.raises(SymbolNotFound):
        nav_history(NOV5, NOV6, amfi_code="9", client=_serve(_text(*other))[0])


def test_nav_history_checks_date_range_of_row_with_missing_nav() -> None:
    text = _text(_row(nav="N.A.", date="07-Nov-2026"))
    with pytest.raises(SourceFormatError) as err:
        nav_history(NOV5, NOV6, client=_serve(text)[0])
    assert err.value.line == 7


def test_nav_history_drops_utf8_bom() -> None:
    body = b"\xef\xbb\xbf" + _text(_row()).encode()
    reply = httpx.Response(200, content=body, headers={"Content-Type": "text/plain"})
    assert len(nav_history(NOV5, NOV6, client=_serve(reply)[0])) == 1


def test_nav_history_accepts_lf_line_endings() -> None:  # AC12
    client, _ = _serve(_file(TWO_DAYS).replace("\r\n", "\n"))
    assert nav_history(NOV5, NOV6, client=client) == _two_days()


@pytest.mark.live
def test_nav_history_live() -> None:  # AC13
    navs = nav_history(NOV5, NOV6, amfi_code="148921")
    assert [(n.date, n.nav) for n in navs] == [
        (NOV5, Dec("22.77")),
        (NOV6, Dec("22.83")),
    ]
