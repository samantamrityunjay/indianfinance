"""Fixed deposit (FD) value.

The rate is a yearly fraction (``Decimal("0.07")`` is 7 %). Whole compounding periods
are compounded; the days after the last whole period earn simple interest at
actual / 365. The result is rounded to paise. TDS is ignored.
"""

from __future__ import annotations

import calendar
import datetime as dt
import decimal
from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import Final, Literal

from indianfinance.returns import _CONTEXT, DAYS_PER_YEAR, _to_decimal

__all__ = ["COMPOUNDING_PERIODS", "fd_value"]

COMPOUNDING_PERIODS: Final[Mapping[str, int]] = MappingProxyType(
    {"monthly": 12, "quarterly": 4, "half-yearly": 2, "yearly": 1}
)
"""Compounding periods per year, by the names `fd_value()` accepts."""

_PAISA: Final[Decimal] = Decimal("0.01")


def fd_value(
    principal: Decimal,
    rate: Decimal,
    start: dt.date,
    as_of: dt.date,
    *,
    compounding: Literal["monthly", "quarterly", "half-yearly", "yearly"] = "quarterly",
    cumulative: bool = True,
) -> Decimal:
    """Return the value of a fixed deposit on ``as_of``, rounded to paise.

    Cumulative (interest reinvested): every whole compounding period since
    ``start`` is compounded at ``rate / periods_per_year``; the days after the last
    whole period earn simple interest at ``rate x days / 365`` on that amount.
    Periods are calendar months from ``start`` (3 for quarterly); a start on the
    31st ends a period on the last day of shorter months.

    Non-cumulative (interest paid out): ``principal x (1 + rate x days / 365)``, the
    principal plus all interest earned up to ``as_of``; ``compounding`` is ignored.

    TDS is ignored. There is no maturity date: pass the maturity date as ``as_of``
    for the maturity value; later dates keep growing at the same rate.

    Args:
        principal: Amount deposited, in rupees. Must be > 0.
        rate: Yearly interest rate as a fraction, ``Decimal("0.07")`` for 7 %.
            Must be >= 0 and < 1.
        start: Date the deposit was made.
        as_of: Date to value it on. Must be on or after ``start``.
        compounding: ``"monthly"``, ``"quarterly"`` (banks' usual choice),
            ``"half-yearly"`` or ``"yearly"``.
        cumulative: ``True`` if interest is reinvested, ``False`` if it is paid
            out.

    Returns:
        The value in rupees as a ``Decimal`` with 2 decimal places, rounded half
        up.

    Raises:
        TypeError: If ``principal`` or ``rate`` is a ``float``.
        ValueError: If ``principal`` or ``rate`` is not finite, ``principal <= 0``,
            ``rate < 0`` or ``rate >= 1``, ``as_of`` is before ``start``, or
            ``compounding`` is not one of the four names.

    Example:
        >>> import datetime as dt
        >>> from decimal import Decimal
        >>> from indianfinance.fd import fd_value
        >>> fd_value(
        ...     Decimal("100000"),
        ...     Decimal("0.07"),
        ...     dt.date(2025, 1, 1),
        ...     dt.date(2026, 1, 1),
        ... )
        Decimal('107185.90')
    """
    p = _to_decimal(principal, "principal")
    r = _to_decimal(rate, "rate")
    if p <= 0:
        raise ValueError(f"principal must be > 0, got {p}")
    if r < 0:
        raise ValueError(f"rate must be >= 0, got {r}")
    if r >= 1:
        raise ValueError(
            f"rate must be a fraction below 1 (7 % is Decimal('0.07')), got {r}"
        )
    if as_of < start:
        raise ValueError(
            f"as_of {as_of.isoformat()} is before start {start.isoformat()}"
        )
    if compounding not in COMPOUNDING_PERIODS:
        raise ValueError(
            "compounding must be one of 'monthly', 'quarterly', 'half-yearly', "
            f"'yearly', got {compounding!r}"
        )
    with decimal.localcontext(_CONTEXT):
        if not cumulative:
            days = (as_of - start).days
            value = p * (1 + r * Decimal(days) / Decimal(DAYS_PER_YEAR))
        else:
            m = COMPOUNDING_PERIODS[compounding]
            step = 12 // m
            n = 0
            while _add_months(start, (n + 1) * step) <= as_of:
                n += 1
            days = (as_of - _add_months(start, n * step)).days
            value = (
                p * (1 + r / m) ** n * (1 + r * Decimal(days) / Decimal(DAYS_PER_YEAR))
            )
        return value.quantize(_PAISA, rounding=decimal.ROUND_HALF_UP)


def _add_months(day: dt.date, months: int) -> dt.date:
    """Return ``day`` plus ``months`` calendar months.

    The day is clamped to the month's last day (31 Jan + 1 month = 28 or 29 Feb).
    """
    total = day.month - 1 + months
    year, month = day.year + total // 12, total % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return dt.date(year, month, min(day.day, last))
