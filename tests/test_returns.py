"""Tests for indianfinance.returns (T-011). Reference values are hand arithmetic."""

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
from indianfinance.models import EodPrice, NavRecord, PricePoint

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
    assert returns.__all__ == ["DAYS_PER_YEAR", "absolute_return", "cagr"]
    assert returns.DAYS_PER_YEAR == 365
    assert indianfinance.__all__ == ["__version__"]
