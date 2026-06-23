"""Shared fixtures. Tests use a synthetic provider so they run offline and
deterministically, without touching any network data source.
"""
from __future__ import annotations

import pytest

from valuation.data.base import CompanyFinancials, DataProvider
from valuation.model.assumptions import Assumptions


class StubProvider(DataProvider):
    """Returns a fixed, internally consistent snapshot for any ticker."""

    name = "stub"

    def fetch(self, ticker: str) -> CompanyFinancials:
        return make_financials(ticker)


def make_financials(ticker: str = "TEST") -> CompanyFinancials:
    """A clean, balanced base-year snapshot (figures in millions)."""
    return CompanyFinancials(
        ticker=ticker.upper(),
        name="Test Corp",
        currency="USD",
        fiscal_year=2025,
        revenue=10_000.0,
        cogs=6_000.0,
        sga=2_000.0,
        depreciation_amortization=500.0,
        interest_expense=120.0,
        tax_expense=294.0,            # 21% of pretax 1,380
        pretax_income=1_380.0,
        net_income=1_086.0,
        cash=1_500.0,
        accounts_receivable=1_200.0,
        inventory=900.0,
        net_ppe=5_000.0,
        accounts_payable=800.0,
        total_debt=3_000.0,
        total_equity=4_800.0,
        capex=600.0,
        share_price=50.0,
        shares_outstanding=200.0,
        beta=1.1,
        revenue_history={2023: 8_500.0, 2024: 9_200.0, 2025: 10_000.0},
    )


@pytest.fixture
def financials() -> CompanyFinancials:
    return make_financials()


@pytest.fixture
def assumptions() -> Assumptions:
    return Assumptions(forecast_years=5, revenue_growth=0.06)


@pytest.fixture
def stub_provider() -> StubProvider:
    return StubProvider()
