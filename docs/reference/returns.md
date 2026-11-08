# Returns

Return calculations on NAVs, prices and amounts.

- Results are `Decimal` fractions: `0.125` means 12.5 %. Format with `f"{r:.2%}"`.
- Results have 28 significant digits and are not rounded. Your own `decimal` context
  is ignored and left unchanged.
- `cagr()` takes `(date, Decimal)` tuples, or `NavRecord`, `EodPrice` or any
  `PricePoint` objects.
- Years are counted as days / 365.

```python
import datetime as dt
from decimal import Decimal

from indianfinance.returns import absolute_return, cagr

gain = absolute_return(Decimal("10000"), Decimal("11250"))
assert gain == Decimal("0.125")
r = cagr([(dt.date(2021, 1, 1), Decimal("100")), (dt.date(2023, 1, 1), Decimal("121"))])
assert f"{r:.2%}" == "10.00%"
```

::: indianfinance.returns
