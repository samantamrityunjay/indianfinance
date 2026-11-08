"""Return calculations: absolute return, CAGR and XIRR.

Results are ``Decimal`` fractions (``0.125`` means 12.5 %), computed with 28
significant digits and not rounded. Round them yourself for display. ``xirr()`` is
solved numerically and returns a ``float`` fraction.
"""

from __future__ import annotations

import datetime as dt
import decimal
import math
from collections.abc import Iterable
from decimal import Decimal
from typing import Final

from indianfinance.models import Cashflow, PricePoint

__all__ = ["DAYS_PER_YEAR", "absolute_return", "cagr", "xirr"]

DAYS_PER_YEAR: Final[int] = 365
"""Days in a year for annualising (actual/365: a leap day counts as an extra day)."""

# Every calculation runs inside `decimal.localcontext(_CONTEXT)`, so the caller's
# context (precision, rounding, traps) never changes the result and is left unchanged.
_CONTEXT: Final[decimal.Context] = decimal.Context(
    prec=28, rounding=decimal.ROUND_HALF_EVEN
)

_XIRR_TOLERANCE: Final[float] = 1e-10  # stop when a step changes the rate by <= this
_NEWTON_MAX_STEPS: Final[int] = 100  # same limit as spreadsheet XIRR
_BISECT_MAX_STEPS: Final[int] = 200
_RATE_LOW: Final[float] = -0.9999  # -99.99 %
_RATE_HIGH_START: Final[float] = 1.0  # 100 %, widened x10 up to _RATE_HIGH_MAX
_RATE_HIGH_MAX: Final[float] = 1e6  # 100,000,000 %


def absolute_return(start_value: Decimal, end_value: Decimal) -> Decimal:
    """Return the gain or loss from ``start_value`` to ``end_value`` as a fraction.

    ``(end_value - start_value) / start_value``. ``Decimal("0.125")`` means +12.5 %,
    ``Decimal("-0.2")`` means -20 %. Not annualised; dates play no part.

    Args:
        start_value: Value at the start (a NAV, price or amount). Must be > 0.
        end_value: Value at the end. Must be >= 0.

    Returns:
        The return as a ``Decimal`` fraction, 28 significant digits, not rounded.

    Raises:
        TypeError: If a value is a ``float`` (pass ``Decimal("...")`` instead).
        ValueError: If a value is not finite (NaN, Infinity), ``start_value <= 0``
            or ``end_value < 0``.

    Example:
        >>> from decimal import Decimal
        >>> from indianfinance.returns import absolute_return
        >>> absolute_return(Decimal("10000"), Decimal("11250"))
        Decimal('0.125')
    """
    with decimal.localcontext(_CONTEXT):
        start = _to_decimal(start_value, "start_value")
        end = _to_decimal(end_value, "end_value")
        if start <= 0:
            raise ValueError(f"start_value must be > 0, got {start}")
        if end < 0:
            raise ValueError(f"end_value must be >= 0, got {end}")
        return (end - start) / start


def cagr(series: Iterable[PricePoint | tuple[dt.date, Decimal]]) -> Decimal:
    """Return the compound annual growth rate of a series, as a fraction.

    Uses the earliest and the latest point by date (input order does not matter;
    points in between are checked but not used):
    ``(last_value / first_value) ** (365 / days) - 1``, where ``days`` is the number
    of calendar days between the two dates (actual/365).

    Args:
        series: At least 2 points, each a ``(date, value)`` tuple or an object with
            ``.date`` and ``.value`` (``NavRecord``, ``EodPrice``, any
            ``PricePoint``). Any iterable, including a generator. Dates must be
            unique. Values must be >= 0, and the earliest value must be > 0.

    Returns:
        The CAGR as a ``Decimal`` fraction, 28 significant digits, not rounded.
        Periods under one year are annualised too.

    Raises:
        TypeError: If a value is a ``float``.
        ValueError: If there are fewer than 2 points, two points share a date, a
            value is not finite or is < 0, or the earliest value is 0.

    Example:
        >>> import datetime as dt
        >>> from decimal import Decimal
        >>> from indianfinance.returns import cagr
        >>> r = cagr(
        ...     [
        ...         (dt.date(2021, 1, 1), Decimal("100")),
        ...         (dt.date(2023, 1, 1), Decimal("121")),
        ...     ]
        ... )
        >>> round(r, 4)
        Decimal('0.1000')
        >>> f"{r:.2%}"
        '10.00%'
    """
    with decimal.localcontext(_CONTEXT):
        pts = _points(series)
        if len(pts) < 2:
            raise ValueError(f"series needs at least 2 points, got {len(pts)}")
        (first_date, first_value), (last_date, last_value) = pts[0], pts[-1]
        if first_value == 0:
            raise ValueError(
                f"value on {first_date.isoformat()} (the earliest point) must be > 0"
            )
        days = (last_date - first_date).days
        years_inverse = Decimal(DAYS_PER_YEAR) / Decimal(days)
        return (last_value / first_value) ** years_inverse - 1


def xirr(cashflows: Iterable[Cashflow], *, guess: float = 0.1) -> float:
    """Return the yearly rate of return of dated cashflows (like spreadsheet XIRR).

    Finds the rate ``r`` where the cashflows' present value is zero:
    ``sum(amount / (1 + r) ** (days / 365)) == 0``, with ``days`` counted from the
    earliest cashflow (actual/365). Use negative amounts for money paid in (SIP
    instalments, purchases) and positive amounts for money received (redemptions,
    dividends, the current value).

    Args:
        cashflows: At least 2 ``Cashflow`` objects, in any order. Several on the same
            date are allowed. Any iterable, including a generator.
        guess: Starting rate for Newton's method, a fraction > -1. Change it only if
            the cashflows change sign several times and you want a different one of
            several valid rates.

    Returns:
        The rate as a ``float`` fraction (``0.12`` means 12 % a year), not rounded.
        Always > -1.

    Raises:
        TypeError: If an amount is a ``float``.
        ValueError: If there are fewer than 2 cashflows, no negative or no positive
            amount, all cashflows are on one date, an amount is not finite,
            ``guess`` is not finite or is <= -1, or no rate solves it. The
            bisection fallback searches -99.99 % to 100,000,000 %; a rate found by
            Newton's method is returned as is and can be outside that range (for
            example -1 then 2 a day later gives about 7.5e109).

    Example:
        >>> import datetime as dt
        >>> from decimal import Decimal
        >>> from indianfinance.models import Cashflow
        >>> from indianfinance.returns import xirr
        >>> r = xirr(
        ...     [
        ...         Cashflow(dt.date(2021, 1, 1), Decimal("-100")),
        ...         Cashflow(dt.date(2023, 1, 1), Decimal("121")),
        ...     ]
        ... )
        >>> round(r, 6)
        0.1
        >>> f"{r:.2%}"
        '10.00%'
    """
    flows = list(cashflows)
    amounts = [
        float(_to_decimal(cf.amount, f"amount on {cf.date.isoformat()}"))
        for cf in flows
    ]
    if len(flows) < 2:
        raise ValueError(f"xirr needs at least 2 cashflows, got {len(flows)}")
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        raise ValueError("xirr needs at least one negative and one positive amount")
    first = min(cf.date for cf in flows)
    if all(cf.date == first for cf in flows):
        raise ValueError(
            f"all cashflows are on {first.isoformat()}; xirr needs at least 2 dates"
        )
    if not math.isfinite(guess) or guess <= -1:
        raise ValueError(f"guess must be a finite number > -1, got {guess}")
    times = [(cf.date - first).days / DAYS_PER_YEAR for cf in flows]
    return _solve(times, amounts, float(guess))


def _present_value(rate: float, times: list[float], amounts: list[float]) -> float:
    """Return the present value of ``amounts`` at ``rate``."""
    value = sum(a * math.pow(1 + rate, -t) for t, a in zip(times, amounts, strict=True))
    if not math.isfinite(value):
        raise OverflowError("present value is not finite")
    return value


def _solve(times: list[float], amounts: list[float], guess: float) -> float:
    """Find the rate: Newton's method from ``guess``, then bisection as a fallback."""
    rate = guess
    for _ in range(_NEWTON_MAX_STEPS):
        try:
            value = _present_value(rate, times, amounts)
            slope = sum(
                -t * a * math.pow(1 + rate, -t - 1)
                for t, a in zip(times, amounts, strict=True)
            )
            if not (math.isfinite(value) and math.isfinite(slope)):
                break
            new_rate = rate - value / slope
        except (OverflowError, ZeroDivisionError):
            break
        if not math.isfinite(new_rate) or new_rate <= -1:
            break
        if abs(new_rate - rate) <= _XIRR_TOLERANCE:
            return new_rate
        rate = new_rate
    return _bisect(times, amounts)


def _bisect(times: list[float], amounts: list[float]) -> float:
    """Find a rate between -99.99 % and 100,000,000 % by bracketing and halving."""
    message = "xirr found no rate between -99.99 % and 100,000,000 %"
    low, high = _RATE_LOW, _RATE_HIGH_START
    try:
        f_low = _present_value(low, times, amounts)
        f_high = _present_value(high, times, amounts)
        while math.copysign(1, f_low) == math.copysign(1, f_high) and (
            high < _RATE_HIGH_MAX
        ):
            high *= 10
            f_high = _present_value(high, times, amounts)
        if f_low == 0:
            return low
        if f_high == 0:
            return high
        if math.copysign(1, f_low) == math.copysign(1, f_high):
            raise ValueError(message)
        for _ in range(_BISECT_MAX_STEPS):
            if high - low <= _XIRR_TOLERANCE:
                break
            mid = (low + high) / 2
            f_mid = _present_value(mid, times, amounts)
            if math.copysign(1, f_mid) == math.copysign(1, f_low):
                low, f_low = mid, f_mid
            else:
                high = mid
    except OverflowError:
        raise ValueError(message) from None
    return (low + high) / 2


def _to_decimal(value: Decimal | int | float, name: str) -> Decimal:
    """Return ``value`` as a finite ``Decimal``; ``name`` is used in error messages.

    ``float`` -> ``TypeError``; ``int`` / ``Decimal`` -> ``Decimal(value)``;
    NaN / Infinity -> ``ValueError``.
    """
    if isinstance(value, float):
        raise TypeError(
            f"{name} is a float; pass a Decimal, for example Decimal('12.34')"
        )
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError(f"{name} must be finite, got {result}")
    return result


def _points(
    series: Iterable[PricePoint | tuple[dt.date, Decimal]],
) -> list[tuple[dt.date, Decimal]]:
    """Read a series into ``(date, Decimal)`` pairs sorted by date (T-013 reuses it).

    Tuples are unpacked as ``(date, value)``; anything else is read via ``.date``
    and ``.value``. Each value goes through ``_to_decimal`` and must be >= 0.
    Duplicate dates raise ``ValueError``. Does not check the count.
    """
    seen: dict[dt.date, Decimal] = {}
    for item in series:
        day, raw = item if isinstance(item, tuple) else (item.date, item.value)
        value = _to_decimal(raw, f"value on {day.isoformat()}")
        if value < 0:
            raise ValueError(f"value on {day.isoformat()} must be >= 0, got {value}")
        if day in seen:
            raise ValueError(f"duplicate date {day.isoformat()} in series")
        seen[day] = value
    return sorted(seen.items())
