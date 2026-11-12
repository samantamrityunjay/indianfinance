"""AMFI mutual fund NAVs and schemes, from AMFI's whole-market files.

Every function downloads a whole file (no cache). Each record carries the NAV date
AMFI gives, never "today". NAV history is whole-market too, split into 90-day
requests. See the Data sources page for the file formats.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from decimal import Decimal
from typing import Final

import httpx

from indianfinance import _http
from indianfinance._dates import chunk_range, format_amfi_date, parse_amfi_date
from indianfinance.exceptions import (
    NoDataForDate,
    SourceFormatError,
    SourceUnavailable,
    SymbolNotFound,
)
from indianfinance.models import NavRecord, Scheme

__all__ = ["HISTORY_TIMEOUT", "latest_navs", "nav_history", "schemes"]

logger: Final = logging.getLogger(__name__)

HISTORY_TIMEOUT: Final[httpx.Timeout] = httpx.Timeout(10.0, read=300.0)
"""Timeouts for NAV history: 10 s to connect, write and pool; 300 s to read.

AMFI builds a 90-day report (about 73 MB) for 2 to 2.5 minutes before the first byte.
Use it for your own client: ``httpx.Client(timeout=HISTORY_TIMEOUT)``.
"""

_HISTORY_URL: Final[str] = (
    "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
)
_HISTORY_HEADER: Final[str] = (
    "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;"
    "ISIN Div Reinvestment;Net Asset Value;Date"
)
_HISTORY_ATTEMPTS: Final[int] = 2
_NO_DATA_TEXT: Final[str] = "no data found"

_NAVALL_URL: Final[str] = "https://portal.amfiindia.com/spages/NAVAll.txt"
_NAVALL_HEADER: Final[str] = (
    "Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;"
    "Plan;Option;Net Asset Value;Date"
)
_FIELDS: Final[int] = 8
_NAV_MISSING: Final[frozenset[str]] = frozenset({"", "-", "N.A.", "N.A", "NA"})
_CATEGORY_RE: Final = re.compile(r"(?P<type>[^()]*?Schemes)\s*\((?P<category>.*)\)")
_ISIN_RE: Final = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]")
_CODE_RE: Final = re.compile(r"[0-9]+")
_NAV_RE: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def latest_navs(*, client: httpx.Client | None = None) -> list[NavRecord]:
    """Return the latest NAV of every AMFI scheme, each with its own NAV date.

    Downloads AMFI's ``NAVAll.txt`` (about 1.5 MB) once per call. The NAV date differs
    per record: most have the last business day, liquid and overnight funds can have a
    later (weekend) date, and closed schemes can be years old. Read ``NavRecord.date``;
    never assume one date for the whole list.

    Rows whose NAV is missing (``N.A.``, ``-`` or empty) are skipped. A NAV of ``0``
    (for example a segregated portfolio) is returned as ``Decimal("0")``.

    Args:
        client: Your own ``httpx.Client`` (timeout, proxies, headers). Used as is and
            not closed. ``None`` creates a short-lived client with the library defaults.

    Returns:
        One record per scheme row, in file order.

    Raises:
        SourceUnavailable: If the download fails after retries, or the reply is not
            ``text/plain`` (for example an HTML error page).
        SourceFormatError: If the file does not have the documented format: wrong
            header, no rows, a row without 8 fields, a bad scheme code, NAV or date,
            or a row before its category / AMC line. ``.line`` is the 1-based line.

    Example:
        >>> from indianfinance.amfi import latest_navs
        >>> navs = latest_navs()  # doctest: +SKIP
    """
    parsed = _parse_navall(_download(client))
    records = [rec for _, rec in parsed if rec is not None]
    skipped = len(parsed) - len(records)
    if skipped:
        logger.info("NAVAll: skipped %d rows with no NAV", skipped)
    return records


def schemes(*, client: httpx.Client | None = None) -> list[Scheme]:
    """Return every AMFI scheme with its ISINs, AMC, scheme type and category.

    Downloads ``NAVAll.txt`` once per call (the same file as ``latest_navs()``). One
    ``Scheme`` per row, so one per AMFI code (each plan and option has its own code).
    Rows with a missing NAV are included. ``amc`` comes from the AMC line above the
    row; ``scheme_type`` and ``category`` from the category line, for example
    ``Open Ended Schemes(Debt Scheme - Liquid Fund)`` gives ``"Open Ended Schemes"``
    and ``"Debt Scheme - Liquid Fund"``.

    Args:
        client: As in ``latest_navs()``.

    Returns:
        One scheme per row, in file order.

    Raises:
        SourceUnavailable: As in ``latest_navs()``.
        SourceFormatError: As in ``latest_navs()``.

    Example:
        >>> from indianfinance.amfi import schemes
        >>> found = [s for s in schemes() if "Liquid" in s.category]  # doctest: +SKIP
    """
    return [scheme for scheme, _ in _parse_navall(_download(client))]


def nav_history(
    start: dt.date,
    end: dt.date,
    *,
    amfi_code: str | None = None,
    client: httpx.Client | None = None,
) -> list[NavRecord]:
    """Return every NAV AMFI has from ``start`` to ``end``, both days included.

    Downloads AMFI's whole-market NAV history. Ranges longer than 90 days are split
    into 90-day pieces, downloaded one after another. Each piece of 90 days is about
    73 MB and AMFI needs 2 to 2.5 minutes before it starts sending, so a year takes
    about 10 to 13 minutes (estimate from measured waits of 113-145 s per piece, not
    counting download time). There is no cache.

    Weekends and holidays have NAVs only for schemes that publish every day (liquid,
    overnight, some ETFs). A piece with no NAVs at all is skipped. Rows with a missing
    NAV are skipped; a NAV of ``0`` is kept.

    Args:
        start: First day, included.
        end: Last day, included.
        amfi_code: Keep only this scheme (AMFI scheme code, digits, for example
            ``"148921"``). The whole market is still downloaded. ``None`` keeps all.
        client: Your own ``httpx.Client``. Used as is (also its timeout) and not
            closed. ``None`` creates a client with ``HISTORY_TIMEOUT``.

    Returns:
        One record per scheme per NAV date, piece after piece in date order; inside a
        piece in AMFI's order (grouped by scheme, dates going up). With ``amfi_code``,
        the dates go up.

    Raises:
        ValueError: If ``start > end`` or ``amfi_code`` is not ASCII digits. Nothing
            is downloaded.
        NoDataForDate: If AMFI has no NAVs in the whole range (for example dates not
            published yet). ``.day`` is ``start``.
        SymbolNotFound: If ``amfi_code`` has no NAV in the range. ``.symbol`` is the
            code.
        SourceUnavailable: If a download fails after retries, AMFI redirects the
            request (range over its limit), or the reply is neither ``text/plain`` nor
            the "No data found" page.
        SourceFormatError: If a file does not have the documented format (wrong
            header, no rows, a row without 8 fields, a bad code, NAV or date, or a date
            outside the requested piece). ``.line`` is the 1-based line.

    Example:
        >>> import datetime as dt
        >>> from indianfinance.amfi import nav_history
        >>> navs = nav_history(
        ...     dt.date(2026, 11, 5), dt.date(2026, 11, 6), amfi_code="148921"
        ... )  # doctest: +SKIP
    """
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    if amfi_code is not None and _CODE_RE.fullmatch(amfi_code) is None:
        raise ValueError(f"amfi_code must be digits, got {amfi_code!r}")
    records: list[NavRecord] = []
    seen_data = False
    with _http.open_client(client, timeout=HISTORY_TIMEOUT) as c:
        for first, last in chunk_range(start, end):
            text = _download_history(c, first, last)
            if text is None:
                logger.info("NAV history %s..%s: no data", first, last)
                continue
            seen_data = True
            records.extend(
                _parse_history(text, first=first, last=last, amfi_code=amfi_code)
            )
    if not seen_data:
        raise NoDataForDate(f"AMFI has no NAVs from {start} to {end}", day=start)
    if amfi_code is not None and not records:
        raise SymbolNotFound(
            f"no NAV for AMFI code {amfi_code} from {start} to {end}", symbol=amfi_code
        )
    return records


def _download_history(
    client: httpx.Client, first: dt.date, last: dt.date
) -> str | None:
    """Download one piece (at most 90 days); return its text, or None for "no data".

    Raises ``SourceUnavailable`` if AMFI redirects away from the history URL (a range
    over its limit) or the reply is not ``text/plain``.
    """
    params = {"frmdt": format_amfi_date(first), "todt": format_amfi_date(last)}
    response = _http.get(
        client, _HISTORY_URL, params=params, max_attempts=_HISTORY_ATTEMPTS
    )
    final = response.request.url
    wanted = httpx.URL(_HISTORY_URL)
    if (final.host, final.path) != (wanted.host, wanted.path):
        raise SourceUnavailable(
            f"AMFI redirected the NAV history request to {final}; "
            "the range may be over AMFI's limit",
            url=str(wanted.copy_merge_params(params)),
            status_code=response.status_code,
        )
    media_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if media_type == "text/html" and _NO_DATA_TEXT in response.text.casefold():
        return None
    return _decode_text(response)


def _parse_history(
    text: str, *, first: dt.date, last: dt.date, amfi_code: str | None = None
) -> list[NavRecord]:
    """Parse one NAV history file into records, in file order. Pure: no HTTP.

    Rows with a missing NAV are skipped (one INFO log with the count). With
    ``amfi_code``, other schemes' rows are skipped before their NAV, ISIN and date are
    parsed.
    """
    lines = [raw.removesuffix("\r") for raw in text.split("\n")]
    if lines[0].strip() != _HISTORY_HEADER:
        raise SourceFormatError("unexpected NAV history header", line=1)
    records: list[NavRecord] = []
    rows = skipped = 0
    for number, line in enumerate(lines[1:], start=2):
        if ";" not in line:
            continue
        fields = [f.strip() for f in line.split(";")]
        if len(fields) != _FIELDS:
            raise SourceFormatError(
                f"expected {_FIELDS} fields, got {len(fields)}", line=number
            )
        rows += 1
        code, name, plan, option, isin, isin_re, nav_text, date_text = fields
        if amfi_code is not None and code != amfi_code:
            continue
        if _CODE_RE.fullmatch(code) is None:
            raise SourceFormatError(f"bad scheme code {code!r}", line=number)
        if not name:
            raise SourceFormatError("empty scheme name", line=number)
        nav = _parse_nav(nav_text, line=number)
        day = parse_amfi_date(date_text, line=number)
        if not first <= day <= last:
            raise SourceFormatError(f"date {day} outside {first}..{last}", line=number)
        if nav is None:
            skipped += 1
            continue
        records.append(
            NavRecord(
                amfi_code=code,
                scheme_name=name,
                plan=plan or None,
                option=option or None,
                isin=_parse_isin(isin),
                isin_reinvestment=_parse_isin(isin_re),
                date=day,
                nav=nav,
            )
        )
    if rows == 0:
        raise SourceFormatError("NAV history has no rows", line=None)
    if skipped:
        logger.info(
            "NAV history %s..%s: skipped %d rows with no NAV", first, last, skipped
        )
    return records


def _download(client: httpx.Client | None = None) -> str:
    """Download ``NAVAll.txt`` and return its text."""
    with _http.open_client(client) as c:
        return _decode_text(_http.get(c, _NAVALL_URL))


def _decode_text(response: httpx.Response) -> str:
    """Check the reply is ``text/plain`` and return its body as text.

    Anything else (also a missing ``Content-Type``) raises ``SourceUnavailable``. Bytes
    that are not UTF-8 raise ``SourceFormatError``. A BOM is dropped.
    """
    media_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if media_type != "text/plain":
        raise SourceUnavailable(
            f"expected text/plain, got {media_type or 'no Content-Type'!r}",
            url=str(response.request.url),
            status_code=response.status_code,
        )
    try:
        return response.content.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise SourceFormatError("reply is not valid UTF-8", line=None) from err


def _split_category(line: str) -> tuple[str, str] | None:
    """Return ``(scheme_type, category)`` for a category line, else ``None``.

    Works for NAVAll (``Open Ended Schemes(Debt Scheme - Gilt Fund)``) and history
    (``Open Ended Schemes ( Equity Scheme - Multi Cap Fund )``). An AMC name with
    brackets (``IL&FS Mutual Fund (IDF)``) is not a category.
    """
    match = _CATEGORY_RE.fullmatch(line.strip())
    if match is None:
        return None
    return match.group("type").strip(), match.group("category").strip()


def _parse_isin(text: str) -> str | None:
    """Return the stripped ISIN, or ``None`` if it is not one."""
    value = text.strip()
    return value if _ISIN_RE.fullmatch(value) else None


def _parse_nav(text: str, *, line: int) -> Decimal | None:
    """Return the NAV, or ``None`` if the source says it is missing.

    Raises:
        SourceFormatError: If the text is not a plain non-negative decimal.
    """
    value = text.strip()
    if value.upper() in _NAV_MISSING:
        return None
    if _NAV_RE.fullmatch(value) is None:
        raise SourceFormatError(f"bad NAV {text!r}", line=line)
    return Decimal(value)


def _parse_navall(text: str) -> list[tuple[Scheme, NavRecord | None]]:
    """Parse ``NAVAll.txt`` text into ``(scheme, record)`` pairs, in file order.

    ``record`` is ``None`` when the NAV is missing. Pure: no HTTP.
    """
    lines = [raw.removesuffix("\r") for raw in text.split("\n")]
    if lines[0].strip() != _NAVALL_HEADER:
        raise SourceFormatError("unexpected NAVAll header", line=1)
    category: tuple[str, str] | None = None
    amc: str | None = None
    result: list[tuple[Scheme, NavRecord | None]] = []
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "":
            continue
        if ";" not in line:
            found = _split_category(line)
            if found is not None:
                category, amc = found, None
            else:
                amc = line.strip()
            continue
        fields = [f.strip() for f in line.split(";")]
        if len(fields) != _FIELDS:
            raise SourceFormatError(
                f"expected {_FIELDS} fields, got {len(fields)}", line=number
            )
        code, isin, isin_re, name, plan, option, nav_text, date_text = fields
        if category is None or amc is None:
            raise SourceFormatError("row before its category / AMC line", line=number)
        if _CODE_RE.fullmatch(code) is None:
            raise SourceFormatError(f"bad scheme code {code!r}", line=number)
        if not name:
            raise SourceFormatError("empty scheme name", line=number)
        isins = (_parse_isin(isin), _parse_isin(isin_re))
        for raw, clean in zip((isin, isin_re), isins, strict=True):
            if clean is None and raw not in ("", "-"):
                logger.debug("NAVAll line %d: ignored non-ISIN %r", number, raw)
        nav = _parse_nav(nav_text, line=number)
        day = parse_amfi_date(date_text, line=number)
        scheme = Scheme(
            amfi_code=code,
            scheme_name=name,
            plan=plan or None,
            option=option or None,
            isin=isins[0],
            isin_reinvestment=isins[1],
            amc=amc,
            scheme_type=category[0],
            category=category[1],
        )
        record = (
            None
            if nav is None
            else NavRecord(
                amfi_code=code,
                scheme_name=name,
                plan=plan or None,
                option=option or None,
                isin=isins[0],
                isin_reinvestment=isins[1],
                date=day,
                nav=nav,
            )
        )
        result.append((scheme, record))
    if not result:
        raise SourceFormatError("NAVAll has no rows", line=None)
    return result
