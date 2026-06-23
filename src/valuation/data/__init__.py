"""Data providers and the snapshot type they produce."""
from __future__ import annotations

from .base import CompanyFinancials, DataError, DataProvider
from .yfinance_provider import YFinanceProvider
from .fmp_provider import FMPProvider

_REGISTRY: dict[str, type[DataProvider]] = {
    YFinanceProvider.name: YFinanceProvider,
    FMPProvider.name: FMPProvider,
}


def get_provider(name: str = "yfinance", **kwargs) -> DataProvider:
    """Instantiate a registered provider by name."""
    try:
        provider_cls = _REGISTRY[name.lower()]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown provider '{name}'. Available: {available}.")
    return provider_cls(**kwargs)


__all__ = [
    "CompanyFinancials",
    "DataError",
    "DataProvider",
    "YFinanceProvider",
    "FMPProvider",
    "get_provider",
]
