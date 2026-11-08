"""Return calculations: absolute return and CAGR.

Results are ``Decimal`` fractions (``0.125`` means 12.5 %), computed with 28
significant digits and not rounded. Round them yourself for display.
"""

from __future__ import annotations

import datetime as dt
import decimal
from collections.abc import Iterable
from decimal import Decimal
from typing import Final

from indianfinance.models import PricePoint

__all__ = ["DAYS_PER_YEAR", "absolute_return", "cagr"]

DAYS_PER_YEAR: Final[int] = 365
"""Days in a year for annualising (actual/365: a leap day counts as an extra day)."""

# Every calculation runs inside `decimal.localcontext(_CONTEXT)`, so the caller's
# context (precision, rounding, traps) never changes the result and is left unchanged.
_CONTEXT: Final[decimal.Context] = decimal.Context(
    prec=28, rounding=decimal.ROUND_HALF_EVEN
)


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
