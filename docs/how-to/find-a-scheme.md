# Find a scheme

`schemes()` returns every AMFI scheme as a `Scheme`: AMFI code, name, plan, option,
ISINs, AMC, scheme type and category. It downloads the whole `NAVAll.txt` file (about
1.5 MB) on every call, so it needs the network. Call it once and filter the list.

One `Scheme` is one plan and option with its own AMFI code. A fund therefore has several
codes (for example Direct and Regular, Growth and IDCW). The code is what you use to pick
a record with `latest_nav()` or `latest_navs(codes=...)`.

<!-- docs-test: live -->
```python
from indianfinance.amfi import schemes

found = schemes()


def show(items):
    for s in items:
        print(s.amfi_code, s.scheme_name, s.plan, s.option)


# By name, case-insensitive.
show([s for s in found if "children's fund" in s.scheme_name.lower()][:3])

# By ISIN, in either ISIN column.
isin = "INF846K01WS2"
show([s for s in found if isin in (s.isin, s.isin_reinvestment)])

# By AMC and category.
show([s for s in found if s.amc == "Axis Mutual Fund" and "Children" in s.category][:3])
```

Sample output for the three queries in order, rows in file order (the scheme list changes over time):

```text
135762 Axis Children's Fund Direct Plan Growth Option
135765 Axis Children's Fund Direct Plan IDCW Option
135759 Axis Children's Fund Regular Plan Growth Option
135763 Axis Children's Fund Direct Plan IDCW Option
135762 Axis Children's Fund Direct Plan Growth Option
135765 Axis Children's Fund Direct Plan IDCW Option
135759 Axis Children's Fund Regular Plan Growth Option
```

`amc` comes from the AMC line above the row in the file. `scheme_type` and `category`
come from the category line, for example `Open Ended Schemes(Debt Scheme - Liquid Fund)`
gives `"Open Ended Schemes"` and `"Debt Scheme - Liquid Fund"`. An ISIN that is `-` or not
an ISIN is `None`.

## Then get its NAV

Pass the code you found to `latest_nav()`:

<!-- docs-test: live -->
```python
from indianfinance.amfi import latest_nav

rec = latest_nav("135763")
print(rec.amfi_code, rec.date, rec.nav)
```

```text
135763 2026-11-06 28.3978
```

If you need the NAV and not the AMC or category, `latest_navs(name=..., plan=...,
option=...)` searches by name directly (see [Latest NAVs](latest-navs.md#pick-funds)).
The same name, plan and option can match more than one code (Axis Children's Fund has two
Direct Plan / Growth Option codes), so keep the AMFI code or ISIN of the fund you pick.

Errors are the same as in [Latest NAVs](latest-navs.md#errors). See the
[API reference](../reference/amfi.md).
