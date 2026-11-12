# NAV history

`nav_history()` returns every NAV AMFI has between two dates (both included), as a list
of `NavRecord`. It downloads AMFI's whole-market NAV history, so it needs the network.
Pass `amfi_code` to keep one scheme. Find the code with [Find a scheme](find-a-scheme.md).

<!-- docs-test: live -->
```python
import datetime as dt

from indianfinance.amfi import nav_history

navs = nav_history(dt.date(2026, 11, 5), dt.date(2026, 11, 6), amfi_code="148921")
for rec in navs:
    print(rec.date, rec.nav)
```

Sample output:

```text
2026-11-05 22.77
2026-11-06 22.83
```

## Long ranges

- AMFI serves at most 90 days per request. A longer range is split into 90-day pieces,
  downloaded one after another.
- Each piece of 90 days is about 73 MB, and AMFI needs 2 to 2.5 minutes to build it
  before it sends the first byte. A year is 5 pieces, so about 10 to 13 minutes
  (estimate from measured waits of 113-145 s per piece, not counting download time).
- The default client has a 300 s read timeout (`indianfinance.amfi.HISTORY_TIMEOUT`).
  If you pass your own client, give it `HISTORY_TIMEOUT` or longer. See
  [Use your own HTTP client](custom-http-client.md).

## Several schemes

`amfi_code` takes one code. Each call downloads the whole market, so do not call once
per scheme. Call once without `amfi_code` and filter with a set of codes:

<!-- docs-test: live -->
```python
wanted = {"148921", "151835"}
navs = nav_history(dt.date(2026, 11, 5), dt.date(2026, 11, 6))
for rec in [r for r in navs if r.amfi_code in wanted]:
    print(rec.amfi_code, rec.date, rec.nav)
```

Sample output:

```text
148921 2026-11-05 22.77
148921 2026-11-06 22.83
151835 2026-11-05 1034.6939
151835 2026-11-06 1034.6939
```

## NAV on a date

`navs_as_of(day)` returns each scheme's last NAV on or before `day`, as a list of
`NavRecord`. Each record keeps its own `date`. It takes the same `codes=` / `name=` /
`plan=` / `option=` selection as `latest_navs()`.

<!-- docs-test: live -->
```python
from indianfinance.amfi import navs_as_of

navs = navs_as_of(
    dt.date(2026, 11, 8),
    name="Aditya Birla Sun Life Overnight Fund",
    plan="Direct",
    option="Growth",
)
for rec in navs:
    print(rec.amfi_code, rec.date, rec.nav)
```

Sample output:

```text
145486 2026-11-08 1502.8108
```

- The window is `lookback_days` days ending on `day` (default 7, 1 to 90). It is one
  request. Size: AMFI's history is about 1.2 MB per day (T-015 measurement), so at most
  about 8 MB for 7 days (estimate: about 1.2 MB per weekday from T-015; weekend days
  have far fewer rows).
- A scheme with no NAV in the window is left out. A requested code with none raises
  `SymbolNotFound`: raise `lookback_days`.
- Rows with a missing NAV are skipped, so an earlier NAV in the window is used.
- Results are in AMFI's file order, not in `codes` order.
- There is no "today" check. `nav_history()` itself never moves to another date.

### Names in NAV history

History names are AMFI's long "NAV Name", with plan and option inside, and their
spelling is free. For example AMFI writes `ADITYA BIRLA SUNLIFE OVERNIGHT FUND-REGULAR
PLAN-GROWTH` (no space in "SUNLIFE"), so this finds nothing:

<!-- docs-test: live -->
```python
print(
    len(
        navs_as_of(
            dt.date(2026, 11, 8),
            name="Sun Life Overnight",
            plan="Regular",
            option="Growth",
        )
    )
)
```

Sample output:

```text
0
```

Use `name=` to explore. For a portfolio, use `codes=`.

## Order

Records come piece by piece. Inside a piece they are in AMFI's order: grouped by scheme,
with dates going up. The list is not sorted and not de-duplicated. Sort it yourself if
you need another order. With `amfi_code`, the dates go up.

## Weekends, holidays and no data

- On weekends and holidays AMFI has NAVs only for schemes that publish every day
  (overnight, liquid and some ETFs).
- AMFI answers a range with no NAVs with a "No data found" page. A 90-day piece with no
  data inside a longer range is skipped. If the whole range has none, `nav_history()`
  raises `NoDataForDate`.
- The library does not check "today": future dates are sent to AMFI as asked.
- Rows with a missing NAV are skipped. A NAV of `0` is kept.

## Errors

- `ValueError`: `start` is after `end`, or `amfi_code` is not digits. Nothing is sent.
- `TypeError` / `ValueError` (`navs_as_of()`): `day` is not a `datetime.date`, or
  `lookback_days` is not an `int` from 1 to 90. Nothing is sent.
- `NoDataForDate`: AMFI has no NAVs in the whole range. `.day` is `start` (for
  `navs_as_of()`, `day`).
- `SymbolNotFound`: `amfi_code` has no NAV in the range. For `navs_as_of()`, a code or
  ISIN in `codes` has no NAV in the window.
- `SourceUnavailable`: the download failed after one retry, the reply was not
  `text/plain`, or AMFI redirected the request (the range is over its limit).
- `SourceFormatError`: the file does not have the documented format. `.line` is the
  line number.

## Memory

- A 90-day whole-market piece is about 73 MB, plus its text and many records. Memory use
  is not measured; plan for a large amount.
- Pass `amfi_code` to keep only one scheme: other rows are dropped before records are
  built.

See also [Data sources](../sources.md), [Data timing](../explanation/data-timing.md)
and the [AMFI API reference](../reference/amfi.md).
