"""Tests for the DCF valuation."""
from __future__ import annotations

import math

import pytest

from valuation.model.assumptions import Assumptions
from valuation.model.dcf import DCFValuation
from valuation.model.three_statement import ThreeStatementModel


def _run(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    return DCFValuation(model).run()


def test_wacc_between_debt_and_equity_cost(financials, assumptions):
    model = ThreeStatementModel(financials, assumptions).build()
    dcf = DCFValuation(model)
    wacc = dcf.wacc()
    assert dcf.after_tax_cost_of_debt() < wacc < dcf.cost_of_equity()


def test_enterprise_value_decomposes(financials, assumptions):
    result = _run(financials, assumptions)
    assert math.isclose(
        result.enterprise_value,
        result.pv_explicit_fcf + result.pv_terminal_value,
        rel_tol=1e-9)


def test_equity_bridge(financials, assumptions):
    result = _run(financials, assumptions)
    assert math.isclose(
        result.equity_value,
        result.enterprise_value - result.net_debt,
        rel_tol=1e-9)
    assert math.isclose(
        result.implied_share_price,
        result.equity_value / result.shares_outstanding,
        rel_tol=1e-9)


def test_higher_wacc_lowers_value(financials):
    low = _run(financials, Assumptions(beta_override=0.8))
    high = _run(financials, Assumptions(beta_override=1.6))
    assert high.wacc > low.wacc
    assert high.implied_share_price < low.implied_share_price


def test_terminal_growth_must_be_below_wacc(financials):
    bad = Assumptions(terminal_growth=0.09, beta_override=0.2,
                      risk_free_rate=0.01, equity_risk_premium=0.02)
    model = ThreeStatementModel(financials, bad).build()
    with pytest.raises(ValueError):
        DCFValuation(model).run()


def test_exit_multiple_terminal_value(financials):
    a = Assumptions(exit_ev_ebitda=10.0)
    result = _run(financials, a)
    assert result.terminal_value > 0
    # Exit-multiple TV should equal 10x final-year EBITDA.
    model = ThreeStatementModel(financials, a).build()
    ebitda_last = model.income_statement.loc["EBITDA"].iloc[-1]
    assert math.isclose(result.terminal_value, 10.0 * ebitda_last, rel_tol=1e-9)


def test_sensitivity_grid_dimensions(financials, assumptions):
    result = _run(financials, assumptions)
    assert result.sensitivity.shape == (
        len(assumptions.wacc_sensitivity), len(assumptions.growth_sensitivity))
