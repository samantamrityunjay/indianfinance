"""AMFI mutual fund NAVs and schemes, from AMFI's whole-market files.

Every function downloads a whole file (no cache). Each record carries the NAV date
AMFI gives, never "today". See the Data sources page for the file formats.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Final

import httpx

from indianfinance import _http
from indianfinance._dates import parse_amfi_date
from indianfinance.exceptions import SourceFormatError, SourceUnavailable
from indianfinance.models import NavRecord, Scheme

__all__ = ["latest_navs", "schemes"]

logger: Final = logging.getLogger(__name__)

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
