# XIRR for a SIP

`xirr()` in `indianfinance.returns` gives the yearly rate of return of dated cashflows,
like the `XIRR` function in a spreadsheet. Use it when money goes in several times, for
example a monthly SIP. The result is a `float` fraction: `0.12` means 12 % a year.
Everything on this page runs offline.

## Signs: paid in is negative

Pass `Cashflow` objects. Money you pay in (SIP instalments, purchases) is **negative**.
Money you receive (redemptions, dividends, the current value) is **positive**.

## A monthly SIP

`5000` paid on the 5th of each month in 2025, and the holding is worth `64000` on
2026-01-05:

```python
import datetime as dt
from decimal import Decimal

from indianfinance.models import Cashflow
from indianfinance.returns import xirr

sip = [Cashflow(dt.date(2025, month, 5), Decimal("-5000")) for month in range(1, 13)]
sip.append(Cashflow(dt.date(2026, 1, 5), Decimal("64000")))

r = xirr(sip)
print(f"{r:.2%}")
assert f"{r:.2%}" == "12.48%"
assert round(r, 4) == 0.1248
```

## Current value from units and NAV

The final cashflow is what your units are worth today. Multiply the units by the latest
NAV with `Decimal` and round to paise:

```python
units = Decimal("1234.567")
latest_nav = Decimal("51.8412")
current_value = (units * latest_nav).quantize(Decimal("0.01"))
assert current_value == Decimal("64001.43")

sip[-1] = Cashflow(dt.date(2026, 1, 5), current_value)
assert round(xirr(sip), 4) == 0.1249
```

## A redemption in the middle

Money you take out before the end is a positive cashflow on its own date. Here `10000`
is redeemed on 2025-07-05 and the rest is worth `53500` at the end:

```python
with_redemption = sip[:-1] + [
    Cashflow(dt.date(2025, 7, 5), Decimal("10000")),
    Cashflow(dt.date(2026, 1, 5), Decimal("53500")),
]
assert round(xirr(with_redemption), 4) == 0.129
```

## Things to know

- Years are counted as days / 365 from the earliest cashflow, like spreadsheet `XIRR`
  and `cagr()`.
- The result is a `float`, not rounded. Round it for display, for example
  `f"{r:.2%}"`.
- The order of the cashflows does not matter, and several cashflows on one date are
  fine.
- `ValueError` is raised for fewer than 2 cashflows, no negative or no positive amount,
  all cashflows on one date, an invalid `guess` (not finite, or <= -1), or no rate
  found (the fallback search covers -99.99 % to 100,000,000 %). A `float` amount
  raises `TypeError`.
- If the cashflows change sign several times, more than one rate can be valid. `xirr()`
  returns one of them, found from `guess` (default `0.1`). Pass `guess=` to look for a
  different one.
- Use `cagr()` for one lump sum (two values), and `xirr()` for many cashflows.
