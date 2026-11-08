"""Date parsing, formatting and range helpers for source files (internal)."""

from __future__ import annotations

import datetime as dt
import re
from typing import Final

from indianfinance.exceptions import SourceFormatError

MAX_HISTORY_DAYS: Final[int] = 90
"""Most days (both ends counted) in one AMFI NAV history request."""

_MONTHS: Final[tuple[str, ...]] = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
_MONTH_NUMBER: Final[dict[str, int]] = {m.lower(): i for i, m in enumerate(_MONTHS, 1)}

# Explicit ASCII classes, never \d, so non-ASCII digits are rejected.
_AMFI_RE: Final = re.compile(r"([0-9]{2})-([A-Za-z]{3})-([0-9]{4})")
_ISO_RE: Final = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_COMPACT_RE: Final = re.compile(r"([0-9]{4})([0-9]{2})([0-9]{2})")


def _bad(
    text: str,
    kind: str,
    pattern: str,
    line: int | None,
    cause: ValueError | None = None,
) -> SourceFormatError:
    err = SourceFormatError(f"bad {kind} date {text!r}: expected {pattern}", line=line)
    err.__cause__ = cause
    return err


def parse_amfi_date(text: str, *, line: int | None = None) -> dt.date:
    """Parse an AMFI date such as ``07-Nov-2026``.

    Format: two-digit day, ``-``, three-letter English month (any case), ``-``,
    four-digit year. Leading and trailing whitespace is ignored.

    Args:
        text: The date text from the source.
        line: 1-based line number in the source file, passed on to the error.

    Returns:
        The date.

    Raises:
        SourceFormatError: If ``text`` does not match the format, the month is unknown,
            or the date does not exist (for example ``31-Feb-2026``).
    """
    match = _AMFI_RE.fullmatch(text.strip())
    month = _MONTH_NUMBER.get(match.group(2).lower()) if match else None
    if match is None or month is None:
        raise _bad(text, "AMFI", "dd-Mmm-yyyy", line)
    try:
        return dt.date(int(match.group(3)), month, int(match.group(1)))
    except ValueError as err:
        raise _bad(text, "AMFI", "dd-Mmm-yyyy", line, err) from err


def _parse_numeric(
    regex: re.Pattern[str], text: str, kind: str, pattern: str, line: int | None
) -> dt.date:
    match = regex.fullmatch(text.strip())
    if match is None:
        raise _bad(text, kind, pattern, line)
    try:
        return dt.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError as err:
        raise _bad(text, kind, pattern, line, err) from err


def parse_iso_date(text: str, *, line: int | None = None) -> dt.date:
    """Parse an ISO date such as ``2026-11-07`` (NSE UDiFF ``TradDt``).

    Format: exactly ``yyyy-mm-dd`` with ASCII digits. Leading and trailing whitespace
    is ignored.

    Args:
        text: The date text from the source.
        line: 1-based line number in the source file, passed on to the error.

    Returns:
        The date.

    Raises:
        SourceFormatError: If ``text`` does not match the format or the date does not
            exist (for example ``2026-02-29``).
    """
    return _parse_numeric(_ISO_RE, text, "ISO", "yyyy-mm-dd", line)


def parse_compact_date(text: str, *, line: int | None = None) -> dt.date:
    """Parse a compact date such as ``20261107`` (NSE bhavcopy file names).

    Format: exactly 8 ASCII digits, ``yyyymmdd``. Leading and trailing whitespace is
    ignored.

    Args:
        text: The date text from the source.
        line: 1-based line number in the source file, passed on to the error.

    Returns:
        The date.

    Raises:
        SourceFormatError: If ``text`` does not match the format or the date does not
            exist (for example ``20261301``).
    """
    return _parse_numeric(_COMPACT_RE, text, "compact", "yyyymmdd", line)


def format_amfi_date(day: dt.date) -> str:
    """Format a date as AMFI writes it, e.g. ``07-Nov-2026`` (NAV history URLs).

    The day is zero-padded to 2 digits, the month comes from a fixed English table
    (title case), and the year is zero-padded to 4 digits. The result does not depend
    on the computer's language settings.

    Args:
        day: The date to format.

    Returns:
        The text, for example ``05-Mar-2026``.
    """
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year:04d}"


def format_compact_date(day: dt.date) -> str:
    """Format a date as ``yyyymmdd``, e.g. ``20261107`` (NSE bhavcopy file names).

    Args:
        day: The date to format.

    Returns:
        The text, for example ``20260305``.
    """
    return f"{day.year:04d}{day.month:02d}{day.day:02d}"


def is_weekday(day: dt.date) -> bool:
    """Return True for Monday to Friday, False for Saturday and Sunday.

    Does not know about market holidays (D-002).

    Args:
        day: The date to check.

    Returns:
        True if ``day`` is Monday to Friday.
    """
    return day.weekday() < 5


def chunk_range(
    start: dt.date, end: dt.date, *, max_days: int = MAX_HISTORY_DAYS
) -> list[tuple[dt.date, dt.date]]:
    """Split the inclusive range ``start``..``end`` into consecutive pieces.

    Each piece is an inclusive ``(first, last)`` pair with at most ``max_days`` days
    (both ends counted). Pieces are in date order, do not overlap and leave no gap. The
    first starts on ``start``, the last ends on ``end``, and only the last may be
    shorter.

    Args:
        start: First day, included.
        end: Last day, included.
        max_days: Most days in one piece. Default ``MAX_HISTORY_DAYS`` (90).

    Returns:
        The pieces. ``start == end`` gives one one-day piece.

    Raises:
        ValueError: If ``start > end`` or ``max_days < 1`` (caller mistake, not a
            source problem).

    Example:
        >>> import datetime as dt
        >>> from indianfinance._dates import chunk_range
        >>> chunk_range(dt.date(2026, 1, 1), dt.date(2026, 1, 10), max_days=4)
        [(datetime.date(2026, 1, 1), datetime.date(2026, 1, 4)),
         (datetime.date(2026, 1, 5), datetime.date(2026, 1, 8)),
         (datetime.date(2026, 1, 9), datetime.date(2026, 1, 10))]
    """
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    if max_days < 1:
        raise ValueError(f"max_days must be at least 1, got {max_days}")
    step = dt.timedelta(days=max_days)
    one = dt.timedelta(days=1)
    pieces: list[tuple[dt.date, dt.date]] = []
    first = start
    while first <= end:
        pieces.append((first, min(first + step - one, end)))
        first += step
    return pieces
