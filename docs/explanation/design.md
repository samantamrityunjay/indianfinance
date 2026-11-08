# Design

The rules the library follows. Data functions arrive in later 0.1.0 milestones; these
rules apply to all of them.

## Stateless

- No database and no cache.
- No files are written, unless you pass a destination path or ask for bytes.
- Every call downloads what it needs and returns plain data.

## End-of-day data from official sources

- Sources: AMFI, NSE and NPS Trust.
- The library downloads whole-market files only, never one symbol at a time.
- No live quotes, no Yahoo, no broker APIs.

## Decimal for money

Prices, NAVs and money are `Decimal`, not `float`. Binary floats cannot store most
decimal fractions exactly, so sums drift:

```python
from decimal import Decimal

print(0.1 + 0.2 == 0.3)
print(Decimal("0.1") + Decimal("0.2") == Decimal("0.3"))
```

```text
False
True
```

The one exception is XIRR, which is solved numerically and returns a `float`.

## Dates

- Every record carries the date the source gives. The library never guesses "today".
- Date ranges are inclusive: both `start` and `end` are included.

## Errors

The library raises typed exceptions, all subclasses of `IndianFinanceError`. See
[Exceptions](../reference/exceptions.md). When the cause is another error (for example
an `httpx` timeout), it is kept as `__cause__`.
