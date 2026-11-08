import contextlib
import datetime as dt
import inspect
import itertools
import locale

import pytest

import indianfinance._dates as d
from indianfinance.exceptions import SourceFormatError

D = dt.date
M = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
PATTERN = {"amfi": "dd-Mmm-yyyy", "iso": "yyyy-mm-dd", "compact": "yyyymmdd"}
ARABIC = "".join(chr(0x660 + int(c)) for c in "07")  # non-ASCII digits, must fail
WIDE = "".join(chr(0xFF10 + int(c)) for c in "20261107")
NOV7 = (2026, 11, 7)
# Valid rows: (parser kind, text, (year, month, day))
OK = [("amfi", f"15-{m}-2026", (2026, i, 15)) for i, m in enumerate(M, 1)]
OK += [("amfi", t, NOV7) for t in ("07-NOV-2026", "07-nov-2026")]
OK += [("amfi", "29-Feb-2024", (2024, 2, 29))]
OK += [("amfi", " 06-Nov-2026\r\n", (2026, 11, 6))]
OK += [("iso", t, NOV7) for t in ("2026-11-07", " 2026-11-07\r")]
OK += [("compact", t, NOV7) for t in ("20261107", "20261107\n")]
# Bad rows: (parser kind, text); each text list is "|" separated
BAD = {
    "amfi": "7-Nov-2026|07-Nov-26|07/Nov/2026|07 Nov 2026|07-Nvo-2026|07 -Nov-2026"
    f"|07-Sept-2026|07-11-2026|2026-11-07|07-Nov-2026 10:00|{ARABIC}-Nov-2026"
    "|31-Feb-2026|29-Feb-2026|00-Jan-2026",
    "iso": "2026-11-7|2026/11/07|20261107|2026-W45-6|2026-11-07T00:00:00"
    "|07-Nov-2026|2026-02-29|2026-13-01|0000-01-01",
    "compact": f"2026117|202611070|2026-11-07|2026110a|20261301|{WIDE}",
}
BAD_ROWS = [(k, t) for k in PATTERN for t in ("", "   ", "N.A.", "-")]
BAD_ROWS += [(k, t) for k, v in BAD.items() for t in v.split("|")]
# Chunk rows: (last day, as days after 2026-01-01; max_days; pieces as day pairs)
CHUNKS = [
    (0, 90, [(0, 0)]),
    (89, 90, [(0, 89)]),
    (90, 90, [(0, 89), (90, 90)]),
    (180, 90, [(0, 89), (90, 179), (180, 180)]),
    (9, 4, [(0, 3), (4, 7), (8, 9)]),
]
BAD_ARGS = [(3, 2, 90), (1, 2, 0), (1, 2, -1)]  # (start day, end day, max_days)


def parse(kind: str, text: str, **kw: int) -> dt.date:
    return getattr(d, f"parse_{kind}_date")(text, **kw)  # type: ignore[no-any-return]


@pytest.mark.parametrize(("kind", "text", "ymd"), OK)
def test_parse_returns_date_for_valid_text(
    kind: str, text: str, ymd: tuple[int, ...]
) -> None:
    # AC1, AC2
    assert parse(kind, text) == D(*ymd)
    assert type(parse(kind, text)) is dt.date


@pytest.mark.parametrize(("kind", "text"), BAD_ROWS)
def test_parse_raises_source_format_error_for_bad_text(kind: str, text: str) -> None:
    # AC3
    with pytest.raises(SourceFormatError) as info:
        parse(kind, text)
    assert type(info.value) is SourceFormatError
    assert repr(text) in str(info.value)
    assert PATTERN[kind] in str(info.value)


def test_parse_error_keeps_line_and_cause() -> None:
    # AC4
    with pytest.raises(SourceFormatError) as info:
        d.parse_amfi_date("bad", line=42)
    with pytest.raises(SourceFormatError) as info2:
        d.parse_amfi_date("31-Feb-2026")
    assert info.value.line == 42
    assert info2.value.line is None
    assert isinstance(info2.value.__cause__, ValueError)


def test_format_gives_source_text() -> None:
    # AC5
    assert d.format_amfi_date(D(2026, 3, 5)) == "05-Mar-2026"
    assert d.format_amfi_date(D(2026, 12, 31)) == "31-Dec-2026"
    assert d.format_compact_date(D(2026, 3, 5)) == "20260305"
    assert d.format_compact_date(D(1, 1, 1)) == "00010101"


def test_format_then_parse_round_trips() -> None:
    # AC5
    for day in [D(2026, m, 1) for m in range(1, 13)]:
        assert d.parse_amfi_date(d.format_amfi_date(day)) == day
        assert d.parse_compact_date(d.format_compact_date(day)) == day


def test_amfi_dates_ignore_locale() -> None:
    # AC6
    old = locale.setlocale(locale.LC_TIME)
    try:
        for name in ("de_DE.UTF-8", "de_DE", "German_Germany.1252", "de-DE"):
            with contextlib.suppress(locale.Error):
                locale.setlocale(locale.LC_TIME, name)
                break
        else:
            pytest.skip("no German locale installed")
        for month, text in ((3, "07-Mar-2026"), (12, "07-Dec-2026")):
            assert d.parse_amfi_date(text) == D(2026, month, 7)
            assert d.format_amfi_date(D(2026, month, 7)) == text
    finally:
        locale.setlocale(locale.LC_TIME, old)


def test_is_weekday_for_each_day_of_a_week() -> None:
    # AC7: Mon 2026-11-02 .. Sun 2026-11-08
    got = [d.is_weekday(D(2026, 11, 2 + i)) for i in range(7)]
    assert got == [True] * 5 + [False] * 2


@pytest.mark.parametrize(("last", "size", "want"), CHUNKS)
def test_chunk_range_returns_expected_pieces(
    last: int, size: int, want: list[tuple[int, int]]
) -> None:
    # AC8
    base = D(2026, 1, 1)
    got = d.chunk_range(base, base + dt.timedelta(days=last), max_days=size)
    assert [((a - base).days, (b - base).days) for a, b in got] == want


@pytest.mark.parametrize("size", [1, 7, 90])
def test_chunk_range_pieces_cover_range_without_gaps(size: int) -> None:
    # AC9
    start, end = D(2023, 12, 15), D(2025, 1, 10)
    pieces = d.chunk_range(start, end, max_days=size)
    assert pieces[0][0] == start
    assert pieces[-1][1] == end
    assert all(a <= b and (b - a).days + 1 <= size for a, b in pieces)
    for (_, prev_last), (nxt_first, _) in itertools.pairwise(pieces):
        assert nxt_first - prev_last == dt.timedelta(days=1)
    assert all((b - a).days + 1 == size for a, b in pieces[:-1])


@pytest.mark.parametrize(("start", "end", "size"), BAD_ARGS)
def test_chunk_range_rejects_bad_arguments(start: int, end: int, size: int) -> None:
    # AC10
    with pytest.raises(ValueError, match=r"start|max_days"):
        d.chunk_range(D(2026, 1, start), D(2026, 1, end), max_days=size)


def test_max_history_days_is_chunk_default() -> None:
    # AC11
    assert d.MAX_HISTORY_DAYS == 90
    assert inspect.signature(d.chunk_range).parameters["max_days"].default == 90
