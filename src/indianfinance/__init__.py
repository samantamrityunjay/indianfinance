"""Indian market end-of-day (EOD) data from official sources."""

from importlib.metadata import version as _version

__all__ = ["__version__"]

__version__: str = _version("indianfinance")
"""The installed package version, for example `"0.1.0.dev0"`."""
