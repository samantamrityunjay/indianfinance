# Exceptions

Every error the library raises is a subclass of `IndianFinanceError`. Catch it to
handle all library errors in one place, or catch a subclass to handle one case.

```text
Exception
└── IndianFinanceError
    ├── NoDataForDate
    ├── SourceFormatError
    ├── SourceUnavailable
    └── SymbolNotFound
```

| Exception | Meaning | Attributes |
|---|---|---|
| `NoDataForDate` | The source has no data for that date: holiday, weekend, or not published yet. | `day` |
| `SourceFormatError` | The file format changed, or a row cannot be parsed. | `line` |
| `SourceUnavailable` | Network error, timeout or HTTP error after retries. | `url`, `status_code` |
| `SymbolNotFound` | Unknown NSE symbol or AMFI scheme code. | `symbol` |

```python
import datetime as dt

from indianfinance.exceptions import IndianFinanceError, NoDataForDate

try:
    raise NoDataForDate("no bhavcopy for 2026-11-08", day=dt.date(2026, 11, 8))
except IndianFinanceError as err:
    print(err.day)
```

```text
2026-11-08
```

::: indianfinance.exceptions
