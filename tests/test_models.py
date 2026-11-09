"""Tests for indianfinance.models (T-008). Typed: also checked by mypy --strict."""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import pickle
import typing
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

import indianfinance
import indianfinance.models as models
from indianfinance.models import (
    Cashflow,
    EodPrice,
    NavRecord,
    PricePoint,
    RollingReturn,
    Scheme,
)

_DAY = dt.date(2026, 11, 6)
_EARLIER = dt.date(2026, 11, 4)
_NAV: dict[str, Any] = {
    "amfi_code": "135763",
    "scheme_name": "Axis Children's Fund",
    "plan": "Direct Plan",
    "option": "IDCW Option",
    "isin": "INF846K01WS2",
    "isin_reinvestment": "INF846K01WQ6",
    "date": _DAY,
    "nav": Decimal("28.3978"),
}
_SCHEME: dict[str, Any] = {
    "amfi_code": "135763",
    "scheme_name": "Axis Children's Fund",
    "plan": "Direct Plan",
    "option": "IDCW Option",
    "isin": "INF846K01WS2",
    "isin_reinvestment": None,
    "amc": "Axis Mutual Fund",
    "scheme_type": "Open Ended Schemes",
    "category": "Debt Scheme - Gilt Fund",
}
_EOD: dict[str, Any] = {
    "symbol": "INFY",
    "series": "EQ",
    "isin": "INE009A01021",
    "date": _DAY,
    "open": Decimal("1500.00"),
    "high": Decimal("1520.50"),
    "low": Decimal("1490.25"),
    "close": Decimal("1510.75"),
    "prev_close": Decimal("1498.00"),
    "volume": 1234567,
    "traded_value": Decimal("1864000000.50"),
}
_CASH: dict[str, Any] = {"date": _DAY, "amount": Decimal("-5000")}
_ROLL: dict[str, Any] = {"start": _EARLIER, "end": _DAY, "start_value": Decimal("100")}
_ROLL |= {"end_value": Decimal("110"), "cagr": Decimal("0.1")}

# (class, constructor kwargs, one changed field)
_CASES: list[tuple[type[Any], dict[str, Any], dict[str, Any]]] = [
    (NavRecord, _NAV, {"nav": Decimal("1")}),
    (Scheme, _SCHEME, {"amc": "Other Mutual Fund"}),
    (EodPrice, _EOD, {"volume": 1}),
    (Cashflow, _CASH, {"amount": Decimal("1")}),
    (RollingReturn, _ROLL, {"cagr": Decimal("1")}),
]
_IDS = [case[0].__name__ for case in _CASES]
_each_model = pytest.mark.parametrize(("cls", "kw", "change"), _CASES, ids=_IDS)


def _latest(points: Sequence[PricePoint]) -> Decimal:
    return max(points, key=lambda p: p.date).value


if TYPE_CHECKING:
    _latest([Cashflow(_DAY, Decimal("1"))])  # type: ignore[list-item]  # AC10


@_each_model
def test_model_fields_are_exact(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC1: dict order of kw is the spec field order
    assert [f.name for f in dataclasses.fields(cls)] == list(kw)


@_each_model
def test_model_fields_have_no_defaults(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC1
    for f in dataclasses.fields(cls):
        assert f.default is dataclasses.MISSING
        assert f.default_factory is dataclasses.MISSING


@_each_model
def test_model_rejects_field_assignment(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC2
    name = next(iter(kw))
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(cls(**kw), name, kw[name])


@_each_model
def test_model_rejects_new_attribute(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC2. CPython 3.12 raises TypeError here (frozen + slots dataclass bug in
    # its generated __setattr__); newer versions raise AttributeError.
    with pytest.raises((AttributeError, TypeError)):
        setattr(cls(**kw), "foo", 1)  # noqa: B010


@_each_model
def test_model_has_slots_not_dict(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC2
    assert not hasattr(cls(**kw), "__dict__")
    assert list(cls.__slots__) == list(kw)


@pytest.mark.parametrize(
    ("cls", "kw"), [c[:2] for c in _CASES[:3] + _CASES[4:]], ids=_IDS[:3] + _IDS[4:]
)
def test_source_models_reject_positional_args(
    cls: type[Any], kw: dict[str, Any]
) -> None:
    # AC3
    with pytest.raises(TypeError):
        cls(*kw.values())


@_each_model
def test_model_requires_every_field(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC3
    for name in kw:
        with pytest.raises(TypeError):
            cls(**{k: v for k, v in kw.items() if k != name})


def test_cashflow_accepts_positional_and_keyword_args() -> None:
    # AC3
    amount = Decimal("-5000")
    assert Cashflow(_DAY, amount) == Cashflow(date=_DAY, amount=amount)


def test_nav_record_value_is_nav() -> None:
    # AC4
    rec = NavRecord(**_NAV)
    assert rec.value is rec.nav


def test_eod_price_value_is_close() -> None:
    # AC4
    bar = EodPrice(**_EOD)
    assert bar.value is bar.close


@_each_model
def test_value_is_not_a_field(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC4
    assert "value" not in [f.name for f in dataclasses.fields(cls)]
    assert "value" not in dataclasses.asdict(cls(**kw))


def test_model_keeps_decimal_date_and_int_unchanged() -> None:
    # AC5
    rec = NavRecord(**_NAV)
    assert rec.nav == Decimal("28.3978")
    assert str(rec.nav) == "28.3978"
    assert rec.date is _DAY
    bar = EodPrice(**_EOD)
    assert type(bar.volume) is int
    assert str(bar.open) == "1500.00"


def test_optional_amfi_fields_accept_none() -> None:
    # AC5
    rec = NavRecord(
        **{
            **_NAV,
            "plan": None,
            "option": None,
            "isin": None,
            "isin_reinvestment": None,
        }
    )
    assert (rec.plan, rec.option, rec.isin, rec.isin_reinvestment) == (None,) * 4
    assert Scheme(**_SCHEME).isin_reinvestment is None


@_each_model
def test_equal_models_are_equal_and_hash_the_same(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC6
    a, b = cls(**kw), cls(**kw)
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


@_each_model
def test_models_differ_when_one_field_differs(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC6
    assert cls(**kw) != cls(**{**kw, **change})


@_each_model
def test_models_have_no_ordering(
    cls: type[Any], kw: dict[str, Any], change: dict[str, Any]
) -> None:
    # AC6
    with pytest.raises(TypeError):
        _ = cls(**kw) < cls(**{**kw, **change})


def test_models_sort_by_key() -> None:
    # AC6
    late, early = NavRecord(**_NAV), NavRecord(**{**_NAV, "date": _EARLIER})
    assert sorted([late, early], key=lambda r: r.date) == [early, late]


def _via_pickle(x: Any) -> Any:
    return pickle.loads(pickle.dumps(x))


@pytest.mark.parametrize(
    "how", [_via_pickle, copy.copy, copy.deepcopy], ids=["pickle", "copy", "deepcopy"]
)
@_each_model
def test_model_survives_pickle_and_copy(
    cls: type[Any],
    kw: dict[str, Any],
    change: dict[str, Any],
    how: Callable[[Any], Any],
) -> None:
    # AC7
    original = cls(**kw)
    result = how(original)
    assert type(result) is cls
    assert result == original


def test_price_point_is_a_protocol_with_properties() -> None:
    # AC8
    assert typing.Protocol in PricePoint.__mro__
    assert getattr(PricePoint, "_is_protocol", False) is True
    for name in ("date", "value"):
        assert isinstance(PricePoint.__dict__[name], property)


def test_price_point_is_not_runtime_checkable() -> None:
    # AC8
    with pytest.raises(TypeError):
        isinstance(NavRecord(**_NAV), PricePoint)  # type: ignore[misc]


def test_price_point_helper_accepts_nav_records_and_eod_prices() -> None:
    # AC8, AC10
    navs = [
        NavRecord(**{**_NAV, "date": _EARLIER, "nav": Decimal("1")}),
        NavRecord(**_NAV),
    ]
    bars = [EodPrice(**{**_EOD, "date": _EARLIER}), EodPrice(**_EOD)]
    assert _latest(navs) == Decimal("28.3978")
    assert _latest(bars) == Decimal("1510.75")


def test_models_module_public_names() -> None:
    # AC9
    assert models.__all__ == [
        "Cashflow",
        "EodPrice",
        "NavRecord",
        "PricePoint",
        "RollingReturn",
        "Scheme",
    ]
    assert indianfinance.__all__ == ["__version__"]


def test_nav_record_with_all_optional_fields_none_survives_pickle() -> None:
    # AC5, AC7
    rec = NavRecord(
        **{
            **_NAV,
            "plan": None,
            "option": None,
            "isin": None,
            "isin_reinvestment": None,
        }
    )
    assert _via_pickle(rec) == rec


def test_decimals_with_different_exponents_compare_and_hash_equal() -> None:
    # Edge case: Decimal("28.30") == Decimal("28.3"); str() keeps the digits
    a = NavRecord(**{**_NAV, "nav": Decimal("28.30")})
    b = NavRecord(**{**_NAV, "nav": Decimal("28.3")})
    assert a == b
    assert hash(a) == hash(b)
    assert str(a.nav) == "28.30"
