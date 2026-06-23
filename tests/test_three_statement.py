"""Tests for the three-statement projection."""
from __future__ import annotations

from valuation.model.three_statement import ThreeStatementModel


def test_projection_has_expected_shape(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    assert model.income_statement.shape[1] == assumptions.forecast_years
    assert model.balance_sheet.shape[1] == assumptions.forecast_years
    assert model.cash_flow_statement.shape[1] == assumptions.forecast_years


def test_balance_sheet_ties_out(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    imbalance = model.balance_check()
    assert (imbalance < 1e-3).all(), f"balance sheet imbalance: {imbalance.to_dict()}"


def test_revenue_grows_at_assumed_rate(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    revenue = model.income_statement.loc["Revenue"]
    first_year = revenue.iloc[0]
    assert abs(first_year - financials.revenue * 1.06) < 1e-6
    # Compounding holds across the horizon.
    ratio = revenue.iloc[1] / revenue.iloc[0]
    assert abs(ratio - 1.06) < 1e-6


def test_per_year_assumption_lists(financials):
    from valuation.model.assumptions import Assumptions

    a = Assumptions(forecast_years=3, revenue_growth=[0.10, 0.05, 0.00])
    model = ThreeStatementModel(financials, a).build()
    revenue = model.income_statement.loc["Revenue"]
    assert abs(revenue.iloc[0] / financials.revenue - 1.10) < 1e-6
    assert abs(revenue.iloc[2] / revenue.iloc[1] - 1.00) < 1e-6


def test_ppe_rolls_forward(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    ppe = model.balance_sheet.loc["Net PP&E"]
    income = model.income_statement
    cfs = model.cash_flow_statement
    # PP&E change equals capex minus depreciation.
    delta = ppe.iloc[0] - financials.net_ppe
    expected = -cfs.loc["Capex"].iloc[0] - income.loc["D&A"].iloc[0]
    assert abs(delta - expected) < 1e-6


def test_fcff_is_positive_for_profitable_base(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    fcf = model.free_cash_flow_to_firm()
    assert (fcf > 0).all()
