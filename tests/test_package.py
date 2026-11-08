"""Smoke tests for packaging: version, py.typed, dependencies and pytest config."""

import importlib.metadata
import importlib.resources
import re

import pytest

_NAME_END = re.compile(r"[<>=!~;\[ ]")


_EXTRA_MARKER = re.compile(r"extra\s*==\s*['\"]([^'\"]+)['\"]")


def _extra_of(requirement: str) -> str | None:
    """The extra a requirement belongs to, or None for a runtime requirement."""
    match = _EXTRA_MARKER.search(requirement)
    return match.group(1) if match else None


def _requirement_names(*, extra: str | None) -> set[str]:
    """Names of requirements for one extra (or the runtime set if extra is None)."""
    requires = importlib.metadata.requires("indianfinance") or []
    return {
        _NAME_END.split(req, maxsplit=1)[0]
        for req in requires
        if _extra_of(req) == extra
    }


# AC3
def test_version_matches_installed_metadata() -> None:
    import indianfinance

    assert isinstance(indianfinance.__version__, str)
    assert indianfinance.__version__ != ""
    assert indianfinance.__version__ == importlib.metadata.version("indianfinance")


# AC3
def test_public_names_are_only_version() -> None:
    import indianfinance

    assert indianfinance.__all__ == ["__version__"]


# AC1, AC8
def test_package_ships_py_typed_marker() -> None:
    marker = importlib.resources.files("indianfinance").joinpath("py.typed")

    assert marker.is_file()


# AC4
def test_runtime_requires_only_httpx() -> None:
    assert _requirement_names(extra=None) == {"httpx"}


# AC4
def test_pandas_extra_requires_only_pandas() -> None:
    assert _requirement_names(extra="pandas") == {"pandas"}


# AC10
def test_requires_python_is_3_12_or_newer() -> None:
    meta = importlib.metadata.metadata("indianfinance")

    assert meta["Requires-Python"] == ">=3.12"


# AC7
def test_live_marker_is_registered(pytestconfig: pytest.Config) -> None:
    markers = pytestconfig.getini("markers")

    assert any(m.startswith("live:") for m in markers)


# AC7
def test_default_run_excludes_live_tests(pytestconfig: pytest.Config) -> None:
    addopts = list(pytestconfig.getini("addopts"))

    assert "-m" in addopts
    assert addopts[addopts.index("-m") + 1] == "not live"


# AC7
def test_strict_markers_enabled(pytestconfig: pytest.Config) -> None:
    assert "--strict-markers" in pytestconfig.getini("addopts")
