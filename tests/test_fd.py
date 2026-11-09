"""Tests for indianfinance.fd (T-014). Expected values are hand-derived literals."""

import datetime as dt
import decimal
from decimal import Decimal
from typing import Any

import pytest

import indianfinance
from indianfinance import fd
from indianfinance.exceptions import IndianFinanceError
from indianfinance.fd import COMPOUNDING_PERIODS as PERIODS
from indianfinance.fd import fd_value

D = Decimal
P, R = D("100000"), D("0.07")
Q: dict[str, Any] = {}  # quarterly, cumulative (the defaults)
NC: dict[str, Any] = {"cumulative": False}
Y: dict[str, Any] = {"compounding": "yearly"}
H: dict[str, Any] = {"compounding": "half-yearly"}
M: dict[str, Any] = {"compounding": "monthly"}
F: Any = 100000.0  # a float the type checker lets through
BAD: Any = "daily"  # a compounding name the type checker lets through
CMP = "compounding must be one of"
LATE = {"as_of": dt.date(2024, 12, 31)}

# principal, rate, start, as_of, kwargs, expected
FD_CASES: list[tuple[Any, D, str, str, dict[str, Any], str]] = [
    # AC1 whole periods
    (P, R, "2025-01-01", "2026-01-01", Q, "107185.90"),
    (P, R, "2025-01-01", "2027-01-01", Q, "114888.18"),
    (P, D("0.1"), "2025-01-01", "2027-01-01", Y, "121000.00"),
    (P, D("0.08"), "2025-01-01", "2026-01-01", H, "108160.00"),
    (P, D("0.12"), "2025-01-01", "2026-01-01", M, "112682.50"),
    # AC2 broken periods, simple part is actual / 365 even in a leap year
    (P, R, "2025-01-01", "2025-05-11", Q, "102530.55"),
    (P, R, "2025-01-01", "2025-03-01", Q, "101131.51"),
    (P, R, "2024-01-01", "2024-03-01", Q, "101150.68"),
    # AC3 month-end start: period ends are computed from start, half up
    (P, R, "2025-01-31", "2025-04-30", Q, "101750.00"),
    (P, R, "2025-01-31", "2025-04-29", Q, "101687.67"),
    (P, R, "2025-01-31", "2025-07-31", Q, "103530.63"),
    (P, R, "2024-02-29", "2025-02-28", Q, "107185.90"),  # 29 Feb: 4 whole quarters
    # AC4 non-cumulative ignores compounding
    (P, R, "2025-01-01", "2026-01-01", NC, "107000.00"),
    (P, R, "2024-01-01", "2025-01-01", NC, "107019.18"),
    (P, R, "2025-01-01", "2026-01-01", NC | M, "107000.00"),
    (P, R, "2024-01-01", "2025-01-01", NC | M, "107019.18"),
    # AC5 boundaries
    (P, R, "2025-01-01", "2025-01-01", Q, "100000.00"),
    (D("12345.67"), R, "2025-01-01", "2025-01-01", Q, "12345.67"),
    (P, D("0"), "2025-01-01", "2026-01-01", Q, "100000.00"),
    (100000, R, "2025-01-01", "2026-01-01", Q, "107185.90"),
]


@pytest.mark.parametrize(("p", "r", "start", "as_of", "kwargs", "expected"), FD_CASES)
def test_fd_value_matches_hand_arithmetic(
    p: Any, r: D, start: str, as_of: str, kwargs: dict[str, Any], expected: str
) -> None:  # AC1-AC5
    day = dt.date.fromisoformat
    v = fd_value(p, r, day(start), day(as_of), **kwargs)
    assert v == D(expected)
    assert v.as_tuple().exponent == -2


def test_fd_value_direct_typed_call() -> None:  # AC6
    v: Decimal = fd_value(P, R, dt.date(2025, 1, 1), dt.date(2026, 1, 1))
    assert (type(v), v) == (Decimal, D("107185.90"))


def test_fd_value_ignores_caller_decimal_context() -> None:  # AC7
    with decimal.localcontext(prec=6, rounding=decimal.ROUND_DOWN) as c:
        v = fd_value(P, R, dt.date(2025, 1, 1), dt.date(2026, 1, 1))
        assert (c.prec, c.rounding) == (6, decimal.ROUND_DOWN)
    assert v == D("107185.90")


# overrides of the call arguments, exception type, message part
FD_ERRORS: list[tuple[dict[str, Any], type[Exception], str]] = [
    ({"principal": D(0)}, ValueError, "principal must be > 0"),
    ({"principal": D(-1)}, ValueError, "principal must be > 0"),
    ({"principal": F}, TypeError, "principal is a float"),
    ({"principal": D("NaN")}, ValueError, "principal must be finite"),
    ({"rate": D("-0.01")}, ValueError, "rate must be >= 0"),
    ({"rate": D("Infinity")}, ValueError, "rate must be finite"),
    ({"rate": D(7)}, ValueError, "rate must be a fraction below 1"),
    ({"rate": D(1)}, ValueError, "rate must be a fraction below 1"),
    ({"rate": 0.07}, TypeError, "rate is a float"),
    (LATE, ValueError, "as_of 2024-12-31 is before start 2025-01-01"),
    ({"compounding": BAD}, ValueError, CMP),
    ({"compounding": "Quarterly"}, ValueError, CMP),
    ({"compounding": BAD, "cumulative": False}, ValueError, CMP),
]


@pytest.mark.parametrize(("override", "exc", "match"), FD_ERRORS)
def test_fd_value_rejects_bad_arguments(
    override: dict[str, Any], exc: type[Exception], match: str
) -> None:  # AC8
    args: dict[str, Any] = {"principal": P, "rate": R, "start": dt.date(2025, 1, 1)}
    args |= {"as_of": dt.date(2026, 1, 1)} | override
    with pytest.raises(exc, match=match) as info:
        fd_value(**args)
    assert not isinstance(info.value, IndianFinanceError)


def test_fd_public_names() -> None:  # AC9
    assert fd.__all__ == ["COMPOUNDING_PERIODS", "fd_value"]
    names = {"monthly": 12, "quarterly": 4, "half-yearly": 2, "yearly": 1}
    assert dict(PERIODS) == names
    table: Any = PERIODS
    with pytest.raises(TypeError):
        table["daily"] = 365
    assert indianfinance.__all__ == ["__version__"]
