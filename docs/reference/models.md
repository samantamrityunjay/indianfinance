# Models

Every data function returns these frozen, slotted dataclasses. Prices, NAVs and money
are `Decimal`, and dates are `datetime.date`. Create `Decimal` values from strings
(`Decimal("28.3978")`), not from floats.

| Model | What it is | Will be returned by |
|---|---|---|
| `NavRecord` | One mutual fund NAV on one date | `amfi.latest_navs()`, `amfi.nav_history()` |
| `Scheme` | One AMFI scheme with its fund house and category | `amfi.schemes()` |
| `EodPrice` | One end-of-day price row from the NSE bhavcopy | `nse.bhavcopy()`, `nse.bhavcopy_range()` |
| `Cashflow` | One dated amount | input to `returns.xirr()` |
| `RollingReturn` | The CAGR over one rolling window | `returns.rolling_returns()` |

Three models have a field named `date`. Use `import datetime as dt` and write
`dt.date(...)`.

## PricePoint

`NavRecord` and `EodPrice` match the `PricePoint` protocol: a `date` and a `value`.
`NavRecord.value` is `nav`, and `EodPrice.value` is `close`. `value` is a property, not
a field, so it is not in `dataclasses.asdict()`.

## Cashflow signs

Negative means money you paid in. Positive means money you received, or the current
value.

```python
import dataclasses
import datetime as dt
from decimal import Decimal

from indianfinance.models import Cashflow, NavRecord

rec = NavRecord(
    amfi_code="135763",
    scheme_name="Axis Children's Fund",
    plan="Direct Plan",
    option="IDCW Option",
    isin="INF846K01WS2",
    isin_reinvestment=None,
    date=dt.date(2026, 11, 6),
    nav=Decimal("28.3978"),
)
paid = Cashflow(dt.date(2026, 1, 5), Decimal("-5000"))
print(rec.value, rec.date)
try:
    rec.nav = Decimal("1")
except dataclasses.FrozenInstanceError as err:
    print("frozen:", err)
```

```text
28.3978 2026-11-06
frozen: cannot assign to field 'nav'
```

::: indianfinance.models
