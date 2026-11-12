# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added `indianfinance.__version__`, read from the installed package metadata.
- Added type hints for users: the package ships a `py.typed` marker (PEP 561).
- Added the `[pandas]` extra (`pip install "indianfinance[pandas]"`). The pandas helpers
  that use it arrive later in 0.1.0.
- Added a documentation site (Zensical): Home, Install, API reference and Changelog
  pages. Build it locally with `uv run zensical build`.
- Added tests that run every Python example in the docs pages and docstrings, so the
  examples stay correct.
- Added continuous integration (GitHub Actions): every push and pull request runs the
  linters, type checks, tests and docs build on Linux with Python 3.12 to 3.15, and
  checks the built package.
- Added `indianfinance.exceptions`: `IndianFinanceError` and its subclasses
  `NoDataForDate`, `SourceFormatError`, `SourceUnavailable` and `SymbolNotFound`, with
  typed attributes (`day`, `line`, `url`, `status_code`, `symbol`).
- Added docs pages: "Exceptions" in the API reference and "Design" (stateless, end-of-day
  data from official sources, `Decimal` for money).
- Added `indianfinance.models`: frozen, slotted dataclasses `NavRecord`, `Scheme`,
  `EodPrice` and `Cashflow`, and the `PricePoint` protocol (`.date`, `.value`). Prices,
  NAVs and amounts are `Decimal`; dates are `datetime.date`.
- Added docs: "Models" page in the API reference and a "Frozen dataclasses" section on
  the Design page.
- Added internal date helpers for the AMFI and NSE file formats (`07-Nov-2026`,
  `2026-11-07`, `20261107`). Month names use a fixed English table, so parsing does not
  depend on the computer's language settings. Bad dates raise `SourceFormatError`.
- Added internal HTTP helpers used by every download: 10 s connect / 30 s read timeouts,
  up to 3 retries with exponential backoff for timeouts, connection errors and HTTP 429 /
  5xx, `User-Agent: indianfinance/<version>` (browser-like for NSE), and downloads only
  from the official AMFI, NSE and NPS Trust hosts. Failures raise `SourceUnavailable`.
- Added an "HTTP" section to the Design docs page: timeouts, retries, User-Agent and
  passing your own `httpx.Client`.
- Added `indianfinance.returns.absolute_return()` and `indianfinance.returns.cagr()`.
  Both return `Decimal` fractions (`0.125` = 12.5 %) with 28 significant digits.
  `cagr()` takes `(date, Decimal)` tuples or `NavRecord` / `EodPrice` objects and
  counts years as days / 365. Bad arguments raise `ValueError` or `TypeError`.
- Added docs: "Returns" API reference page and the how-to guide "Absolute return and
  CAGR".
- Added `indianfinance.returns.xirr()`: the yearly rate of return of dated `Cashflow`
  amounts, like spreadsheet `XIRR` (days / 365). Returns a `float` fraction
  (`0.12` = 12 %). Bad input or no solution raises `ValueError` or `TypeError`.
- Added docs: `xirr()` on the "Returns" reference page and the how-to guide "XIRR for
  a SIP".
- Added `indianfinance.returns.rolling_returns()` and the `RollingReturn` model: the
  CAGR over every `years`-long window that ends on a point of a NAV or price series.
  A window starts on the same day `years` earlier, or the latest point before it.
  Takes the same inputs as `cagr()`; returns an empty list for a series shorter than
  the window.
- Added docs: `rolling_returns()` on the "Returns" page, `RollingReturn` on the
  "Models" page, and the how-to guide "Rolling returns".
- Added `indianfinance.fd.fd_value()`: the value of a fixed deposit on a date, rounded
  to paise. Rate as a yearly fraction (`Decimal("0.07")` = 7 %); monthly, quarterly
  (default), half-yearly or yearly compounding; days after the last whole period earn
  simple interest at actual / 365. `cumulative=False` gives principal plus interest
  paid out. TDS is ignored.
- Added docs: "FD" API reference page and the how-to guide "FD value".
- Added docs: "Data sources" page with the exact AMFI URLs, columns and quirks (NAVAll
  and NAV history, 90-day limit), and "Data timing" page (when AMFI publishes NAVs and
  what "latest" means).
- Added trimmed real AMFI files as test fixtures, and live tests that detect changes to
  the AMFI file headers (`pytest -m live`).
- Added docs: NSE capital market bhavcopy on the "Data sources" page (URL, file name,
  columns, quirks, how to tell ETFs apart, holiday and weekend replies, User-Agent and
  cookie behaviour) and on the "Data timing" page (one file per trading day, measured
  publish time, Muhurat trading).
- Added a trimmed real NSE bhavcopy as a test fixture, and a live test that detects
  changes to the bhavcopy header (`pytest -m live`).
- Added `indianfinance.amfi.latest_navs()` and `indianfinance.amfi.schemes()`: the
  latest NAV of every mutual fund scheme, and every scheme with its ISINs, AMC, scheme
  type and category, from AMFI's `NAVAll.txt`. Each NAV keeps its own date. ISINs that
  are `-`, `Redeemed` or not an ISIN become `None`; missing NAVs are skipped; a NAV of
  `0` is kept. A changed file format raises `SourceFormatError` with the line number.
- Added docs: "AMFI" API reference page and the how-to guides "Latest NAVs" and "Find
  a scheme".
- Added `indianfinance.amfi.nav_history()`: every NAV from AMFI's NAV history between
  two dates (both included), optionally for one AMFI scheme code. Ranges over 90 days
  are split into 90-day requests. A range with no NAVs raises `NoDataForDate`; an
  unknown scheme code raises `SymbolNotFound`. History downloads use a 300 s read
  timeout (`amfi.HISTORY_TIMEOUT`), because AMFI needs minutes to build a large report.
- Added docs: how-to guides "NAV history" and "Use your own HTTP client" (timeouts,
  proxies, retries, testing with `httpx.MockTransport`).

### Changed

- **Breaking:** requires Python 3.12 or newer (0.0.x allowed 3.5+).
- Changed the only runtime dependency from `requests` to `httpx`.
- Changed packaging to `pyproject.toml` with the hatchling build backend and a `src/`
  layout. The package is now released under the MIT license.
- Changed the package metadata to list Python 3.12, 3.13, 3.14 and 3.15 as supported.

### Removed

- **Breaking:** removed the 0.0.x API: the `indianfinance.company` class with its
  `market_info()`, `historical_data()` and `annual_report()` methods, and the
  `indianfinance.utilities` helpers `autocomplete()` and `create_dir()`. They called
  per-symbol NSE web APIs. 0.1.0 replaces them with end-of-day data from official
  whole-market files.
- Removed build artifacts (`build/`, `dist/`, `indianfinance.egg-info/`, `__pycache__/`)
  from the git repository. They are generated files and were never source.
- Removed `setup.py` (replaced by `pyproject.toml`).
