"""Tests for config loading, the provider registry, and the pipeline."""
from __future__ import annotations

import pytest

from valuation.config import load_assumptions
from valuation.data import get_provider
from valuation.data.base import DataError
from valuation.data.fmp_provider import FMPProvider
from valuation.model.assumptions import Assumptions
from valuation.model.dcf import DCFValuation
from valuation.model.three_statement import ThreeStatementModel


def test_default_config_loads():
    a = load_assumptions()
    assert isinstance(a, Assumptions)
    assert a.forecast_years >= 1


def test_assumptions_reject_unknown_keys():
    with pytest.raises(ValueError):
        Assumptions.from_dict({"not_a_real_key": 1})


def test_assumptions_series_length_validation():
    a = Assumptions(forecast_years=5, revenue_growth=[0.1, 0.1])
    with pytest.raises(ValueError):
        a.series("revenue_growth", 0.06)


def test_provider_registry():
    assert get_provider("yfinance").name == "yfinance"
    with pytest.raises(ValueError):
        get_provider("does_not_exist")


def test_fmp_requires_key():
    with pytest.raises(DataError):
        FMPProvider(api_key="").fetch("AAPL")


def test_end_to_end_with_stub(stub_provider, assumptions):
    financials = stub_provider.fetch("TEST")
    model = ThreeStatementModel(financials, assumptions).build()
    result = DCFValuation(model).run()
    assert result.implied_share_price > 0
    assert result.shares_outstanding == financials.shares_outstanding
