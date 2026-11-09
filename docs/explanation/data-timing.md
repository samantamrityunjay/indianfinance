# Data timing

When the data is published, and what "latest" means. Exact files and columns are on
the [Data sources](../sources.md) page.

## AMFI NAVs

- Scheme information documents on the AMFI portal say fund houses upload NAVs to the
  AMFI site by 11:00 p.m. on every business day.
- Schemes that invest abroad upload by 10:00 a.m. on the next business day.
- On Monday 2026-11-09 `NAVAll.txt` was last modified at 12:59 IST and still had
  `06-Nov-2026` (Friday) for most rows.

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
- AMFI serves at most 90 days per request. The library will split longer ranges into
  several requests (M4).
- A date with no NAVs yet gets a "No data found" page, not an empty file.
