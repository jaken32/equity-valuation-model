"""High-level orchestration: ticker in, valuation out."""
from __future__ import annotations

from dataclasses import dataclass

from .data import CompanyFinancials, get_provider
from .model.assumptions import Assumptions
from .model.dcf import DCFResult, DCFValuation
from .model.three_statement import ThreeStatementModel


@dataclass
class ValuationRun:
    """Everything produced by a single end-to-end valuation."""

    financials: CompanyFinancials
    model: ThreeStatementModel
    result: DCFResult


def value_ticker(ticker: str, assumptions: Assumptions | None = None,
                 provider: str = "yfinance", **provider_kwargs) -> ValuationRun:
    """Fetch ``ticker``, build the three-statement model, and run the DCF.

    Parameters
    ----------
    ticker:
        Equity symbol, e.g. ``"AAPL"``.
    assumptions:
        Forecast drivers; defaults to :class:`Assumptions` defaults.
    provider:
        Data provider name (``"yfinance"`` or ``"fmp"``).
    """
    assumptions = assumptions or Assumptions()
    data_provider = get_provider(provider, **provider_kwargs)
    financials = data_provider.fetch(ticker)

    model = ThreeStatementModel(financials, assumptions).build()
    result = DCFValuation(model).run()
    return ValuationRun(financials=financials, model=model, result=result)
