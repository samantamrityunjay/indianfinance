"""Result types returned by the library: frozen, slotted dataclasses.

Prices, NAVs and amounts are `Decimal`. Dates are `datetime.date`. Import `datetime`
as `dt` and write `dt.date`, because three models have a field named `date`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

__all__ = ["Cashflow", "EodPrice", "NavRecord", "PricePoint", "Scheme"]


class PricePoint(Protocol):
    """Anything with a date and a value, such as a NAV or a closing price.

    `NavRecord` and `EodPrice` match this protocol. Analytics functions accept any
    object that has these two read-only attributes.
    """

    @property
    def date(self) -> dt.date:
        """The date of the value."""
        ...

    @property
    def value(self) -> Decimal:
        """The price or NAV on that date."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class NavRecord:
    """One mutual fund NAV on one date, as published by AMFI.

    Attributes:
        amfi_code: AMFI scheme code, for example `"135763"`. Text, not a number.
        scheme_name: Scheme name as the source gives it.
        plan: Plan, for example `"Direct Plan"`. `None` if the source is blank.
        option: Option, for example `"IDCW Option"`. `None` if the source is blank.
        isin: ISIN from the "ISIN Div Payout/ ISIN Growth" column. `None` if the
            source has `-` or nothing.
        isin_reinvestment: ISIN from the "ISIN Div Reinvestment" column. `None` if
            the source has `-` or nothing.
        date: The NAV date, as the source gives it.
        nav: The "Net Asset Value" column.

    Example:
        >>> import datetime as dt
        >>> from decimal import Decimal
        >>> from indianfinance.models import NavRecord
        >>> rec = NavRecord(
        ...     amfi_code="135763",
        ...     scheme_name="Axis Children's Fund",
        ...     plan="Direct Plan",
        ...     option="IDCW Option",
        ...     isin="INF846K01WS2",
        ...     isin_reinvestment="INF846K01WQ6",
        ...     date=dt.date(2026, 11, 6),
        ...     nav=Decimal("28.3978"),
        ... )
        >>> rec.value
        Decimal('28.3978')
    """

    amfi_code: str
    scheme_name: str
    plan: str | None
    option: str | None
    isin: str | None
    isin_reinvestment: str | None
    date: dt.date
    nav: Decimal

    @property
    def value(self) -> Decimal:
        """The NAV (`nav`), so a `NavRecord` is a `PricePoint`."""
        return self.nav


@dataclass(frozen=True, slots=True, kw_only=True)
class Scheme:
    """One AMFI mutual fund scheme (one plan and option, one AMFI code).

    Attributes:
        amfi_code: AMFI scheme code, for example `"135763"`.
        scheme_name: Scheme name as the source gives it.
        plan: Plan, for example `"Direct Plan"`. `None` if blank.
        option: Option, for example `"IDCW Option"`. `None` if blank.
        isin: ISIN from the "ISIN Div Payout/ ISIN Growth" column, or `None`.
        isin_reinvestment: ISIN from the "ISIN Div Reinvestment" column, or `None`.
        amc: Fund house, for example `"Axis Mutual Fund"`.
        scheme_type: Scheme type, for example `"Open Ended Schemes"`.
        category: Scheme category, for example `"Debt Scheme - Gilt Fund"`.
    """

    amfi_code: str
    scheme_name: str
    plan: str | None
    option: str | None
    isin: str | None
    isin_reinvestment: str | None
    amc: str
    scheme_type: str
    category: str


@dataclass(frozen=True, slots=True, kw_only=True)
class EodPrice:
    """One end-of-day price row from the NSE capital market bhavcopy.

    Attributes:
        symbol: Ticker symbol (`TckrSymb`), for example `"INFY"`.
        series: Series (`SctySrs`), for example `"EQ"`.
        isin: ISIN (`ISIN`).
        date: Trade date (`TradDt`).
        open: Opening price (`OpnPric`).
        high: Highest price (`HghPric`).
        low: Lowest price (`LwPric`).
        close: Official closing price (`ClsPric`, not the last traded price).
        prev_close: Previous day's close (`PrvsClsgPric`).
        volume: Number of shares traded (`TtlTradgVol`).
        traded_value: Value traded in rupees (`TtlTrfVal`).
    """

    symbol: str
    series: str
    isin: str
    date: dt.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    prev_close: Decimal
    volume: int
    traded_value: Decimal

    @property
    def value(self) -> Decimal:
        """The closing price (`close`), so an `EodPrice` is a `PricePoint`."""
        return self.close


@dataclass(frozen=True, slots=True)
class Cashflow:
    """One dated amount of money, for XIRR.

    Sign convention (investor's view): negative means money you pay in (a purchase or
    SIP instalment); positive means money you get back (a redemption, a dividend or the
    current value).

    Attributes:
        date: The date of the cash movement.
        amount: The amount, negative for money paid in, positive for money received.
    """

    date: dt.date
    amount: Decimal
