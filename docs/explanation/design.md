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

## Frozen dataclasses

Results are frozen, slotted dataclasses (see [Models](../reference/models.md)).

- You cannot change them. Use `dataclasses.replace()` to get a changed copy.
- They compare by value and can be set members or dict keys.
- They have no ordering. Sort with `key=`, for example `key=lambda r: r.date`.
- Slots keep memory use small for files with thousands of rows.

```python
import dataclasses
import datetime as dt
from decimal import Decimal

from indianfinance.models import Cashflow

paid = Cashflow(dt.date(2026, 1, 5), Decimal("-5000"))
bigger = dataclasses.replace(paid, amount=Decimal("-6000"))
print(paid)
print(bigger)
```

```text
Cashflow(date=datetime.date(2026, 1, 5), amount=Decimal('-5000'))
Cashflow(date=datetime.date(2026, 1, 5), amount=Decimal('-6000'))
```

## Dates

- Every record carries the date the source gives. The library never guesses "today".
- Date ranges are inclusive: both `start` and `end` are included.
- Three models have a field named `date`, so the examples use `import datetime as dt`
  and write `dt.date(...)`.

## HTTP

- Downloads use `https://` only, from the official AMFI, NSE and NPS Trust hosts
  (`amfiindia.com`, `www.amfiindia.com`, `portal.amfiindia.com`, `nseindia.com`,
  `www.nseindia.com`, `nsearchives.nseindia.com`, `npstrust.org.in`,
  `www.npstrust.org.in`). A redirect to any other host is refused.
- Timeouts: 10 s to connect, 30 s to read; NAV history 300 s to read
  (`amfi.HISTORY_TIMEOUT`).
- Retries: timeouts, connection errors and HTTP 429, 500, 502, 503 and 504 are retried
  up to 3 times, after 1 s, 2 s and 4 s. A `Retry-After` header in whole seconds is
  honoured up to 30 s. A longer `Retry-After` stops retrying at once with
  `SourceUnavailable`. NAV history: 1 retry.
- Other errors, for example HTTP 403 and 404, fail at once.
- A failure raises `SourceUnavailable` with `url` and `status_code`.
- The `User-Agent` is `indianfinance/<version>`. NSE hosts get a browser-like one
  (decision D-001). This is a precaution: on 2026-11-09 `nsearchives.nseindia.com`
  also served the bhavcopy to `indianfinance/<version>`.

### Your own client

Data functions (from M4 on) take `client: httpx.Client | None = None`.

- Your client's timeout, headers, proxies and transport are used as they are.
- Your `User-Agent` is kept. On 2026-11-09 NSE also accepted a
  non-browser `User-Agent`, but this may change.
- The library never closes your client.
- Retries and the allowed-host check still apply.
- More: [Use your own HTTP client](../how-to/custom-http-client.md).

```python
import httpx

with httpx.Client(
    timeout=httpx.Timeout(60.0, connect=10.0),
    headers={"User-Agent": "myapp/1.0 (me@example.com)"},
) as client:
    print(client.timeout)
```

```text
Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)
```

## Errors

The library raises typed exceptions, all subclasses of `IndianFinanceError`. See
[Exceptions](../reference/exceptions.md). When the cause is another error (for example
an `httpx` timeout), it is kept as `__cause__`.
