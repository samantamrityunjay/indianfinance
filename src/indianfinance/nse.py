"""NSE end-of-day prices for stocks and ETFs, from NSE's whole-market CM bhavcopy.

NSE publishes one zip per trading day. Every row and every series is returned, and
each `EodPrice` carries the trade date from the file (never "today"). See the Data
sources page.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import logging
import re
import zipfile
import zlib
from decimal import Decimal
from typing import Final

from indianfinance._dates import parse_iso_date
from indianfinance.exceptions import SourceFormatError
from indianfinance.models import EodPrice

__all__: list[str] = []

logger: Final = logging.getLogger(__name__)

_COLUMNS: Final[tuple[str, ...]] = (
    "TradDt",
    "ISIN",
    "TckrSymb",
    "SctySrs",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "PrvsClsgPric",
    "TtlTradgVol",
    "TtlTrfVal",
)
"""NSE columns the parser needs (all 11 `EodPrice` sources). Found by name."""

_MAX_CSV_BYTES: Final[int] = 50 * 1024 * 1024
"""Largest uncompressed member accepted (real file: about 640 KB). Zip-bomb guard."""

_PRICE_RE: Final = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_VOLUME_RE: Final = re.compile(r"[0-9]+")


def _unzip_bhavcopy(data: bytes) -> str:
    """Return the text of the single CSV member of a bhavcopy zip (in memory).

    Raises:
        SourceFormatError: If ``data`` is not a zip, does not have exactly one
            member, the member is too large or unreadable, or it is not UTF-8.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
            if len(infos) != 1:
                raise SourceFormatError(
                    f"bhavcopy zip has {len(infos)} members, expected 1"
                )
            if infos[0].file_size > _MAX_CSV_BYTES:
                raise SourceFormatError("bhavcopy member is too large")
            raw = zf.read(infos[0])
    except (
        zipfile.BadZipFile,
        NotImplementedError,
        RuntimeError,
        EOFError,
        zlib.error,
    ) as err:
        raise SourceFormatError(f"cannot read bhavcopy zip: {err}") from err
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as err:
        raise SourceFormatError("bhavcopy is not UTF-8 text") from err


def _price(value: str, line: int) -> Decimal:
    if not _PRICE_RE.fullmatch(value):
        raise SourceFormatError(f"bad number {value!r}", line=line)
    return Decimal(value)


def _text(value: str, name: str, line: int) -> str:
    if not value:
        raise SourceFormatError(f"empty {name}", line=line)
    return value


def _parse_bhavcopy(text: str, *, day: dt.date) -> list[EodPrice]:
    """Parse bhavcopy CSV text into prices, one per row, in file order.

    Raises:
        SourceFormatError: On a bad header, row width, value or trade date, with
            ``.line`` set (``None`` if the file has no data rows).
    """
    reader = csv.reader(io.StringIO(text.removeprefix("﻿"), newline=""))
    header: list[str] | None = None
    index: dict[str, int] = {}
    prices: list[EodPrice] = []
    for row in reader:
        if not row:
            continue
        line = reader.line_num
        if header is None:
            header = [name.strip() for name in row]
            for name in _COLUMNS:
                if name not in header:
                    raise SourceFormatError(
                        f"bhavcopy header has no {name!r} column", line=line
                    )
            index = {name: header.index(name) for name in _COLUMNS}
            continue
        if len(row) != len(header):
            raise SourceFormatError(
                f"expected {len(header)} fields, got {len(row)}", line=line
            )
        f = {name: row[i].strip() for name, i in index.items()}
        trade_day = parse_iso_date(f["TradDt"], line=line)
        if trade_day != day:
            raise SourceFormatError(f"TradDt {trade_day} is not {day}", line=line)
        if not _VOLUME_RE.fullmatch(f["TtlTradgVol"]):
            raise SourceFormatError(f"bad volume {f['TtlTradgVol']!r}", line=line)
        prices.append(
            EodPrice(
                symbol=_text(f["TckrSymb"], "TckrSymb", line),
                series=_text(f["SctySrs"], "SctySrs", line),
                isin=_text(f["ISIN"], "ISIN", line),
                date=trade_day,
                open=_price(f["OpnPric"], line),
                high=_price(f["HghPric"], line),
                low=_price(f["LwPric"], line),
                close=_price(f["ClsPric"], line),
                prev_close=_price(f["PrvsClsgPric"], line),
                volume=int(f["TtlTradgVol"]),
                traded_value=_price(f["TtlTrfVal"], line),
            )
        )
    if header is None:
        raise SourceFormatError("bhavcopy is empty", line=1)
    if not prices:
        raise SourceFormatError("bhavcopy has no rows")
    logger.debug("parsed %d bhavcopy rows for %s", len(prices), day)
    return prices


def _read_bhavcopy(data: bytes, *, day: dt.date) -> list[EodPrice]:
    """Unzip and parse one bhavcopy; the single entry point for the download step."""
    return _parse_bhavcopy(_unzip_bhavcopy(data), day=day)
