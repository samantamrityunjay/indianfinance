# Data sources

The library downloads whole-market files only, from AMFI and NSE (NPS later). This page
lists the exact URLs, columns and quirks of each file. Checked on 2026-11-09.

- AMFI: below.
- NSE: coming in a later release.

For when each file is published, see [Data timing](explanation/data-timing.md).

## AMFI: latest NAVs

- URL: `https://portal.amfiindia.com/spages/NAVAll.txt`
- `https://www.amfiindia.com/spages/NAVAll.txt` answers `302` and redirects there.
- Size: about 1.5 MB (14 441 rows on 2026-11-09).
- Plain text, `;`-separated, UTF-8 without BOM, `\r\n` line endings.

First lines (verbatim, trimmed):

```text
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date
 
Open Ended Schemes(Children’s Fund - Childrens' Fund)
 
Axis Mutual Fund
 
135762;INF846K01WO1;-;Axis Children's Fund;Direct Plan;Growth Option;30.7694;06-Nov-2026
135765;INF846K01WP8;-;Axis Children's Fund;Direct Plan;IDCW Option;28.3442;06-Nov-2026
135763;INF846K01WS2;INF846K01WQ6;Axis Children's Fund;Direct Plan;IDCW Option;28.3978;06-Nov-2026
135761;INF846K01WN3;INF846K01WL7;Axis Children's Fund;Regular Plan;IDCW Option;24.6672;06-Nov-2026
```

| # | AMFI column | Meaning | `NavRecord` field |
|---|---|---|---|
| 1 | `Scheme Code` | AMFI scheme code | `amfi_code` |
| 2 | `ISIN Div Payout/ ISIN Growth` | ISIN for growth or dividend payout | `isin` |
| 3 | `ISIN Div Reinvestment` | ISIN for dividend reinvestment | `isin_reinvestment` |
| 4 | `Scheme Name` | Scheme name | `scheme_name` |
| 5 | `Plan` | `Direct Plan`, `Regular Plan` or empty | `plan` |
| 6 | `Option` | Free text, for example `Growth Option` | `option` |
| 7 | `Net Asset Value` | NAV in rupees | `nav` |
| 8 | `Date` | NAV date, `dd-Mmm-yyyy` | `date` |

Quirks:

- The file is a list of sections, not a table. A category line
  (`Open Ended Schemes(Debt Scheme - Banking and PSU Fund)`) and an AMC line
  (`Axis Mutual Fund`) come before the rows. Each has a line with one space before and
  after it. Skip every line that has no `;`.
- Category lines have no spaces inside the parentheses. Some contain non-ASCII
  characters (`–`, `’`).
- Scheme types seen: `Open Ended Schemes`, `Close Ended Schemes`, `Interval Fund Schemes`.
- The file ends with an empty line.
- The date is per row. Most rows have the latest business day, but liquid and overnight
  funds can have a later date, and old or closed schemes have dates back to 2008.
- A missing ISIN is `-`. Column 3 can also hold `Redeemed`, an ISIN with a trailing
  space, or a code that is not an ISIN (`HDFCNIVODG`).
- `Plan` and `Option` are empty on some rows (5 626 rows on 2026-11-09).
- NAV can be `0`, `0.0` or `0.00` (241 rows, for example segregated portfolios), and
  can have up to 7 decimals. No `N.A.` or empty NAV was seen.

## AMFI: NAV history

- URL: `https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx`
- Query parameters: `frmdt` (start) and `todt` (end), both `dd-Mmm-yyyy`, for example
  `?frmdt=05-Nov-2026&todt=06-Nov-2026`. Both days are included.
- Size: about 1.2 MB per day for the whole market. Two days were 2.4 MB.
- Same format as the latest NAVs file: `;`-separated text, UTF-8, `\r\n`.

First lines (verbatim, trimmed):

```text
Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Multi Cap Fund )


Aditya Birla Sun Life Mutual Fund
148921;Aditya Birla Sun Life Multi-Cap Fund-Direct Growth;Direct Plan;GROWTH;INF209KB1Y49;;22.77;05-Nov-2026
148921;Aditya Birla Sun Life Multi-Cap Fund-Direct Growth;Direct Plan;GROWTH;INF209KB1Y49;;22.83;06-Nov-2026
```

The 8 columns are the same as above, in a different order and with different names:

| # | AMFI column | `NavRecord` field |
|---|---|---|
| 1 | `Scheme Code` | `amfi_code` |
| 2 | `NAV Name` (full name with plan and option) | `scheme_name` |
| 3 | `Plan` | `plan` |
| 4 | `Option` | `option` |
| 5 | `ISIN Div Payout/ISIN Growth` | `isin` |
| 6 | `ISIN Div Reinvestment` | `isin_reinvestment` |
| 7 | `Net Asset Value` | `nav` |
| 8 | `Date` | `date` |

Limit and replies:

- AMFI says: "One can download historical NAV for a maximum period of 90 days at a
  time." The library uses 90 days, both ends counted.
- Measured on 2026-11-09: 90 and 91 days were still served; 159 days got a `302` to
  `https://www.amfiindia.com/net-asset-value/nav-download` (an HTML page).
- A 90-day whole-market request is about 73 MB. AMFI builds the report before it sends
  the first byte: about 2 to 2.5 minutes in our checks.
- A range with no NAVs (for example a date not published yet) gets HTTP `200` with a
  `text/html` page that says "No data found on the basis of selected parameters for
  this report". Check the `Content-Type`; real data is `text/plain`.

Quirks:

- A missing ISIN is empty here, not `-` (a few rows have `-`).
- Category lines have spaces inside the parentheses:
  `Open Ended Schemes ( Equity Scheme - Multi Cap Fund )`.
- There are two empty lines after each category line, and one before each AMC line.
  Skip every line that has no `;`.
- One row per scheme per date. Rows are grouped by category, AMC and scheme; dates go up within a scheme.
- Weekends return only schemes that publish NAVs every day: on Sunday 2026-11-08, 734
  rows (overnight, liquid and some ETFs).

## Requests

- `User-Agent: indianfinance/<version>` works on both endpoints.
- No cookies are needed. The history endpoint sets `ASP.NET_SessionId`, but requests
  without it succeed.
