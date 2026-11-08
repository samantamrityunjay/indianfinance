"""Tests for indianfinance._http (httpx.MockTransport only, no network)."""

import contextlib
import logging
from typing import Any

import httpx
import pytest

import indianfinance._http as h
from indianfinance import __version__
from indianfinance.exceptions import SourceUnavailable

UA, BUA, M = h.USER_AGENT, h.BROWSER_USER_AGENT, "myapp/1.0"
AMFI, NSE = "https://www.amfiindia.com/a", "https://nsearchives.nseindia.com/a"
T, EX = httpx.ConnectTimeout("t"), "https://example.com/"
FOLLOW = {"cl": {"follow_redirects": True}}


def _run(*replies: Any, url: str = AMFI, cl: Any = None, **kw: Any) -> Any:
    seen: list[httpx.Request] = []
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        reply = replies[len(seen) - 1]
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(reply) if isinstance(reply, int) else reply

    c = httpx.Client(transport=httpx.MockTransport(handler), **(cl or {}))
    try:
        out: httpx.Response | SourceUnavailable = h.get(
            c, url, sleep=delays.append, **kw
        )
    except SourceUnavailable as err:
        out = err
    finally:
        c.close()
    return out, seen, delays


def _r(status: int, **headers: str) -> httpx.Response:
    return httpx.Response(
        status, headers={k.replace("_", "-"): v for k, v in headers.items()}
    )


def test_make_client_sets_timeout_user_agent_and_no_redirects() -> None:  # AC1
    with h.make_client() as c:
        assert c.timeout == httpx.Timeout(30.0, connect=10.0)
        assert c.headers["User-Agent"] == UA == f"indianfinance/{__version__}"
        assert c.follow_redirects is False
    with h.make_client(timeout=httpx.Timeout(5.0)) as c2:
        assert c2.timeout == httpx.Timeout(5.0)


def test_open_client_closes_only_its_own_client() -> None:  # AC2
    mine = httpx.Client(headers={"X": "1"}, timeout=httpx.Timeout(7.0))
    for boom in (False, True):
        with contextlib.suppress(RuntimeError), h.open_client() as owned:
            if boom:
                raise RuntimeError
        with contextlib.suppress(RuntimeError), h.open_client(mine) as c:
            if boom:
                raise RuntimeError
        assert owned.is_closed
        assert (c is mine, mine.is_closed) == (True, False)
        assert (mine.headers["X"], mine.timeout) == ("1", httpx.Timeout(7.0))


def test_get_returns_response_on_success() -> None:  # AC3, AC12 (body read after close)
    r, seen, delays = _run(httpx.Response(200, content=b"abc"), params={"d": "1-Nov"})
    assert (r.content, r.text, len(seen), delays) == (b"abc", "abc", 1, [])
    assert seen[0].url.params["d"] == "1-Nov"


@pytest.mark.parametrize(
    ("url", "ua", "want"),
    [(AMFI, None, UA), (NSE, None, BUA), (AMFI, M, M), (NSE, M, M)],
)
def test_get_sets_user_agent_by_host_unless_caller_set_one(
    url: str, ua: str | None, want: str
) -> None:  # AC4
    _, seen, _ = _run(200, url=url, cl={"headers": {"User-Agent": ua}} if ua else None)
    assert seen[0].headers["User-Agent"] == want
    assert BUA.startswith("Mozilla/5.0 ")


BAD = "http://www.amfiindia.com/ https://example.com/ ftp://www.amfiindia.com/"
BAD += " https://evil-amfiindia.com/ https://amfiindia.com.evil.com/"


@pytest.mark.parametrize(("url", "n"), [(u, 4) for u in BAD.split()] + [(AMFI, 0)])
def test_get_rejects_url_outside_allowed_hosts(url: str, n: int) -> None:  # AC5
    with pytest.raises(ValueError):  # noqa: PT011  (a sent request would raise IndexError)
        _run(url=url, max_attempts=n)


@pytest.mark.parametrize("host", ["WWW.AMFIINDIA.COM", *sorted(h.ALLOWED_HOSTS)])
def test_get_accepts_every_allowed_host(host: str) -> None:  # AC5
    assert _run(200, url=f"https://{host}/x")[0].status_code == 200


# (replies, sleeps, requests_sent)
OK = [
    ((503, 502, 200), [1.0, 2.0], 3),  # AC6
    ((T, httpx.ReadError("r"), 200), [1.0, 2.0], 3),
    ((httpx.RemoteProtocolError("p"), 200), [1.0], 2),
    ((_r(429, Retry_After="7"), 200), [7.0], 2),  # AC9
    ((_r(429, Retry_After="Wed, 21 Oct 2026 07:28:00 GMT"), 200), [1.0], 2),
    ((_r(301, Location="https://portal.amfiindia.com/y"), 200), [], 2),  # AC10
    ((_r(302, Location="https://nsearchives.nseindia.com/z"), 200), [], 2),
]


@pytest.mark.parametrize("case", OK)
def test_get_retries_and_redirects_then_succeeds(case: Any) -> None:
    replies, sleeps, sent = case
    r, seen, delays = _run(*replies)
    assert r.status_code == 200
    assert (len(seen), delays) == (sent, sleeps)
    last = seen[-1]  # AC10: the User-Agent follows the host of the redirect hop
    assert last.headers["User-Agent"] == (BUA if "nseindia" in last.url.host else UA)


# (replies, kwargs, status_code, requests_sent, sleeps, text_in_message)
FAIL = [
    ((500,) * 4, {}, 500, 4, [1.0, 2.0, 4.0], "4 attempt(s): HTTP 500"),  # AC7
    ((T,) * 4, {}, None, 4, [1.0, 2.0, 4.0], "ConnectTimeout"),
    ((503,), {"max_attempts": 1}, 503, 1, [], "HTTP 503"),
    *[((s, 200), {}, s, 1, [], f"HTTP {s}") for s in (400, 403, 404, 410, 501)],  # AC8
    ((httpx.UnsupportedProtocol("x"), 200), {}, None, 1, [], "UnsupportedProtocol"),
    ((httpx.ProxyError("x"), 200), {}, None, 1, [], "ProxyError"),
    ((_r(503, Retry_After="120"), 200), {}, 503, 1, [], "HTTP 503"),  # AC9
    ((_r(302, Location=EX),), {}, 302, 1, [], "example.com"),  # AC10
    ((_r(302, Location=EX),), FOLLOW, 302, 1, [], "example.com"),
    ((_r(302, Location=AMFI),) * 7, {}, 302, 6, [], "too many redirects"),
]


@pytest.mark.parametrize("case", FAIL)
def test_get_raises_source_unavailable_when_it_must_fail(case: Any) -> None:
    replies, kw, status, sent, sleeps, text = case
    err, seen, delays = _run(*replies, **kw)
    assert isinstance(err, SourceUnavailable)
    assert (err.status_code, len(seen), delays) == (status, sent, sleeps)
    assert text in str(err)
    if isinstance(replies[0], Exception):  # AC7, AC8
        assert err.__cause__ is replies[0]
    else:
        assert isinstance(err.__cause__, httpx.HTTPStatusError) == (status != 302)
        assert status == 302 or err.url == AMFI


def test_get_does_not_wrap_non_httpx_errors() -> None:  # AC8
    with pytest.raises(RuntimeError, match="boom"):
        _run(RuntimeError("boom"))


def test_get_logs_retries_at_info(caplog: pytest.LogCaptureFixture) -> None:  # AC11
    caplog.set_level(logging.DEBUG, logger="indianfinance._http")
    _run(503, 502, 200)
    records = [r for r in caplog.records if r.levelno > logging.DEBUG]
    assert [r.levelno for r in records] == [logging.INFO] * 2
    assert "retry 1 of 3" in records[0].getMessage()
