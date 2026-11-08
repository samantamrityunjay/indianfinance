"""Tests for indianfinance.returns (T-011, T-012). Reference values are literals."""

import datetime as dt
import decimal
from collections.abc import Callable, Iterable
from decimal import Decimal
from functools import partial
from typing import Any

import pytest

import indianfinance
from indianfinance import returns
from indianfinance.exceptions import IndianFinanceError
from indianfinance.models import Cashflow, EodPrice, NavRecord, PricePoint

D = Decimal
absolute_return, cagr = returns.absolute_return, returns.cagr
Pts = Iterable[PricePoint | tuple[dt.date, D]]
F: Any = 121.0  # a float the type checker lets through
NONE: dict[str, Any] = dict.fromkeys(["plan", "option", "isin", "isin_reinvestment"])
NAV = partial(NavRecord, amfi_code="1", scheme_name="F", **NONE)
ONE: dict[str, Any] = dict.fromkeys(["open", "high", "low", "prev_close", "volume"], 1)
EOD = partial(EodPrice, symbol="A", series="EQ", isin="I", traded_value=D(1), **ONE)
THIRD = D("0.3333333333333333333333333333")

_d = dt.date.fromisoformat
A, B, C = _d("2021-01-01"), _d("2022-01-01"), _d("2023-01-01")
TEN = [(A, D("100")), (C, D("121"))]  # 730 days, 10 % a year


def xirr(flows: Iterable[Cashflow], **kw: Any) -> float:
    return returns.xirr(flows, **kw)  # looked up late: T-011 tests run without it


def cfs(*rows: tuple[dt.date | str, Any]) -> list[Cashflow]:
    return [Cashflow(_d(d) if isinstance(d, str) else d, D(a)) for d, a in rows]


MS = [("2008-01-01", -10000), ("2008-03-01", 2750), ("2008-10-30", 4250)]
MS += [("2009-02-15", 3250), ("2009-04-01", 2750)]
LO = [("2001-01-01", -10000), ("2001-02-01", 2000), ("2001-03-15", 2500)]
LO += [("2001-05-12", 5000), ("2001-08-10", 1000)]

ABSOLUTE_CASES = [  # AC1
    (D("10000"), D("11250"), D("0.125")),
    (D("50000"), D("41234.56"), D("-0.1753088")),
    (D("100"), D("100"), D("0")),
    (D("100"), D("0"), D("-1")),
    (D("3"), D("4"), THIRD),
    (200, 250, D("0.25")),
]
CAGR_CASES = [  # AC3: expected carries its own places
    (TEN, D("0.1000000000")),
    ([(A, D("100")), (B, D("200"))], D("1.0000000000")),
    ([(A, D("100")), (C, D("81"))], D("-0.1000000000")),
    ([(A, D("100")), (_d("2021-05-27"), D("105"))], D("0.1297263219")),
    ([(A, D("100")), (C, D("0"))], D("-1.0000000000")),
    ([(_d("2024-01-01"), D("100")), (_d("2025-01-01"), D("110"))], D("0.099714")),
]
SHAPE_CASES = [  # AC4: every shape gives the TEN result
    list(TEN),
    [NAV(date=A, nav=D("100")), NAV(date=C, nav=D("121"))],
    [EOD(date=A, close=D("100")), (C, D("121"))],
    TEN[::-1],
    (p for p in TEN),
    [(A, D("100")), (B, D("50")), (C, D("121"))],
]
ERROR_CASES: list[tuple[Callable[[], object], type[Exception], str]] = [  # AC5
    (lambda: absolute_return(D("0"), D("1")), ValueError, "start_value must be > 0"),
    (lambda: absolute_return(D("-1"), D("1")), ValueError, "start_value must be > 0"),
    (lambda: absolute_return(D("1"), D("-1")), ValueError, "end_value must be >= 0"),
    (lambda: absolute_return(F, D("1")), TypeError, "start_value is a float"),
    (lambda: absolute_return(D("1"), D("NaN")), ValueError, "end_value must be finite"),
    (lambda: absolute_return(D("Infinity"), D("1")), ValueError, "must be finite"),
    (lambda: cagr([]), ValueError, "got 0"),
    (lambda: cagr(TEN[:1]), ValueError, "got 1"),
    (lambda: cagr([(A, D("1")), (A, D("1"))]), ValueError, "duplicate date 2021-01-01"),
    (lambda: cagr([(A, D("0")), (C, D("1"))]), ValueError, "earliest point"),
    (lambda: cagr([(A, D("100")), (C, D("-5"))]), ValueError, "must be >= 0"),
    (lambda: cagr([(A, D("100")), (C, F)]), TypeError, "is a float"),
    (lambda: cagr([(A, D("100")), (C, D("sNaN"))]), ValueError, "must be finite"),
]
XIRR_CASES = [  # AC1 hand arithmetic (in/out)^(365/days)-1; AC2 spreadsheet help pages
    (cfs((A, -100), (C, 121)), 0.1, 1e-9),
    (cfs((A, -100), (B, 200)), 1.0, 1e-9),
    (cfs((A, -100), (C, 81)), -0.1, 1e-9),
    (cfs((A, -1000), (B, 1000)), 0.0, 1e-9),
    (cfs((A, -100), (B, 1)), -0.99, 1e-9),
    (cfs((A, -100), (B, 1000)), 9.0, 1e-9),
    (cfs((A, -100), ("2021-03-15", 110)), 0.61051, 1e-9),  # 1.1 ** 5 - 1, 73 days
    (cfs(*MS), 0.373362535, 1e-8),  # Microsoft XIRR help page
    (cfs(*MS[::-1]), 0.373362535, 1e-8),  # AC3: reversed order
    (cfs(*LO), 0.1828, 5e-5),  # LibreOffice XIRR help page
]
XIRR_SHAPES = [  # AC3: every shape gives 10 % a year
    cfs((C, 121), (A, -100)),
    iter(cfs((A, -100), (C, 121))),
    cfs((A, -60), (A, -40), (C, 121)),
    cfs((A, -100), (B, 0), (C, 121)),
    [Cashflow(A, -100 * ONE["open"]), Cashflow(C, 121 * ONE["open"])],  # int amounts
]
BAD = cfs((A, -100), (A, 100), (C, -1))  # present value is below 0 for every rate
XIRR_ERRORS: list[tuple[Callable[[], object], type[Exception], str]] = [  # AC5
    (lambda: xirr([]), ValueError, "got 0"),
    (lambda: xirr(cfs((A, -1))), ValueError, "got 1"),
    (lambda: xirr(cfs((A, -1), (C, -1))), ValueError, "one negative and one positive"),
    (lambda: xirr(cfs((A, 1), (C, 1))), ValueError, "one negative and one positive"),
    (lambda: xirr(cfs((A, 0), (C, 0))), ValueError, "one negative and one positive"),
    (lambda: xirr(cfs((A, -5), (B, 0))), ValueError, "one negative and one positive"),
    (lambda: xirr(cfs((A, -100), (A, 100))), ValueError, "at least 2 dates"),
    (
        lambda: xirr([Cashflow(A, D(-1)), Cashflow(C, F)]),
        TypeError,
        "amount on 2023-01-01 is a float",
    ),
    (lambda: xirr(cfs((A, -1), (C, "NaN"))), ValueError, "must be finite"),
    (lambda: xirr(cfs(*MS), guess=-1.0), ValueError, "guess must be"),
    (lambda: xirr(cfs(*MS), guess=-2.0), ValueError, "guess must be"),
    (lambda: xirr(cfs(*MS), guess=float("nan")), ValueError, "guess must be"),
    (lambda: xirr(BAD), ValueError, "found no rate"),
]


@pytest.mark.parametrize(("start", "end", "want"), ABSOLUTE_CASES)
def test_absolute_return_matches_hand_arithmetic(start: Any, end: Any, want: D) -> None:
    assert isinstance(absolute_return(start, end), D)  # AC1
    assert absolute_return(start, end) == want


def test_returns_ignore_caller_decimal_context() -> None:  # AC2
    with decimal.localcontext(decimal.Context(prec=6, rounding=decimal.ROUND_DOWN)):
        a, r = absolute_return(D("3"), D("4")), cagr(TEN)
        c = decimal.getcontext()
        assert (c.prec, c.rounding) == (6, decimal.ROUND_DOWN)
    assert a == THIRD
    assert round(r, 10) == D("0.1000000000")


@pytest.mark.parametrize(("points", "expected"), CAGR_CASES)
def test_cagr_matches_reference_values(points: Pts, expected: D) -> None:  # AC3
    places = len(f"{expected:f}".split(".")[1])
    assert round(cagr(points), places) == expected


@pytest.mark.parametrize("series", SHAPE_CASES)
def test_cagr_accepts_any_series_shape(series: Pts) -> None:  # AC4
    assert round(cagr(series), 10) == D("0.1000000000")


@pytest.mark.parametrize(("call", "exc_type", "match"), ERROR_CASES)
def test_returns_reject_bad_arguments(
    call: Callable[[], object], exc_type: type[Exception], match: str
) -> None:
    with pytest.raises(exc_type, match=match) as info:  # AC5
        call()
    assert not isinstance(info.value, IndianFinanceError)


def test_returns_public_names() -> None:  # AC6
    assert returns.__all__ == ["DAYS_PER_YEAR", "absolute_return", "cagr", "xirr"]
    assert returns.DAYS_PER_YEAR == 365
    assert indianfinance.__all__ == ["__version__"]


@pytest.mark.parametrize(("flows", "expected", "tol"), XIRR_CASES)
def test_xirr_matches_reference_values(
    flows: list[Cashflow], expected: float, tol: float
) -> None:
    assert abs(xirr(flows) - expected) <= tol  # AC1, AC2, AC3


@pytest.mark.parametrize("flows", XIRR_SHAPES)
def test_xirr_ignores_order_and_same_day_split(flows: Iterable[Cashflow]) -> None:
    assert abs(xirr(flows) - 0.1) <= 1e-9  # AC3


def test_xirr_guess_and_bisection_fallback() -> None:  # AC4
    lost = cfs((A, -100), (C, 81))
    assert abs(xirr(lost, guess=10.0) - -0.1) <= 1e-9  # Newton leaves the range
    assert abs(xirr(cfs((A, -100), (C, 121)), guess=0.5) - 0.1) <= 1e-9
    assert abs(xirr(lost, guess=0) - -0.1) <= 1e-9  # int guess


@pytest.mark.parametrize(("call", "exc_type", "match"), XIRR_ERRORS)
def test_xirr_rejects_bad_input(
    call: Callable[[], object], exc_type: type[Exception], match: str
) -> None:
    with pytest.raises(exc_type, match=match) as info:  # AC5
        call()
    assert not isinstance(info.value, IndianFinanceError)


def test_xirr_returns_float_for_direct_call() -> None:  # AC6
    r: float = returns.xirr([Cashflow(A, D("-100")), Cashflow(C, D("121"))])
    assert type(r) is float
    assert r == pytest.approx(0.1, abs=1e-9)


def test_xirr_zeroes_present_value_for_sip() -> None:  # AC7
    sip = cfs(
        *[(f"2025-{m:02d}-05", -5000) for m in range(1, 13)], ("2026-01-05", 64000)
    )
    r = xirr(sip)
    t0 = sip[0].date
    pv = sum(float(c.amount) * (1 + r) ** (-(c.date - t0).days / 365) for c in sip)
    assert abs(pv) < 1e-6
    assert abs(r - 0.1248) <= 5e-5  # how-to page value, checked by hand with bisection


def test_xirr_sip_variants_match_hand_bisection() -> None:  # AC7
    sip = cfs(*[(f"2025-{m:02d}-05", -5000) for m in range(1, 13)])
    units_nav = [*sip, Cashflow(_d("2026-01-05"), D("64001.43"))]
    redeemed = [*sip, *cfs(("2025-07-05", 10000), ("2026-01-05", 53500))]
    assert abs(xirr(units_nav) - 0.12486) <= 5e-5  # bisection gives 0.124862
    assert abs(xirr(redeemed) - 0.12896) <= 5e-5  # bisection gives 0.128965
