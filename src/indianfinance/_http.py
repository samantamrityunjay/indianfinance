"""HTTP helpers: client, timeouts, retries, User-Agent and allowed hosts (internal)."""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Final, NoReturn

import httpx

from indianfinance import __version__
from indianfinance.exceptions import SourceUnavailable

logger: Final = logging.getLogger(__name__)

USER_AGENT: Final[str] = f"indianfinance/{__version__}"
"""User-Agent sent to every host except NSE."""

BROWSER_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
)
"""Browser-like User-Agent sent to NSE hosts, which block bot-like ones (D-001)."""

ALLOWED_HOSTS: Final[frozenset[str]] = frozenset(
    {
        "amfiindia.com",
        "www.amfiindia.com",
        "portal.amfiindia.com",
        "nseindia.com",
        "www.nseindia.com",
        "nsearchives.nseindia.com",
        "npstrust.org.in",
        "www.npstrust.org.in",
    }
)
"""Hosts the library may download from (AGENTS.md rule 4). Exact match, lowercase."""

NSE_HOSTS: Final[frozenset[str]] = frozenset(
    {"nseindia.com", "www.nseindia.com", "nsearchives.nseindia.com"}
)
"""Hosts that get BROWSER_USER_AGENT."""

DEFAULT_TIMEOUT: Final[httpx.Timeout] = httpx.Timeout(30.0, connect=10.0)
"""10 s to connect; 30 s for each read, write and pool wait."""

MAX_ATTEMPTS: Final[int] = 4
"""Tries per request: the first one plus 3 retries."""

BACKOFF_BASE: Final[float] = 1.0
"""Wait before the first retry, in seconds. Doubles on each retry."""

BACKOFF_CAP: Final[float] = 30.0
"""Longest wait between tries, in seconds (backoff and Retry-After)."""

RETRY_STATUSES: Final[frozenset[int]] = frozenset({429, 500, 502, 503, 504})
"""HTTP statuses that are retried. Every other non-2xx status fails at once."""

MAX_REDIRECTS: Final[int] = 5
"""Most redirects followed for one try."""

_RETRY_ERRORS: Final = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)


def make_client(*, timeout: httpx.Timeout = DEFAULT_TIMEOUT) -> httpx.Client:
    """Create the client the library uses when the caller passes none.

    The client has ``timeout``, ``User-Agent: USER_AGENT`` and
    ``follow_redirects=False`` (``get`` follows redirects itself, checking each host).

    Args:
        timeout: Timeouts for every request.

    Returns:
        A new, open ``httpx.Client``. The caller must close it.
    """
    return httpx.Client(
        timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=False
    )


@contextlib.contextmanager
def open_client(client: httpx.Client | None = None) -> Iterator[httpx.Client]:
    """Yield the caller's client, or a new one that is closed on exit.

    Public data functions use it as ``with open_client(client) as c: ...``.

    Args:
        client: The caller's client. Used as it is (its timeout, headers, proxies and
            transport) and never closed here.

    Yields:
        ``client`` if given, else a client from ``make_client()``, closed when the
        ``with`` block ends, also on error.
    """
    if client is not None:
        yield client
        return
    with make_client() as owned:
        yield owned


def _allowed(url: httpx.URL) -> bool:
    """Return True for an ``https`` URL on an allowed host."""
    return url.scheme == "https" and url.host in ALLOWED_HOSTS


def _fail(
    url: object, status: int | None, reason: str, attempts: int, cause: Exception | None
) -> NoReturn:
    """Raise ``SourceUnavailable`` for a failed GET, chaining ``cause``."""
    message = f"GET {url} failed after {attempts} attempt(s): {reason}"
    raise SourceUnavailable(message, url=str(url), status_code=status) from cause


def _set_user_agent(client: httpx.Client, request: httpx.Request) -> None:
    """Set the User-Agent by host, unless the caller's client has its own."""
    current = client.headers.get("User-Agent", "")
    if current.startswith("python-httpx/") or current == USER_AGENT:
        browser = request.url.host in NSE_HOSTS
        request.headers["User-Agent"] = BROWSER_USER_AGENT if browser else USER_AGENT


def _send(
    client: httpx.Client, url: str, params: Mapping[str, str] | None, attempts: int
) -> httpx.Response:
    """Send one try, following redirects by hand. Fails for bad redirects."""
    request = client.build_request("GET", url, params=params)
    hops = 0
    while True:
        _set_user_agent(client, request)
        logger.debug("GET %s", request.url)
        response = client.send(request, follow_redirects=False)
        following = response.next_request
        if not response.is_redirect or following is None:
            return response
        hops += 1
        if hops > MAX_REDIRECTS:
            _fail(
                request.url, response.status_code, "too many redirects", attempts, None
            )
        if not _allowed(following.url):
            reason = f"redirect to a host that is not allowed: {following.url}"
            _fail(request.url, response.status_code, reason, attempts, None)
        request = following


def _retry_delay(response: httpx.Response | None, retry_number: int) -> float | None:
    """Seconds to wait, or None when the server asks for longer than the cap."""
    if response is not None and response.status_code in (429, 503):
        value = response.headers.get("Retry-After", "")
        if value.isascii() and value.isdigit():
            seconds = float(value)
            return seconds if seconds <= BACKOFF_CAP else None
    return min(BACKOFF_CAP, BACKOFF_BASE * float(2 ** (retry_number - 1)))


def get(
    client: httpx.Client,
    url: str,
    *,
    params: Mapping[str, str] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """GET ``url`` with retries and return the successful response.

    Timeouts, connection errors, ``RemoteProtocolError`` and HTTP 429 / 500 / 502 /
    503 / 504 are retried with backoff of 1 s, 2 s, 4 s (or a whole-second
    ``Retry-After`` of at most 30 s). Every other error fails at once. Redirects are
    followed here, and every target must be an allowed ``https`` host.

    Args:
        client: The client to send with (from ``open_client``).
        url: An ``https://`` URL on one of ``ALLOWED_HOSTS``.
        params: Query parameters, added to ``url``.
        max_attempts: Most tries, including the first. Default ``MAX_ATTEMPTS`` (4).
        sleep: Called with the wait in seconds before each retry. Tests pass a fake.

    Returns:
        The 2xx response, body already read (``.content`` / ``.text`` work after the
        client is closed).

    Raises:
        ValueError: If ``url`` is not ``https`` or its host is not in
            ``ALLOWED_HOSTS``, or ``max_attempts < 1``. Caller mistake, nothing sent.
        SourceUnavailable: If the request fails for good. ``.url`` is the URL of the
            failing request, ``.status_code`` its HTTP status or None. If an ``httpx``
            error happens on a redirect hop, ``.url`` is the original URL.
    """
    if not _allowed(httpx.URL(url)):
        raise ValueError(f"URL not allowed: {url!r}")
    if max_attempts < 1:
        raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")
    for attempt in range(1, max_attempts + 1):
        response: httpx.Response | None = None
        status: int | None = None
        cause: Exception
        try:
            response = _send(client, url, params, attempt)
            if response.is_success:
                return response
            status = response.status_code
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as err:
                cause = err
            reason = f"HTTP {status}"
            retryable = status in RETRY_STATUSES
        except _RETRY_ERRORS as err:
            cause, reason, retryable = err, f"{type(err).__name__}: {err}", True
        except httpx.HTTPError as err:
            cause, reason, retryable = err, f"{type(err).__name__}: {err}", False
        failing_url = response.request.url if response is not None else url
        delay = _retry_delay(response, attempt)
        if not retryable or delay is None or attempt == max_attempts:
            _fail(failing_url, status, reason, attempt, cause)
        logger.info(
            "GET %s: %s; retry %d of %d in %.1f s",
            failing_url,
            reason,
            attempt,
            max_attempts - 1,
            delay,
        )
        sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
