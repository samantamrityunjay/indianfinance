# AMFI

Mutual fund NAVs, schemes and NAV history from AMFI's whole-market files.

- Each call downloads the whole file (about 1.5 MB). There is no cache.
- Every `NavRecord` has its own NAV date, as AMFI gives it. Dates differ per scheme; see
  [Data timing](../explanation/data-timing.md).
- A missing NAV (`N.A.`, `-` or empty) skips the row in `latest_navs()` and `latest_nav()`;
  `schemes()` keeps it. A NAV of `0` is kept as `Decimal("0")`.
- An ISIN that is `-`, empty, `Redeemed` or not an ISIN becomes `None`.
- A download that fails, or a reply that is not `text/plain`, raises `SourceUnavailable`.
  A file that does not have the documented format raises `SourceFormatError` with the
  line number.
- `nav_history()` splits ranges into 90-day requests, each about 73 MB and 2 to 2.5
  minutes. The default client uses `HISTORY_TIMEOUT` (300 s read). A range with no NAVs
  raises `NoDataForDate`; an unknown `amfi_code` raises `SymbolNotFound`.
- `latest_navs()` and `latest_nav()` select by AMFI code or ISIN, or by name + plan +
  option (case-insensitive parts); one whole-file download either way.
- An unknown code or ISIN raises `SymbolNotFound`; `latest_nav()` with several matches
  raises `ValueError`.
- `navs_as_of(day)` returns each scheme's last NAV on or before `day` from one NAV
  history request (`lookback_days`, default 7); records keep their own date; same
  selection as `latest_navs()`.
- Guides: [Quickstart](../quickstart.md), [Latest NAVs](../how-to/latest-navs.md),
  [Find a scheme](../how-to/find-a-scheme.md), [NAV history](../how-to/nav-history.md)
  and [Use your own HTTP client](../how-to/custom-http-client.md).

::: indianfinance.amfi
