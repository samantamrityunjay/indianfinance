# Data timing

When the data is published, and what "latest" means. Exact files and columns are on
the [Data sources](../sources.md) page.

## AMFI NAVs

- Scheme information documents on the AMFI portal say fund houses upload NAVs to the
  AMFI site by 11:00 p.m. on every business day.
- Schemes that invest abroad upload by 10:00 a.m. on the next business day.
- On Monday 2026-11-09 `NAVAll.txt` was last modified at 12:59 IST and still had
  `06-Nov-2026` (Friday) for most rows.

## NSE bhavcopy

- NSE publishes one final bhavcopy per trading day. Measured
  `Last-Modified` of the file: 16:33 IST on Friday 2026-11-06, and 16:38 IST on Sunday
  2026-11-08 (Muhurat trading). NSE does not state a publish time on the pages we read.
- Weekends and holidays have no file: NSE answers `404`. Special sessions are the
  exception. Muhurat trading on Sunday 2026-11-08 has a full file.
- The 2026 holiday list is in NSE circular NSE/CMTR/71775 of 2025-12-12. The library
  has no holiday calendar.
- Every row has a trade date (`TradDt`). The library returns that date, never "today".

Details and URLs: [Data sources](../sources.md#nse-cm-bhavcopy).

## What "latest" means

`NAVAll.txt` holds one NAV per scheme: the newest one AMFI has for it. So the date
differs from row to row:

- Most rows have the last business day (`06-Nov-2026`).
- Liquid and overnight funds, and some ETFs, have a later date, for example Sunday
  `08-Nov-2026`.
- Old or closed schemes have stale dates, some back to 2008.

"Latest" in this library means the date on each record. It is never "today". Read
`NavRecord.date` instead of assuming one date for the whole file.

## NAV history

- History returns every NAV date in the range, one row per scheme per date.
- Liquid and overnight funds and some ETFs also have NAVs on weekends. Other schemes
  have none.
- AMFI serves at most 90 days per request. `nav_history()` splits longer ranges into
  90-day requests.
- `navs_as_of(day)` returns the last NAV on or before `day`; for most schemes on a
  weekend or holiday that is an earlier date.
- A date with no NAVs yet gets a "No data found" page, not an empty file;
  `nav_history()` raises `NoDataForDate` if the whole range has none.
