# Use your own HTTP client

Every function that downloads takes `client: httpx.Client | None = None`. Pass your own
client to set a proxy, a `User-Agent` with your contact, longer timeouts, to reuse one
client for several calls, or to test your code without the network.

## Rules

- The library uses your client as it is: timeout, headers, proxies and transport.
- It never closes your client.
- Your timeout wins. The library does not raise it for NAV history, so use
  `HISTORY_TIMEOUT` (10 s to connect, 300 s to read) or longer.
- Your `User-Agent` is kept.
- Retries and the allowed-host check still apply.

```python
import httpx

from indianfinance.amfi import HISTORY_TIMEOUT

client = httpx.Client(
    timeout=HISTORY_TIMEOUT,
    headers={"User-Agent": "myapp/1.0 (me@example.com)"},
)
print(client.timeout)
```

```text
Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0)
```

A proxy, and one client for two calls (this needs the network):

<!-- docs-test: skip -->
```python
import datetime as dt

import httpx

from indianfinance.amfi import HISTORY_TIMEOUT, latest_navs, nav_history

with httpx.Client(proxy="http://proxy.example:8080", timeout=HISTORY_TIMEOUT) as client:
    navs = latest_navs(client=client)
    history = nav_history(dt.date(2026, 11, 5), dt.date(2026, 11, 6), client=client)
```

## Retries

- `NAVAll.txt` and other downloads: 4 tries (the first one and 3 retries).
- NAV history: 2 tries (the first one and 1 retry), because a timed-out try can take up
  to 5 minutes.
- Retried: timeouts, connection errors and HTTP 429, 500, 502, 503 and 504. Other errors
  fail at once with `SourceUnavailable`.
- Retries are not configurable.

## Testing your code without the network

`httpx.MockTransport` answers requests from a function, so no request leaves your
machine:

```python
from indianfinance.amfi import latest_navs

NAVALL = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;"
    "Plan;Option;Net Asset Value;Date\n"
    "Open Ended Schemes(Equity Scheme - Large Cap Fund)\n"
    "Example Mutual Fund\n"
    "100001;INF000A01011;;Example Large Cap Fund - Direct Growth;"
    "Direct Plan;Growth;12.3456;06-Nov-2026\n"
)

transport = httpx.MockTransport(lambda request: httpx.Response(200, text=NAVALL))
navs = latest_navs(client=httpx.Client(transport=transport))
assert navs[0].amfi_code == "100001"
print(navs[0].amfi_code, navs[0].nav)
```

```text
100001 12.3456
```
