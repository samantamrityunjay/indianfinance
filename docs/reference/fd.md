# FD

Value of a bank fixed deposit (FD) on a date.

- `rate` is a yearly fraction: `Decimal("0.07")` means 7 %.
- `compounding` is `"monthly"` (12 periods a year), `"quarterly"` (4, the default),
  `"half-yearly"` (2) or `"yearly"` (1). See `COMPOUNDING_PERIODS`.
- Whole compounding periods are compounded. The days after the last whole period earn
  simple interest at actual / 365.
- `cumulative=False` means interest is paid out: the value is the principal plus the
  simple interest earned so far.
- The result is a `Decimal` in rupees, rounded to paise (half up). Your own `decimal`
  context is ignored and left unchanged.
- TDS is ignored. There is no maturity date: pass the maturity date as `as_of`. See
  [FD value](../how-to/fd-value.md).

```python
import datetime as dt
from decimal import Decimal

from indianfinance.fd import fd_value

start = dt.date(2025, 1, 1)
matured = fd_value(Decimal("100000"), Decimal("0.07"), start, dt.date(2026, 1, 1))
assert matured == Decimal("107185.90")
running = fd_value(Decimal("100000"), Decimal("0.07"), start, dt.date(2025, 5, 11))
assert running == Decimal("102530.55")
```

::: indianfinance.fd
