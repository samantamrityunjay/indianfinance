# Absolute return and CAGR

Two functions in `indianfinance.returns` measure growth. `absolute_return()` gives the
total gain or loss. `cagr()` gives the yearly compound rate. Both return a `Decimal`
fraction, so `0.125` means 12.5 %. Everything on this page runs offline.

## Absolute return of a holding

You bought at NAV `28.3978` and the NAV is now `31.2045`:

```python
from decimal import Decimal

from indianfinance.returns import absolute_return

gain = absolute_return(Decimal("28.3978"), Decimal("31.2045"))
print(f"{gain:.2%}")
assert f"{gain:.2%}" == "9.88%"
```

## CAGR from NAV records

`cagr()` uses the earliest and the latest point of the series. Pass `NavRecord`
or `EodPrice` objects as they come from `amfi` and `nse`:

```python
import datetime as dt

from indianfinance.models import NavRecord
from indianfinance.returns import cagr


def nav(day: dt.date, value: str) -> NavRecord:
    return NavRecord(
        amfi_code="100001",
        scheme_name="Example Equity Fund - Direct Growth",
        plan="Direct Plan",
        option="Growth Option",
        isin="INF000000001",
        isin_reinvestment=None,
        date=day,
        nav=Decimal(value),
    )


records = [nav(dt.date(2023, 11, 6), "20"), nav(dt.date(2026, 11, 6), "28")]
rate = cagr(records)
print(round(rate, 4))
assert round(rate, 4) == Decimal("0.1186")
```

## CAGR from tuples

Use `(date, Decimal)` tuples when you have your own data. Two values are a list of two
points:

```python
points = [
    (dt.date(2021, 1, 1), Decimal("100")),
    (dt.date(2023, 1, 1), Decimal("121")),
]
assert round(cagr(points), 4) == Decimal("0.1000")
```

## Things to know

- Years are counted as days / 365. A leap day counts as an extra day, so
  2024-01-01 to 2025-01-01 is 366 / 365 years.
- A period under one year is annualised too, which exaggerates the figure. Use
  `absolute_return()` for short periods.
- Values must be `Decimal` (or `int`). A `float` raises `TypeError`.
- The input order does not matter. Points between the first and the last are checked
  but not used.
- Results have 28 significant digits and are not rounded. Round them for display, for
  example `f"{rate:.2%}"`.
- `ValueError` is raised for fewer than 2 points, duplicate dates, a negative or
  non-finite value, a zero earliest value in `cagr()`, or `start_value <= 0` /
  `end_value < 0` in `absolute_return()`.
