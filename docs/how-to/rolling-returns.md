# Rolling returns

A rolling return is the CAGR over a window of fixed length that ends on each date of a
series: "every 1-year CAGR". It shows how steady a fund has been, not just how it did
between two dates. `rolling_returns()` returns one `RollingReturn` per window. Rates are
`Decimal` fractions (`0.1` means 10 %). Everything on this page runs offline.

## Rolling 1-year returns

The NAVs below are placeholder data for an example fund:

```python
import datetime as dt
from decimal import Decimal

from indianfinance.models import NavRecord
from indianfinance.returns import rolling_returns


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


records = [
    nav(dt.date(2020, 1, 2), "100"),
    nav(dt.date(2021, 1, 1), "110"),
    nav(dt.date(2022, 1, 1), "121"),
    nav(dt.date(2022, 7, 1), "110"),
    nav(dt.date(2023, 1, 1), "133.1"),
]
rows = rolling_returns(records, 1)
for r in rows:
    print(f"{r.start} -> {r.end}: {r.cagr:.2%}")
assert len(rows) == 3
assert [round(r.cagr, 4) for r in rows] == [
    Decimal("0.1000"),
    Decimal("0.0000"),
    Decimal("0.1000"),
]
```

The first two NAVs get no row: there is no NAV one year before them.

## When the start day has no NAV

A window starts on the same day one year earlier. If the series has no point on that day,
the latest point before it is used, and `start` shows the real date. The 2022-07-01 row
above starts on 2021-01-01, not 2021-07-01, so it covers 546 days. To keep only windows
close to the full length, filter on the real number of days:

```python
full = [r for r in rows if (r.end - r.start).days <= 365 * 1 + 7]
assert len(full) == 2
```

## Worst, best and average

Plain Python is enough:

```python
rates = [r.cagr for r in full]
assert min(rates) == Decimal("0.1")
assert max(rates) == Decimal("0.1")
every = [r.cagr for r in rows]
assert round(sum(every) / len(every), 4) == Decimal("0.0667")
```

## Things to know

- The window start is the same calendar day `years` earlier. 29 February becomes
  28 February.
- The CAGR counts days / 365, like `cagr()`, and is not rounded.
- `years` is a whole number of years, 1 or more. Other values raise `TypeError` or
  `ValueError`.
- A series shorter than the window gives an empty list, not an error.
- Rows are sorted by end date, oldest first.
- A zero value used as a window start raises `ValueError`.
