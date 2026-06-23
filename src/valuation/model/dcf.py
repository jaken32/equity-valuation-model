"""Discounted cash-flow valuation built on the three-statement projection.

Discounts unlevered free cash flow at the WACC, adds a terminal value (Gordon
growth by default, or an exit EV/EBITDA multiple), bridges enterprise value to
equity value via net debt, and produces a WACC x terminal-growth sensitivity
grid.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..data.base import CompanyFinancials
from .assumptions import Assumptions
from .three_statement import ThreeStatementModel


@dataclass
class DCFResult:
    """Outputs of a DCF run."""

    wacc: float
    cost_of_equity: float
    cost_of_debt_after_tax: float
    enterprise_value: float
    terminal_value: float
    pv_terminal_value: float
    pv_explicit_fcf: float
    terminal_value_pct: float
    equity_value: float
    net_debt: float
    shares_outstanding: float
    implied_share_price: float
    current_share_price: float
    upside: float
    fcf: pd.Series
    discount_factors: pd.Series
    sensitivity: pd.DataFrame

    def summary(self) -> dict[str, float]:
        return {
            "WACC": self.wacc,
            "Enterprise Value": self.enterprise_value,
            "Equity Value": self.equity_value,
            "Implied Share Price": self.implied_share_price,
            "Current Share Price": self.current_share_price,
            "Upside / (Downside)": self.upside,
            "Terminal Value % of EV": self.terminal_value_pct,
        }


class DCFValuation:
    """Compute a DCF valuation from a built :class:`ThreeStatementModel`."""

    def __init__(self, model: ThreeStatementModel) -> None:
        self.model = model
        self.fin: CompanyFinancials = model.fin
        self.a: Assumptions = model.a

    # -- WACC -------------------------------------------------------------
    def cost_of_equity(self) -> float:
        beta = self.a.beta_override if self.a.beta_override is not None else self.fin.beta
        return self.a.risk_free_rate + beta * self.a.equity_risk_premium

    def after_tax_cost_of_debt(self) -> float:
        tax_rate = (self.a.tax_rate if self.a.tax_rate is not None
                    else self.fin.effective_tax_rate)
        kd = (self.a.cost_of_debt if self.a.cost_of_debt is not None
              else self.model._implied_cost_of_debt())
        return kd * (1 - tax_rate)

    def wacc(self) -> float:
        equity = self.fin.market_cap
        debt = self.fin.total_debt
        total = equity + debt
        if total <= 0:
            return self.cost_of_equity()
        we, wd = equity / total, debt / total
        return we * self.cost_of_equity() + wd * self.after_tax_cost_of_debt()

    # -- valuation --------------------------------------------------------
    def run(self) -> DCFResult:
        wacc = self.wacc()
        fcf = self.model.free_cash_flow_to_firm()
        ev, tv, pv_tv, pv_explicit, factors = self._enterprise_value(fcf, wacc)

        net_debt = self.fin.net_debt
        equity_value = ev - net_debt
        shares = self.fin.shares_outstanding
        implied = equity_value / shares if shares else float("nan")
        current = self.fin.share_price

        return DCFResult(
            wacc=wacc,
            cost_of_equity=self.cost_of_equity(),
            cost_of_debt_after_tax=self.after_tax_cost_of_debt(),
            enterprise_value=ev,
            terminal_value=tv,
            pv_terminal_value=pv_tv,
            pv_explicit_fcf=pv_explicit,
            terminal_value_pct=(pv_tv / ev) if ev else float("nan"),
            equity_value=equity_value,
            net_debt=net_debt,
            shares_outstanding=shares,
            implied_share_price=implied,
            current_share_price=current,
            upside=(implied / current - 1) if current else float("nan"),
            fcf=fcf,
            discount_factors=factors,
            sensitivity=self._sensitivity(fcf),
        )

    # -- internals --------------------------------------------------------
    def _periods(self) -> list[float]:
        n = self.a.forecast_years
        offset = 0.5 if self.a.mid_year_convention else 1.0
        return [t + offset for t in range(n)]

    def _enterprise_value(self, fcf: pd.Series, wacc: float):
        periods = self._periods()
        factors = pd.Series(
            [1.0 / (1 + wacc) ** p for p in periods], index=fcf.index)
        pv_fcf = fcf * factors
        pv_explicit = float(pv_fcf.sum())

        terminal_value = self._terminal_value(fcf, wacc)
        # Terminal value is as of the final explicit year; discount on that period.
        pv_tv = terminal_value * factors.iloc[-1]
        ev = pv_explicit + pv_tv
        return ev, terminal_value, pv_tv, pv_explicit, factors

    def _terminal_value(self, fcf: pd.Series, wacc: float) -> float:
        last_fcf = float(fcf.iloc[-1])
        if self.a.exit_ev_ebitda is not None:
            ebitda_last = float(self.model.income_statement.loc["EBITDA"].iloc[-1])
            return self.a.exit_ev_ebitda * ebitda_last
        g = self.a.terminal_growth
        if wacc <= g:
            raise ValueError(
                f"WACC ({wacc:.2%}) must exceed terminal growth ({g:.2%}).")
        return last_fcf * (1 + g) / (wacc - g)

    def _sensitivity(self, fcf: pd.Series) -> pd.DataFrame:
        base_wacc = self.wacc()
        base_g = self.a.terminal_growth
        net_debt = self.fin.net_debt
        shares = self.fin.shares_outstanding
        periods = self._periods()

        rows, index = [], []
        for dw in self.a.wacc_sensitivity:
            wacc = base_wacc + dw
            index.append(wacc)
            row = []
            for dg in self.a.growth_sensitivity:
                g = base_g + dg
                if wacc <= g:
                    row.append(float("nan"))
                    continue
                factors = [1.0 / (1 + wacc) ** p for p in periods]
                pv_explicit = sum(float(fcf.iloc[i]) * factors[i]
                                  for i in range(len(periods)))
                tv = float(fcf.iloc[-1]) * (1 + g) / (wacc - g)
                ev = pv_explicit + tv * factors[-1]
                price = (ev - net_debt) / shares if shares else float("nan")
                row.append(price)
            rows.append(row)

        return pd.DataFrame(
            rows,
            index=pd.Index([f"{w:.2%}" for w in index], name="WACC"),
            columns=pd.Index([f"{base_g + dg:.2%}" for dg in self.a.growth_sensitivity],
                             name="Terminal g"),
        )
