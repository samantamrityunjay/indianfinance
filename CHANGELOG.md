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
