"""Tests for indianfinance.exceptions (T-007)."""

from __future__ import annotations

import copy
import datetime as dt
import pickle
import re
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

from indianfinance import exceptions
from indianfinance.exceptions import (
    IndianFinanceError,
    NoDataForDate,
    SourceFormatError,
    SourceUnavailable,
    SymbolNotFound,
)

DAY = dt.date(2026, 11, 8)
URL = "https://x.in/a"

SUBCLASSES = [NoDataForDate, SourceFormatError, SourceUnavailable, SymbolNotFound]


def _make(cls: type[IndianFinanceError], message: str = "m") -> IndianFinanceError:
    """Build one instance of each subclass with all attributes set."""
    if cls is NoDataForDate:
        return NoDataForDate(message, day=DAY)
    if cls is SourceFormatError:
        return SourceFormatError(message, line=7)
    if cls is SourceUnavailable:
        return SourceUnavailable(message, url=URL, status_code=503)
    if cls is SymbolNotFound:
        return SymbolNotFound(message, symbol="INFY")
    raise AssertionError(cls)


# AC1
def test_base_error_subclasses_exception() -> None:
    assert issubclass(IndianFinanceError, Exception)


# AC1
@pytest.mark.parametrize("cls", SUBCLASSES)
def test_exceptions_subclass_indianfinanceerror(cls: type[IndianFinanceError]) -> None:
    assert cls.__bases__ == (IndianFinanceError,)


# AC1
def test_exceptions_are_not_subclasses_of_each_other() -> None:
    for a in SUBCLASSES:
        for b in SUBCLASSES:
            if a is not b:
                assert not issubclass(a, b)


# AC1
@pytest.mark.parametrize("cls", SUBCLASSES)
def test_base_error_catches_every_subclass(cls: type[IndianFinanceError]) -> None:
    with pytest.raises(IndianFinanceError):
        raise _make(cls)


# AC2
def test_no_data_for_date_keeps_day() -> None:
    assert NoDataForDate("m", day=DAY).day == dt.date(2026, 11, 8)


# AC2
def test_source_format_error_line_defaults_to_none() -> None:
    assert SourceFormatError("m").line is None


# AC2
def test_source_format_error_keeps_line() -> None:
    assert SourceFormatError("m", line=7).line == 7


# AC2
def test_source_unavailable_status_code_defaults_to_none() -> None:
    assert SourceUnavailable("m", url=URL).status_code is None


# AC2
def test_source_unavailable_keeps_url_and_status_code() -> None:
    err = SourceUnavailable("m", url=URL, status_code=503)
    assert err.url == "https://x.in/a"
    assert err.status_code == 503


# AC2
def test_symbol_not_found_keeps_symbol() -> None:
    assert SymbolNotFound("m", symbol="INFY").symbol == "INFY"


# AC3
@pytest.mark.parametrize("cls", SUBCLASSES)
def test_exception_str_is_message(cls: type[IndianFinanceError]) -> None:
    err = _make(cls)
    assert str(err) == "m"
    assert err.args == ("m",)


# AC3
def test_base_error_accepts_message_only() -> None:
    err = IndianFinanceError("m")
    assert str(err) == "m"
    assert err.args == ("m",)


# AC3 (edge: empty message)
@pytest.mark.parametrize("cls", SUBCLASSES)
def test_exception_str_is_empty_for_empty_message(
    cls: type[IndianFinanceError],
) -> None:
    assert str(_make(cls, message="")) == ""


# AC4
def test_exception_attributes_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        NoDataForDate("m", DAY)  # type: ignore[misc]
    with pytest.raises(TypeError):
        SourceFormatError("m", 7)  # type: ignore[misc]
    with pytest.raises(TypeError):
        SourceUnavailable("m", URL)  # type: ignore[misc]
    with pytest.raises(TypeError):
        SourceUnavailable("m", url=URL, status_code=503, extra=1)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SymbolNotFound("m", "INFY")  # type: ignore[misc]


# AC4
def test_exception_requires_its_attribute() -> None:
    with pytest.raises(TypeError):
        NoDataForDate("m")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SourceUnavailable("m")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SymbolNotFound("m")  # type: ignore[call-arg]


# AC5
@pytest.mark.parametrize("cls", SUBCLASSES)
@pytest.mark.parametrize("clone", [lambda e: pickle.loads(pickle.dumps(e)), copy.copy])
def test_exception_survives_pickle_and_copy(
    cls: type[IndianFinanceError],
    clone: Callable[[IndianFinanceError], IndianFinanceError],
) -> None:
    err = _make(cls)
    other = clone(err)
    assert type(other) is cls
    assert other is not err
    assert str(other) == "m"
    assert other.args == ("m",)
    assert vars(other) == vars(err)


# AC5 (attribute values checked as literals, not just equal to the original)
def test_pickled_exceptions_keep_attribute_values() -> None:
    a = pickle.loads(pickle.dumps(NoDataForDate("m", day=DAY)))
    assert a.day == dt.date(2026, 11, 8)
    b = pickle.loads(pickle.dumps(SourceFormatError("m", line=7)))
    assert b.line == 7
    c = pickle.loads(pickle.dumps(SourceUnavailable("m", url=URL, status_code=503)))
    assert (c.url, c.status_code) == ("https://x.in/a", 503)
    d = pickle.loads(pickle.dumps(SymbolNotFound("m", symbol="INFY")))
    assert d.symbol == "INFY"


# AC5 (edge: None defaults stay None)
def test_pickled_defaults_stay_none() -> None:
    unavailable = pickle.loads(pickle.dumps(SourceUnavailable("m", url=URL)))
    assert unavailable.status_code is None
    assert pickle.loads(pickle.dumps(SourceFormatError("m"))).line is None


# AC6
def test_exceptions_module_public_names() -> None:
    assert exceptions.__all__ == [
        "IndianFinanceError",
        "NoDataForDate",
        "SourceFormatError",
        "SourceUnavailable",
        "SymbolNotFound",
    ]


# AC6
def test_top_level_package_does_not_reexport_exceptions() -> None:
    import indianfinance

    assert indianfinance.__all__ == ["__version__"]
    assert not hasattr(indianfinance, "NoDataForDate")


# Edge cases: datetime accepted as day, line not validated
def test_datetime_day_is_stored_as_given() -> None:
    value = dt.datetime(2026, 11, 8, 9, 30, tzinfo=dt.UTC)
    assert NoDataForDate("m", day=value).day is value


# Edge case
def test_source_format_error_line_is_not_validated() -> None:
    assert SourceFormatError("m", line=0).line == 0
    assert SourceFormatError("m", line=-3).line == -3


# Edge case: subclass identity (a holiday is not an outage)
def test_no_data_for_date_is_not_source_unavailable() -> None:
    assert not isinstance(NoDataForDate("holiday", day=DAY), SourceUnavailable)


# Edge case: chaining keeps __cause__ in-process
def test_source_unavailable_keeps_cause_when_chained() -> None:
    cause = TimeoutError("slow")
    with pytest.raises(SourceUnavailable) as info:
        raise SourceUnavailable("m", url=URL) from cause
    assert info.value.__cause__ is cause


# ---- T-007 qa mode 2: extra edge cases ---------------------------------------------

PROTOCOLS = list(range(pickle.HIGHEST_PROTOCOL + 1))


class _SubNoData(NoDataForDate):
    """User subclass with an extra attribute."""

    def __init__(self, message: str, *, day: dt.date, extra: str) -> None:
        super().__init__(message, day=day)
        self.extra = extra


# AC5: every pickle protocol, not only the default
@pytest.mark.parametrize("protocol", PROTOCOLS)
@pytest.mark.parametrize("cls", SUBCLASSES)
def test_exception_survives_every_pickle_protocol(
    cls: type[IndianFinanceError], protocol: int
) -> None:
    err = _make(cls)
    other = pickle.loads(pickle.dumps(err, protocol=protocol))
    assert type(other) is cls
    assert other.args == ("m",)
    assert vars(other) == vars(err)


# AC5: deepcopy
@pytest.mark.parametrize("cls", SUBCLASSES)
def test_exception_survives_deepcopy(cls: type[IndianFinanceError]) -> None:
    err = _make(cls)
    other = copy.deepcopy(err)
    assert type(other) is cls
    assert other is not err
    assert other.args == ("m",)
    assert vars(other) == vars(err)


# AC5: base class itself (message only, empty __dict__)
def test_base_error_survives_pickle() -> None:
    other = pickle.loads(pickle.dumps(IndianFinanceError("m")))
    assert type(other) is IndianFinanceError
    assert other.args == ("m",)


# AC5: subclass of a subclass keeps its class and extra attribute
def test_subclass_of_subclass_survives_pickle_and_copy() -> None:
    err = _SubNoData("m", day=DAY, extra="x")
    for other in (pickle.loads(pickle.dumps(err)), copy.copy(err), copy.deepcopy(err)):
        assert type(other) is _SubNoData
        assert other.day == dt.date(2026, 11, 8)
        assert other.extra == "x"
        assert other.args == ("m",)
        assert isinstance(other, NoDataForDate)


# AC5: attributes changed after construction are what gets copied
def test_pickle_keeps_attribute_changed_after_construction() -> None:
    err = SourceUnavailable("m", url=URL)
    err.status_code = 429
    assert pickle.loads(pickle.dumps(err)).status_code == 429


# AC5: copy.copy gives an independent __dict__; deepcopy copies mutable values
def test_copy_does_not_share_attribute_dict() -> None:
    err = SymbolNotFound("m", symbol="INFY")
    shallow = copy.copy(err)
    shallow.symbol = "TCS"
    assert err.symbol == "INFY"


# AC5 (odd values): non-ASCII text, odd types, datetime, large and negative ints
def test_pickle_keeps_odd_attribute_values() -> None:
    msg = "रुपये ₹ no data\nline2"
    err = SymbolNotFound(msg, symbol="ÅÄÖ-नमस्ते")
    other = pickle.loads(pickle.dumps(err))
    assert str(other) == msg
    assert other.symbol == "ÅÄÖ-नमस्ते"

    when = dt.datetime(2026, 11, 8, 9, 30, tzinfo=dt.UTC)
    other_day = pickle.loads(pickle.dumps(NoDataForDate("m", day=when)))
    assert other_day.day == when
    assert type(other_day.day) is dt.datetime

    assert pickle.loads(pickle.dumps(SourceFormatError("m", line=-3))).line == -3
    big = 10**30
    assert pickle.loads(pickle.dumps(SourceFormatError("m", line=big))).line == big
    assert (
        pickle.loads(
            pickle.dumps(SourceUnavailable("m", url="", status_code=0))
        ).status_code
        == 0
    )


# AC5: a raised exception with a traceback still pickles; cause is dropped
def test_pickle_of_raised_exception_works_and_drops_cause() -> None:
    try:
        try:
            raise TimeoutError("slow")
        except TimeoutError as cause:
            raise SourceUnavailable("m", url=URL) from cause
    except SourceUnavailable as err:
        other = pickle.loads(pickle.dumps(err))
    assert type(other) is SourceUnavailable
    assert other.__cause__ is None
    assert other.url == URL


# AC3: extra positional args to the base class behave like Exception
def test_base_error_keeps_multiple_args_like_exception() -> None:
    err = IndianFinanceError("a", 1)
    assert err.args == ("a", 1)
    assert pickle.loads(pickle.dumps(err)).args == ("a", 1)


# AC1: catching one subclass does not catch another
def test_except_no_data_for_date_does_not_catch_source_unavailable() -> None:
    caught_wrong = False
    try:
        try:
            raise SourceUnavailable("m", url=URL)
        except NoDataForDate:
            caught_wrong = True
    except SourceUnavailable:
        pass
    assert not caught_wrong


# AC4: keyword names are exact
def test_exception_rejects_wrong_keyword_name() -> None:
    with pytest.raises(TypeError):
        NoDataForDate("m", date=DAY)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SymbolNotFound("m", code="INFY")  # type: ignore[call-arg]


# AC1-AC6: every class has its documented attribute names set in vars()
@pytest.mark.parametrize(
    ("cls", "names"),
    [
        (NoDataForDate, {"day"}),
        (SourceFormatError, {"line"}),
        (SourceUnavailable, {"url", "status_code"}),
        (SymbolNotFound, {"symbol"}),
    ],
)
def test_exception_instance_dict_has_only_documented_attributes(
    cls: type[IndianFinanceError], names: set[str]
) -> None:
    assert set(vars(_make(cls))) == names


# AC7: docstring example exists and every public class has a docstring
def test_exceptions_public_classes_have_docstrings() -> None:
    for name in exceptions.__all__:
        assert getattr(exceptions, name).__doc__


# AC8 / AC9: docs pages exist and carry the required content (harness runs the blocks)
def _docs(page: str) -> str:
    root = Path(__file__).resolve().parent.parent / "docs"
    return (root / page).read_text(encoding="utf-8")


def test_reference_exceptions_page_has_directive_and_runnable_block() -> None:
    text = _docs("reference/exceptions.md")
    assert "::: indianfinance.exceptions" in text
    assert "```python" in text
    for name in exceptions.__all__:
        assert name in text


def test_design_page_has_decimal_block_and_no_missing_links() -> None:
    text = _docs("explanation/design.md")
    assert "```python" in text
    assert "Decimal" in text
    root = Path(__file__).resolve().parent.parent / "docs" / "explanation"
    for target in re.findall(r"\]\(([^)#:]+\.md)(?:#[^)]*)?\)", text):
        assert (root / target).resolve().exists(), target


def test_docs_pages_exist_under_docs_tree() -> None:
    root = Path(__file__).resolve().parent.parent / "docs"
    found = {p.relative_to(root).as_posix() for p in root.rglob("*.md")}
    assert {"reference/exceptions.md", "explanation/design.md"} <= found


# AC10: nav order
def test_zensical_nav_lists_new_pages_in_order() -> None:

    root = Path(__file__).resolve().parent.parent
    nav = tomllib.loads((root / "zensical.toml").read_text(encoding="utf-8"))[
        "project"
    ]["nav"]
    flat = repr(nav)
    positions = [
        flat.index(p)
        for p in (
            "index.md",
            "install.md",
            "reference/index.md",
            "reference/exceptions.md",
            "explanation/design.md",
            "changelog.md",
        )
    ]
    assert positions == sorted(positions)
