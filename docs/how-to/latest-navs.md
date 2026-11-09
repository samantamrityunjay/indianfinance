# Latest NAVs

`latest_navs()` returns the latest NAV of every mutual fund scheme in AMFI's
`NAVAll.txt`, as a list of `NavRecord`. It downloads the whole file (about 1.5 MB) on
every call, so it needs the network. Call it once and filter the list.

<!-- docs-test: live -->
```python
from indianfinance.amfi import latest_navs

navs = latest_navs()
by_code = {rec.amfi_code: rec for rec in navs}
rec = by_code["135763"]
print(rec.scheme_name, rec.plan, rec.option)
print(rec.date, rec.nav)
```

Sample output (the date and NAV change every day):

```text
Axis Children's Fund Direct Plan IDCW Option
2026-11-06 28.3978
```

## Dates differ per scheme

Each record has its own `date`, the NAV date AMFI gives. Never assume one date for the
whole list:

- Most schemes have the last business day.
- Liquid and overnight funds can have a later date, for example a Sunday.
- Old or closed schemes can have dates years back (the 2026-11-06 file has dates back to
  2008).

If you need one day, filter on `rec.date`:

<!-- docs-test: live -->
```python
latest = max(rec.date for rec in navs)
on_latest = [rec for rec in navs if rec.date == latest]
print(latest, len(on_latest), "of", len(navs))
```

## What the library cleans

- An ISIN that is `-`, empty, `Redeemed` or not an ISIN (for example `HDFCNIVODG`)
  becomes `None`. Trailing spaces are stripped.
- A NAV of `0` is kept as `Decimal("0")` (for example segregated portfolios).
- A row with a missing NAV (`N.A.`, `-` or empty) is skipped. `schemes()` keeps it.
- Rows come back in file order, not sorted.

## Errors

- `SourceUnavailable`: the download failed after retries, or AMFI sent something that is
  not `text/plain` (for example an HTML error page). Try again later.
- `SourceFormatError`: the file does not have the documented format. `.line` is the line
  number. AMFI may have changed the file; report it.

See [Data sources](../sources.md) for the file format and the
[API reference](../reference/amfi.md) for all arguments.
