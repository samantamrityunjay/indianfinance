# Quickstart

[Install](install.md) the package, then get the latest NAV of a mutual fund from AMFI.
The first examples download AMFI's `NAVAll.txt` (about 1.5 MB); the last section
downloads NAV history. All of them need the network.

## One fund's latest NAV

Give the AMFI scheme code (or the ISIN):

<!-- docs-test: live -->
```python
from indianfinance.amfi import latest_nav

rec = latest_nav("135763")
print(rec.scheme_name, rec.plan, rec.option)
print(rec.date, rec.nav)
```

Sample output (the date and NAV change every day):

```text
Axis Children's Fund Direct Plan IDCW Option
2026-11-06 28.3978
```

`rec.date` is the NAV date AMFI gives, not today's date. `rec.nav` is a `Decimal`.

## By name

If you only know the fund name, add the plan and option. Each part is a case-insensitive
piece of the text in AMFI's file:

<!-- docs-test: live -->
```python
rec = latest_nav(name="Bajaj Finserv Liquid Fund", plan="Direct", option="Growth")
print(rec.amfi_code, rec.date, rec.nav)
```

```text
151833 2026-11-08 1251.5290
```

If the name matches more than one fund, `latest_nav()` raises `ValueError` and lists the
candidates. Store the AMFI code or ISIN once you know it.

## Several funds

`latest_navs(codes=[...])` takes AMFI codes and ISINs, mixed. It downloads the file once
and returns the records in file order, not in the order you gave:

<!-- docs-test: live -->
```python
from indianfinance.amfi import latest_navs

for rec in latest_navs(codes=["135763", "INF0QA701011", "INF204K01EG7"]):
    print(rec.amfi_code, rec.date, rec.nav)
```

```text
135763 2026-11-06 28.3978
109472 2026-11-06 17.0927
151833 2026-11-08 1251.5290
```

A code or ISIN without a NAV raises `SymbolNotFound`.

## Value a holding

NAVs are `Decimal`, so money stays exact:

<!-- docs-test: live -->
```python
from decimal import Decimal

rec = latest_nav("135763")
units = Decimal("152.347")
print((units * rec.nav).quantize(Decimal("0.01")))
```

```text
4326.32
```

## Value a portfolio on a date

`navs_as_of()` gives each fund's last NAV on or before a date, with the date of that NAV:

<!-- docs-test: live -->
```python
import datetime as dt
from decimal import Decimal

from indianfinance.amfi import navs_as_of

holdings = {"148921": Decimal("250"), "145486": Decimal("10.5")}
navs = navs_as_of(dt.date(2026, 11, 8), codes=list(holdings))
by_code = {rec.amfi_code: rec for rec in navs}
total = Decimal(0)
for code, units in holdings.items():
    rec = by_code[code]
    value = (units * rec.nav).quantize(Decimal("0.01"))
    total += value
    print(code, rec.date, rec.nav, value)
print("Total", total)
```

Sample output:

```text
148921 2026-11-06 22.83 5707.50
145486 2026-11-08 1502.8108 15779.51
Total 21487.01
```

- 8 Nov 2026 is a Sunday. The equity fund (`148921`) has no NAV that day, so you get
  Friday's. The overnight fund (`145486`) publishes every day, so you get Sunday's. Read
  `rec.date`.
- It is one whole-market NAV history request for the 7 days ending on the date. AMFI's
  history is about 1.2 MB per day, so expect several MB (estimate; the wait for a short
  request is not measured).
- If you store ISINs instead of AMFI codes, pass them in `codes` and match the results
  with `rec.isin` / `rec.isin_reinvestment`.

## Next steps

- [Latest NAVs](how-to/latest-navs.md): selection rules, dates and errors.
- [Find a scheme](how-to/find-a-scheme.md): search by AMC or category.
- [NAV history](how-to/nav-history.md): NAVs for past dates and the NAV on a date.
- [XIRR for a SIP](how-to/xirr-for-a-sip.md): the return of a series of investments.
- [Data timing](explanation/data-timing.md): why dates differ per scheme.
