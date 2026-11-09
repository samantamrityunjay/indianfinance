"""Tests for returns.rolling_returns (T-013). Expected values are hand arithmetic."""

from __future__ import annotations

import datetime as dt
import decimal
from decimal import Decimal
from functools import partial
from typing import Any

import pytest

from indianfinance import models, returns
from indianfinance.exceptions import IndianFinanceError
from indianfinance.models import NavRecord

D = Decimal
F: Any = 1.5  # a float the type checker lets through
NONE: dict[str, Any] = dict.fromkeys(["plan", "option", "isin", "isin_reinvestment"])
NAV = partial(NavRecord, amfi_code="1", scheme_name="F", **NONE)
# Series text: "date:value" words. Result text: "start>end:cagr" words (10 places).
S = "2020-01-02:100 2021-01-01:110 2022-01-01:121 2022-07-01:110 2023-01-01:133.1"
S_OUT = "2021-01-01>2022-01-01:0.1000000000 2021-01-01>2022-07-01:0.0000000000 "
S_OUT += "2022-01-01>2023-01-01:0.1000000000"
T = "2021-01-01:100 2022-01-01:105 2023-01-01:121 2024-01-01:127.05"
T_OUT = "2021-01-01>2023-01-01:0.1000000000 2022-01-01>2024-01-01:0.1000000000"
FEB = "2023-02-28:100 2024-02-29:110"
FEB_OUT = "2023-02-28>2024-02-29:0.0997135859"  # 1.1 ** (365 / 366) - 1


def pts(text: str) -> list[tuple[dt.date, D]]:
    words = (w.split(":") for w in text.split())
    return [(dt.date.fromisoformat(a), F if b == "F" else D(b)) for a, b in words]


def show(rows: list[models.RollingReturn]) -> str:  # rounds outside any context block
    return " ".join(f"{r.start}>{r.end}:{round(r.cagr, 10):f}" for r in rows)


ROLLING_CASES = [  # AC1-AC5: (points, years, result text)
    (S, 1, S_OUT),
    (T, 2, T_OUT),
    (" ".join(reversed(T.split())), 2, T_OUT),
    (FEB, 1, FEB_OUT),
    ("2020-02-29:100 2021-03-01:110", 1, "2020-02-29>2021-03-01:0.0997135859"),
    ("2021-01-01:100 2022-01-01:0", 1, "2021-01-01>2022-01-01:-1.0000000000"),
    ("", 1, ""),
    ("2021-01-01:100", 1, ""),
    (T, 5, ""),
    ("2021-01-01:100 2021-12-31:110", 1, ""),
]
ROLLING_ERRORS = [  # AC7: (points, years, exception, message part)
    (T, 0, ValueError, "years must be >= 1, got 0"),
    (T, -1, ValueError, "years must be >= 1, got -1"),
    (T, F, TypeError, "years must be an int, got float"),
    (T, True, TypeError, "got bool"),
    (T, D(1), TypeError, "got Decimal"),
    ("2021-01-01:1 2021-01-01:2", 0, ValueError, "years must be >= 1"),
    ("2021-01-01:0 2022-01-01:5", 1, ValueError, "2021-01-01 must be > 0 to start"),
    ("2021-01-01:1 2021-01-01:2", 1, ValueError, "duplicate date"),
    ("2021-01-01:-1 2022-01-01:5", 1, ValueError, "must be >= 0"),
    ("2021-01-01:F 2022-01-01:5", 1, TypeError, "is a float"),
]


@pytest.mark.parametrize(("text", "years", "want"), ROLLING_CASES)
def test_rolling_returns_hand_arithmetic(text: str, years: int, want: str) -> None:
    assert show(returns.rolling_returns(pts(text), years)) == want  # AC1-AC5


def test_rolling_returns_keeps_exact_values() -> None:
    rows = returns.rolling_returns(pts(S), 1)  # AC1: values are the series values
    got = " ".join(f"{r.start_value}/{r.end_value}" for r in rows)
    assert got == "110/121 110/110 121/133.1"


def test_rolling_returns_accepts_nav_records_and_generators() -> None:  # AC5, AC6
    navs = [NAV(date=d, nav=v) for d, v in pts(T)]
    rows: list[models.RollingReturn] = returns.rolling_returns(navs, 2)
    assert type(rows[0]) is models.RollingReturn
    assert isinstance(rows[0].cagr, D)
    assert show(rows) == T_OUT
    assert show(returns.rolling_returns((p for p in pts(T)), 2)) == T_OUT


@pytest.mark.parametrize(("text", "years", "exc", "match"), ROLLING_ERRORS)
def test_rolling_returns_rejects_bad_arguments(
    text: str, years: Any, exc: type[Exception], match: str
) -> None:
    with pytest.raises(exc, match=match) as info:  # AC7
        returns.rolling_returns(pts(text), years)
    assert not isinstance(info.value, IndianFinanceError)


def test_rolling_returns_ignore_caller_decimal_context() -> None:  # AC8
    with decimal.localcontext(prec=6, rounding=decimal.ROUND_DOWN):
        rows = returns.rolling_returns(pts(FEB), 1)
        ctx = decimal.getcontext()
        assert (ctx.prec, ctx.rounding) == (6, decimal.ROUND_DOWN)
    assert show(rows) == FEB_OUT
