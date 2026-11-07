# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- **Breaking:** removed the 0.0.x API: the `indianfinance.company` class with its
  `market_info()`, `historical_data()` and `annual_report()` methods, and the
  `indianfinance.utilities` helpers `autocomplete()` and `create_dir()`. They called
  per-symbol NSE web APIs. 0.1.0 replaces them with end-of-day data from official
  whole-market files.
- Removed build artifacts (`build/`, `dist/`, `indianfinance.egg-info/`, `__pycache__/`)
  from the git repository. They are generated files and were never source.
