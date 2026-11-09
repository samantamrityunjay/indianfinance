# Data sources

The library downloads whole-market files only, from AMFI and NSE (NPS later). This page
lists the exact URLs, columns and quirks of each file. Checked on 2026-11-09.

- AMFI: below.
- NSE: [CM bhavcopy](#nse-cm-bhavcopy).

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

How the library reads it (`amfi.latest_navs()` and `amfi.schemes()`):

- Line 1 must be the header above, or `SourceFormatError` (line 1). Only lines with `;`
  are rows; they need 8 fields.
- A category line sets `scheme_type` and `category`, and resets the AMC. Any other line
  without `;` is the AMC line. A row before both raises `SourceFormatError`.
- An ISIN that is `-`, empty, `Redeemed` or not shaped like an ISIN becomes `None`.
  Trailing spaces are stripped.
- A NAV of `0` is kept as `Decimal("0")`. A NAV of `N.A.`, `-` or empty skips the row in
  `latest_navs()`; `schemes()` keeps it.
- A bad row (wrong field count, scheme code, NAV or date) raises `SourceFormatError`
  with its line number. A reply that is not `text/plain` raises `SourceUnavailable`.

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

## NSE: CM bhavcopy

The capital market (CM) bhavcopy is NSE's end-of-day file for every security traded on
the day (UDiFF format).

- URL: `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_<yyyymmdd>_F_0000.csv.zip`
- Example for Friday 2026-11-06:
  `https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261106_F_0000.csv.zip`
- In the file name, `F` means final (`P` is provisional) and `0000` is the time part,
  which is `0000` for the final file (NSE file-format sheet).
- A zip with one CSV member. The member has the same name without `.zip`.
- Size: about 200 KB zipped (208 064 bytes on 2026-11-06), 640 KB unzipped, 3 715 rows.
- ASCII, LF line endings (no `CR`), no quotes, no BOM. The file ends with a row and a
  line break.

Sample lines (verbatim, in file order, 6 of 3 715 rows):

```text
TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty,Rmks,Rsvd1,Rsvd2,Rsvd3,Rsvd4
2026-11-06,2026-11-06,CM,NSE,STK,19078,IN0020200104,SGBJUN28,GB,,,,,2.5%GOLDBONDS2028SR-III,14380.00,14380.00,14199.00,14247.52,14299.99,14421.02,,14204.04,,,214,3055333.94,87,F1,1,,,,,
2026-11-06,2026-11-06,CM,NSE,STK,15147,INE0O6N01012,AGUL,SM,,,,,A G UNIVERSAL LIMITED,64.75,64.75,64.75,64.75,64.75,61.70,,64.75,,,2000,129500.00,1,F1,2000,,,,,
2026-11-06,2026-11-06,CM,NSE,STK,100,INE885A01032,ARE&M,EQ,,,,,AMARA RAJA ENERGY MOB LTD,737.00,737.45,723.70,728.25,728.00,736.45,,728.27,,,316359,230677299.50,18501,F1,1,,,,,
2026-11-06,2026-11-06,CM,NSE,STK,766492,IN002026Y279,182D080427,TB,,,,,GOI TBILL 182D-08/04/27,97.40,97.40,97.40,97.40,97.40,96.59,,97.40,,,500,48700.00,1,F1,100,,,,,
2026-11-06,2026-11-06,CM,NSE,STK,1594,INE009A01021,INFY,EQ,,,,,INFOSYS LIMITED,1182.80,1198.80,1163.00,1181.40,1181.40,1167.40,,1181.38,,,15301109,18005126629.60,229030,F1,1,,,,,
2026-11-06,2026-11-06,CM,NSE,STK,10576,INF204KB14I2,NIFTYBEES,EQ,,,,,NIP IND ETF NIFTY BEES,278.00,284.95,276.57,284.22,284.45,279.36,,284.21,,,20193627,5682683007.94,91621,F1,1,,,,,
```

The file has 34 columns. The 11 that `EodPrice` uses, plus the other columns that have
data:

| NSE column | NSE meaning | Old bhavcopy name | `EodPrice` field |
|---|---|---|---|
| `TradDt` | Trade date, `yyyy-mm-dd` | `TIMESTAMP` | `date` |
| `BizDt` | Business date (when the session started) | - | - |
| `Sgmt` | Segment, `CM` = cash market | - | - |
| `Src` | Source, `NSE` | - | - |
| `FinInstrmTp` | Instrument type, `STK` = stock | - | - |
| `FinInstrmId` | Unique instrument id at the exchange (token number) | - | - |
| `ISIN` | ISIN of the security | `ISIN` | `isin` |
| `TckrSymb` | Instrument symbol | `SYMBOL` | `symbol` |
| `SctySrs` | Instrument series | `SERIES` | `series` |
| `FinInstrmNm` | Instrument (security) name | - | - |
| `OpnPric` | Open | `OPEN` | `open` |
| `HghPric` | High | `HIGH` | `high` |
| `LwPric` | Low | `LOW` | `low` |
| `ClsPric` | Close | `CLOSE` | `close` |
| `LastPric` | Last traded price | `LAST` | - |
| `PrvsClsgPric` | Previous close | `PREVCLOSE` | `prev_close` |
| `SttlmPric` | Settlement price | - | - |
| `TtlTradgVol` | Total traded quantity | `TOTTRDQTY` | `volume` |
| `TtlTrfVal` | Total traded value | `TOTTRDVAL` | `traded_value` |
| `TtlNbOfTxsExctd` | Total number of trades | `TOTALTRADES` | - |
| `SsnId` | Session id, `F1` = final bhavcopy of session 1 | - | - |
| `NewBrdLotQty` | Market lot size | - | - |

NSE says these 12 columns are blank for the CM segment, and they are blank in every
row: `XpryDt`, `FininstrmActlXpryDt`, `StrkPric`, `OptnTp`, `UndrlygPric`, `OpnIntrst`,
`ChngInOpnIntrst`, `Rmks`, `Rsvd1`, `Rsvd2`, `Rsvd3`, `Rsvd4`.

Quirks (2026-11-06 file):

- Every row has `FinInstrmTp` = `STK` and `SsnId` = `F1`, ETFs and bonds included. Only
  one date appears: `TradDt` = `BizDt` = `2026-11-06`.
- 58 series. Most rows: `EQ` 2 746, `SM` 384, `BE` 201, `ST` 79, `GS` 51, `GB` 43,
  `BZ` 33, `SG` 23.
- **Almost all ETFs (358 of 359 `INF` rows) are series `EQ`; the other one is `MF`.**
  Tell them apart by the ISIN prefix: `INF` is a mutual fund unit. ISIN prefixes on
  2026-11-06: `INE` 3 224, `INF` 359, `IN0` 103, other `IN` 29.
- The ISIN links an ETF's NSE price to its AMFI NAV. 358 of the 359 `INF` ISINs are in
  `NAVAll.txt`. Example: `NIFTYBEES` (`INF204KB14I2`) closed at 284.22 on NSE, and the
  AMFI NAV is 285.6510, dated 06-Nov-2026 in `NAVAll.txt` (the same day).
- `ClsPric` is not `LastPric`. They differ in 2 773 of 3 715 rows. `EodPrice.close` is
  `ClsPric`.
- Prices and `TtlTrfVal` have exactly 2 decimals. `TtlTradgVol` is a whole number.
  No row had zero volume or an empty or zero price.
- Symbols can contain `&` and `-`: `ARE&M`, `BAJAJ-AUTO`. 19 of them on this day.
- All ISINs match `IN` plus 10 letters or digits.

No file:

- A holiday (Friday 2026-10-02) and a Saturday (2026-11-07) get HTTP `404` with a
  `text/html` page of 3 425 bytes. It is not a redirect and not an empty zip.
- Muhurat trading on Sunday 2026-11-08 has a full file: 3 550 rows, `TradDt` =
  `2026-11-08`, `PrvsClsgPric` is the 06-Nov close. NSE says in circular
  NSE/CMTR/71775 that Muhurat trading is on that Sunday.
- NSE circular NSE/CMTR/71775 (2025-12-12) lists the 2026 CM trading holidays, for
  example Monday 2026-01-26, Friday 2026-10-02 and Tuesday 2026-11-10.

NSE sources:

- File nomenclature and column definitions: NSE "UDiFF trade and Bhavcopy file
  formats" sheet, linked from
  `https://www.nseindia.com/static/resources/forms-formats-members`.
- Old and new column names: `https://nsearchives.nseindia.com/content/new_bhavcopy_format_readme.xlsx`.
- Holidays: `https://nsearchives.nseindia.com/content/circulars/CMTR71775.pdf`.

## Requests

AMFI:

- `User-Agent: indianfinance/<version>` works on both endpoints.
- No cookies are needed. The history endpoint sets `ASP.NET_SessionId`, but requests
  without it succeed.

NSE (measured on 2026-11-09):

- `nsearchives.nseindia.com` served the bhavcopy to `indianfinance/<version>` and to a
  browser `User-Agent`. Both got the same file.
- No cookies and no warm-up request are needed. `nsearchives` sets no cookies.
- `www.nseindia.com` pages set the Akamai cookies `_abck` and `bm_sz`. The bhavcopy does
  not need them.
