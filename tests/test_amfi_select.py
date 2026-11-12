"""Tests for amfi fund selection: latest_navs filters, latest_nav."""

import datetime as dt
from decimal import Decimal as Dec
from pathlib import Path
from typing import Any

import httpx
import pytest

from indianfinance import amfi
from indianfinance.exceptions import SymbolNotFound
from indianfinance.models import NavRecord

FIXTURE = Path(__file__).parent / "fixtures" / "amfi" / "navall_20261106.txt"
HEADER = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;"
    "Plan;Option;Net Asset Value;Date"
)
AXIS = ["135762", "135765", "135759", "135760", "135764", "135763", "135766", "135761"]
NA_ROW = "2;-;-;Fund;P;O;N.A.;06-Nov-2026"


def _client(body: bytes) -> tuple[httpx.Client, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=body, headers={"Content-Type": "text/plain"})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def _fixture() -> tuple[httpx.Client, list[httpx.Request]]:
    return _client(FIXTURE.read_bytes())


def _text(*rows: str) -> bytes:
    lines = [HEADER, " ", "Open Ended Schemes(Debt Scheme - Liquid Fund)", " "]
    return ("\r\n".join([*lines, "X Mutual Fund", " ", *rows]) + "\r\n").encode()


def _codes(navs: list[NavRecord]) -> list[str]:
    return [r.amfi_code for r in navs]


def test_latest_navs_selects_codes_and_isins_in_file_order() -> None:  # AC1
    client, _ = _fixture()
    navs = amfi.latest_navs(
        codes=["INF0QA701011", "135763", "INF204K01EG7"], client=client
    )
    assert _codes(navs) == ["135763", "109472", "151833"]
    # source value "INF178L01BT0 " has a trailing space
    assert _codes(amfi.latest_navs(codes=["INF178L01BT0"], client=client)) == ["133786"]


def test_latest_navs_returns_each_row_once_for_repeated_codes() -> None:  # AC2
    client, seen = _fixture()
    navs = amfi.latest_navs(
        codes=iter(["135763", "INF846K01WS2", "135763"]), client=client
    )
    assert _codes(navs) == ["135763"]
    assert len(seen) == 1


def test_latest_navs_raises_symbol_not_found_for_missing_codes() -> None:  # AC3
    client, _ = _fixture()
    with pytest.raises(SymbolNotFound, match="999999") as exc:
        amfi.latest_navs(codes=["135763", "999999", "INF000000000"], client=client)
    assert exc.value.symbol == "999999"
    assert "INF000000000" in str(exc.value)


def test_latest_navs_treats_na_nav_as_missing_code() -> None:  # AC3
    client, _ = _client(_text(NA_ROW))
    with pytest.raises(SymbolNotFound) as exc:
        amfi.latest_navs(codes=["2"], client=client)
    assert exc.value.symbol == "2"


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"name": "AXIS children's"}, AXIS),  # AC4a
        ({"plan": "Regular", "option": "growth"}, ["135759", "135766", "148303"]),
        ({"name": "no such fund"}, []),  # AC4d
    ],
)
def test_latest_navs_matches_name_plan_option_substrings(
    kwargs: dict[str, str], expected: list[str]
) -> None:  # AC4
    client, seen = _fixture()
    assert _codes(amfi.latest_navs(client=client, **kwargs)) == expected
    assert len(seen) == 1


def test_latest_navs_plan_filter_skips_rows_with_empty_plan() -> None:  # AC4c
    client, _ = _fixture()
    navs = amfi.latest_navs(plan="direct", client=client)
    assert len(navs) == 14
    assert all(r.plan is not None for r in navs)


@pytest.mark.parametrize("name", ["fund- direct", "FUND-   DIRECT"])
def test_latest_navs_name_match_collapses_spaces(name: str) -> None:  # AC4
    row = "3;-;-;FUND-  Direct Growth;Direct Plan;Growth;1.5;06-Nov-2026"
    client, _ = _client(_text(row))
    assert _codes(amfi.latest_navs(name=name, client=client)) == ["3"]


def test_latest_nav_returns_one_record_by_code() -> None:  # AC5
    client, _ = _fixture()
    rec: NavRecord = amfi.latest_nav("135763", client=client)
    assert rec == NavRecord(
        amfi_code="135763",
        scheme_name="Axis Children's Fund",
        plan="Direct Plan",
        option="IDCW Option",
        isin="INF846K01WS2",
        isin_reinvestment="INF846K01WQ6",
        date=dt.date(2026, 11, 6),
        nav=Dec("28.3978"),
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code": "INF0QA701011"},
        {"name": "Bajaj Finserv Liquid Fund", "plan": "Direct", "option": "Growth"},
    ],
)
def test_latest_nav_returns_one_record_by_isin_or_name(
    kwargs: dict[str, str],
) -> None:  # AC5
    client, _ = _fixture()
    rec = amfi.latest_nav(client=client, **kwargs)
    assert rec.amfi_code == "151833"
    assert rec.date == dt.date(2026, 11, 8)
    assert rec.nav == Dec("1251.5290")


@pytest.mark.parametrize(
    ("args", "symbol"),
    [
        ({"code": "999999"}, "999999"),
        ({"name": "No Such Fund"}, "No Such Fund"),
        ({"code": "2"}, "2"),  # appended row with N.A. NAV
    ],
)
def test_latest_nav_raises_symbol_not_found_when_nothing_matches(
    args: dict[str, str], symbol: str
) -> None:  # AC6
    client, _ = _client(FIXTURE.read_bytes() + NA_ROW.encode() + b"\r\n")
    with pytest.raises(SymbolNotFound) as exc:
        amfi.latest_nav(client=client, **args)
    assert exc.value.symbol == symbol


def test_latest_nav_lists_both_codes_when_two_schemes_match() -> None:  # AC7
    client, _ = _fixture()
    with pytest.raises(ValueError, match="2 schemes") as exc:
        amfi.latest_nav(
            name="Axis Children's Fund", plan="Direct", option="Growth", client=client
        )
    assert "135762" in str(exc.value)
    assert "135764" in str(exc.value)


def test_latest_nav_lists_five_candidates_and_remainder_when_eight_match() -> (
    None
):  # AC7
    client, _ = _fixture()
    with pytest.raises(ValueError, match="8 schemes") as exc:
        amfi.latest_nav(name="axis", client=client)
    msg = str(exc.value)
    assert all(code in msg for code in AXIS[:5])
    assert "and 3 more" in msg
    assert "135761" not in msg


MISTAKES: list[tuple[str, tuple[Any, ...], dict[str, Any], type[Exception]]] = [
    ("latest_navs", (), {"codes": "135763"}, TypeError),
    ("latest_navs", (), {"codes": [135763]}, TypeError),
    ("latest_navs", (), {"codes": ["abc"]}, ValueError),
    ("latest_navs", (), {"codes": [" 135763"]}, ValueError),
    ("latest_navs", (), {"codes": [""]}, ValueError),
    ("latest_navs", (), {"codes": ["inf846k01ws2"]}, ValueError),
    ("latest_navs", (), {"codes": ["HDFCNIVODG"]}, ValueError),
    ("latest_navs", (), {"name": ""}, ValueError),
    ("latest_navs", (), {"name": "  "}, ValueError),
    ("latest_navs", (), {"plan": ""}, ValueError),
    ("latest_navs", (), {"option": " "}, ValueError),
    ("latest_navs", (), {"codes": ["135763"], "name": "Axis"}, ValueError),
    ("latest_navs", (), {"codes": [], "plan": "Direct"}, ValueError),
    ("latest_nav", (), {}, ValueError),
    ("latest_nav", ("135763",), {"name": "Axis"}, ValueError),
    ("latest_nav", ("135763",), {"plan": "Direct"}, ValueError),
    ("latest_nav", (), {"plan": "Direct"}, ValueError),
    ("latest_nav", (135763,), {}, TypeError),
]


@pytest.mark.parametrize(("func", "args", "kwargs", "exc"), MISTAKES)
def test_filter_rejects_caller_mistakes_without_request(
    func: str, args: tuple[Any, ...], kwargs: dict[str, Any], exc: type[Exception]
) -> None:  # AC8
    client, seen = _fixture()
    with pytest.raises(exc) as err:
        getattr(amfi, func)(*args, client=client, **kwargs)
    assert "unexpected keyword" not in str(err.value)  # not a missing parameter
    assert seen == []


def test_latest_navs_empty_codes_returns_empty_without_request() -> None:  # AC9
    client, seen = _fixture()
    assert amfi.latest_navs(codes=[], client=client) == []
    assert seen == []


def test_isin_on_row_with_missing_nav_is_not_found() -> None:  # AC3
    client, _ = _client(_text("2;INF111111111;-;Fund;P;O;N.A.;06-Nov-2026"))
    with pytest.raises(SymbolNotFound) as exc:
        amfi.latest_navs(codes=["INF111111111"], client=client)
    assert exc.value.symbol == "INF111111111"


def test_shared_isin_returns_both_rows_but_latest_nav_raises() -> None:  # edge
    rows = [f"{c};INF111111111;-;Fund {c};P;O;1.5;06-Nov-2026" for c in ("7", "8")]
    client, _ = _client(_text(*rows))
    assert _codes(amfi.latest_navs(codes=["INF111111111"], client=client)) == ["7", "8"]
    with pytest.raises(ValueError, match="2 schemes"):
        amfi.latest_nav("INF111111111", client=client)


def test_norm_collapses_tabs_and_spaces_and_casefolds() -> None:  # rule 6
    assert amfi._norm("  Axis \t\t Fund  X ") == "axis fund x"


def test_missing_code_listed_once_when_repeated() -> None:  # AC2, AC3
    client, _ = _fixture()
    with pytest.raises(SymbolNotFound) as exc:
        amfi.latest_navs(codes=["999999", "999999"], client=client)
    assert str(exc.value).count("999999") == 1


@pytest.mark.live
def test_latest_nav_and_codes_live() -> None:  # AC10
    rec = amfi.latest_nav("135763")
    assert rec.isin == "INF846K01WS2"
    assert rec.date >= dt.date(2026, 11, 6)
    navs = amfi.latest_navs(codes=["135763", "INF0QA701011"])
    assert {r.amfi_code for r in navs} == {"135763", "151833"}
