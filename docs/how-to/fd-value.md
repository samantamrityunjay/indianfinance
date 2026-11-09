# FD value

`fd_value()` gives the value of a bank fixed deposit (FD) on any date, in rupees and
paise. Rates are `Decimal` fractions (`0.07` means 7 %). Everything on this page runs
offline. The numbers are example data.

## Maturity value of a 1-year FD

Rs 1,00,000 at 7 % a year, compounded quarterly (the default), for one year. Pass the
maturity date as `as_of`:

```python
import datetime as dt
from decimal import Decimal

from indianfinance.fd import fd_value

principal = Decimal("100000")
rate = Decimal("0.07")
start = dt.date(2025, 1, 1)

maturity = fd_value(principal, rate, start, dt.date(2026, 1, 1))
print(maturity)
assert maturity == Decimal("107185.90")
```

## Value today of a running FD

On 11 May 2025 the FD is 1 quarter and 40 days old. The first quarter is compounded
(`100000 x 1.0175 = 101750`). The 40 days after it earn simple interest at actual / 365:
`101750 x (1 + 0.07 x 40 / 365)`.

```python
today = dt.date(2025, 5, 11)
running = fd_value(principal, rate, start, today)
print(running)
assert running == Decimal("102530.55")
```

## FD that pays interest out

With `cumulative=False` the interest is not reinvested. The value is the principal plus
the simple interest earned so far, `principal x (1 + rate x days / 365)`:

```python
payout = fd_value(principal, rate, start, dt.date(2026, 1, 1), cumulative=False)
assert payout == Decimal("107000.00")
interest_earned = payout - principal
assert interest_earned == Decimal("7000.00")
```

## Effective yearly yield

Use `returns.cagr()` on the start and end values to get the effective yield. Quarterly
compounding at 7 % gives a little more than 7 % a year:

```python
from indianfinance.returns import cagr

effective = cagr([(start, principal), (dt.date(2026, 1, 1), maturity)])
print(f"{effective:.2%}")
assert round(effective, 4) == Decimal("0.0719")
```

## Why your bank's figure can differ

`fd_value()` rounds once, at the end. A bank's figure can differ by a few paise or
more:

- Banks round the interest each quarter.
- Banks deduct TDS; `fd_value()` ignores it.
- Some banks pay simple interest on deposits under 6 months.
- Some banks use a lower rate for monthly interest payout.
- Premature withdrawal has a penalty; `fd_value()` does not model it.
- `fd_value()` divides by 365 even in a leap year; some banks use 366.
