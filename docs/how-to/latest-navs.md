# Latest NAVs

`latest_navs()` returns the latest NAV of every mutual fund scheme in AMFI's
`NAVAll.txt`, as a list of `NavRecord`. It downloads the whole file (about 1.5 MB) on
every call, so it needs the network. For one fund, `latest_nav()` returns its record.

For the NAV on a past date, see [NAV on a date](nav-history.md#nav-on-a-date).

<!-- docs-test: live -->
```python
from indianfinance.amfi import latest_nav, latest_navs

rec = latest_nav("135763")
print(rec.scheme_name, rec.plan, rec.option)
print(rec.date, rec.nav)
```

Sample output (the date and NAV change every day):

```text
Axis Children's Fund Direct Plan IDCW Option
2026-11-06 28.3978
```

## Pick funds

Pass the funds you hold. `codes=` takes AMFI scheme codes and ISINs, mixed:

<!-- docs-test: live -->
```python
for rec in latest_navs(codes=["135763", "INF0QA701011", "INF204K01EG7"]):
    print(rec.amfi_code, rec.date, rec.nav)
```

```text
135763 2026-11-06 28.3978
109472 2026-11-06 17.0927
151833 2026-11-08 1251.5290
```

Or select by name, plan and option. `latest_nav()` takes the same arguments and returns
exactly one record:

<!-- docs-test: live -->
```python
rec = latest_nav(name="Bajaj Finserv Liquid Fund", plan="Direct", option="Growth")
print(rec.amfi_code, rec.date, rec.nav)
```

```text
151833 2026-11-08 1251.5290
```

Matching rules:

- A code matches the AMFI scheme code, exactly.
- An ISIN matches either ISIN column (payout / growth or reinvestment), exactly.
- `name`, `plan` and `option` are case-insensitive parts of the text, with runs of
  spaces counted as one. `plan="direct"` matches `Direct Plan`; `option="growth"` matches
  `Growth Option`, `Growth` and `GROWTH`. Every one you give must match.
- A scheme with an empty plan or option never matches a `plan` or `option` filter.

`codes=` cannot be combined with `name`, `plan` or `option`. Results come back in file
order. It is still one whole-file download; the selection runs after it.

### When a name matches several funds

The same name, plan and option can belong to more than one AMFI code. `latest_nav()`
raises `ValueError` and lists up to 5 candidates:

<!-- docs-test: live -->
```python
try:
    latest_nav(name="Axis Children's Fund", plan="Direct", option="Growth")
except ValueError as err:
    print(err)
```

```text
2 schemes match name="Axis Children's Fund", plan='Direct', option='Growth': 135762 Axis Children's Fund (Direct Plan, Growth Option), 135764 Axis Children's Fund (Direct Plan, Growth Option); pass an AMFI code or ISIN
```

Store the AMFI code or ISIN of your fund and pass it as `codes=` or to `latest_nav()`.
With `latest_navs(name=...)` several matches are not an error: you get the list.

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
navs = latest_navs()
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

- `SymbolNotFound`: a code or ISIN in `codes=` has no NAV in the file (unknown, or its
  NAV is missing), or `latest_nav()` found no match. `.symbol` is the first one missing.
- `ValueError`: a malformed code or ISIN, an empty `name` / `plan` / `option`, `codes=`
  combined with `name` / `plan` / `option`, or several matches in `latest_nav()`. A
  single `str` as `codes` (instead of a list) raises `TypeError`. Nothing is downloaded
  for these mistakes.
- `SourceUnavailable`: the download failed after retries, or AMFI sent something that is
  not `text/plain` (for example an HTML error page). Try again later.
- `SourceFormatError`: the file does not have the documented format. `.line` is the line
  number. AMFI may have changed the file; report it.

See [Data sources](../sources.md) for the file format and the
[API reference](../reference/amfi.md) for all arguments.
