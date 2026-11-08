"""Typed exceptions raised by indianfinance.

Catch `IndianFinanceError` to handle every library error in one place.
"""

from __future__ import annotations

import datetime as dt

__all__ = [
    "IndianFinanceError",
    "NoDataForDate",
    "SourceFormatError",
    "SourceUnavailable",
    "SymbolNotFound",
]


def _rebuild(
    cls: type[IndianFinanceError], args: tuple[object, ...], state: dict[str, object]
) -> IndianFinanceError:
    """Recreate an exception for pickle / copy without calling its `__init__`."""
    err = cls.__new__(cls)
    err.args = args
    err.__dict__.update(state)
    return err


class IndianFinanceError(Exception):
    """Base class for every error raised by indianfinance.

    Example:
        >>> from indianfinance.exceptions import IndianFinanceError, SymbolNotFound
        >>> try:
        ...     raise SymbolNotFound("no scheme with AMFI code 999999", symbol="999999")
        ... except IndianFinanceError as err:
        ...     print(type(err).__name__, err.symbol)
        SymbolNotFound 999999
    """

    def __reduce__(self) -> tuple[object, ...]:
        """Support pickle and copy for subclasses with keyword-only arguments."""
        return (_rebuild, (type(self), self.args, dict(self.__dict__)))


class NoDataForDate(IndianFinanceError):
    """The source has no data for the requested date.

    For example a market holiday, a weekend, or a file that is not published yet.

    Attributes:
        day: The date that has no data.
    """

    day: dt.date

    def __init__(self, message: str, *, day: dt.date) -> None:
        """Create the error.

        Args:
            message: Human-readable text.
            day: The date that has no data.
        """
        super().__init__(message)
        self.day = day


class SourceFormatError(IndianFinanceError):
    """A downloaded file does not have the expected format.

    For example a missing column, a bad number or an unknown header.

    Attributes:
        line: 1-based line number in the source file, or None if not known.
    """

    line: int | None

    def __init__(self, message: str, *, line: int | None = None) -> None:
        """Create the error.

        Args:
            message: Human-readable text.
            line: 1-based line number in the source file, if known.
        """
        super().__init__(message)
        self.line = line


class SourceUnavailable(IndianFinanceError):
    """The source could not be reached or answered with an error, after retries.

    For example a connection error, a timeout or an HTTP error status.

    Attributes:
        url: The requested URL.
        status_code: The HTTP status code, or None if no response arrived.
    """

    url: str
    status_code: int | None

    def __init__(
        self, message: str, *, url: str, status_code: int | None = None
    ) -> None:
        """Create the error.

        Args:
            message: Human-readable text.
            url: The requested URL.
            status_code: HTTP status, or None if no response arrived (timeout,
                connection error).
        """
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class SymbolNotFound(IndianFinanceError):
    """The requested NSE symbol or AMFI scheme code is not in the source data.

    Attributes:
        symbol: The NSE symbol or AMFI scheme code that was asked for.
    """

    symbol: str

    def __init__(self, message: str, *, symbol: str) -> None:
        """Create the error.

        Args:
            message: Human-readable text.
            symbol: The NSE symbol or AMFI scheme code that was asked for.
        """
        super().__init__(message)
        self.symbol = symbol
