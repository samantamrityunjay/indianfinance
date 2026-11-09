# AMFI

Mutual fund NAVs and schemes from AMFI's `NAVAll.txt`.

- Each call downloads the whole file (about 1.5 MB). There is no cache.
- Every `NavRecord` has its own NAV date, as AMFI gives it. Dates differ per scheme; see
  [Data timing](../explanation/data-timing.md).
- A missing NAV (`N.A.`, `-` or empty) skips the row in `latest_navs()`; `schemes()`
  keeps it. A NAV of `0` is kept as `Decimal("0")`.
- An ISIN that is `-`, empty, `Redeemed` or not an ISIN becomes `None`.
- A download that fails, or a reply that is not `text/plain`, raises `SourceUnavailable`.
  A file that does not have the documented format raises `SourceFormatError` with the
  line number.
- Guides: [Latest NAVs](../how-to/latest-navs.md) and
  [Find a scheme](../how-to/find-a-scheme.md).

::: indianfinance.amfi
