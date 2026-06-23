"""Linked three-statement projection.

Builds an integrated income statement, balance sheet and cash-flow statement
that articulate: cash is solved from the cash-flow statement and flows to the
balance sheet, retained earnings roll forward through net income, and net PP&E
rolls forward through capex less depreciation. The balance sheet therefore ties
out by construction each period; :meth:`balance_check` verifies this
numerically.
"""
from __future__ import annotations

import pandas as pd

from ..data.base import CompanyFinancials
from .assumptions import Assumptions

_DAYS = 365.0


class ThreeStatementModel:
    """Project integrated financial statements from a base-year snapshot."""

    def __init__(self, financials: CompanyFinancials, assumptions: Assumptions) -> None:
        self.fin = financials
        self.a = assumptions
        self._income: pd.DataFrame | None = None
        self._balance: pd.DataFrame | None = None
        self._cashflow: pd.DataFrame | None = None

    # -- public surface ---------------------------------------------------
    def build(self) -> "ThreeStatementModel":
        """Run the projection and populate the three statement frames."""
        f, a = self.fin, self.a
        years = list(range(f.fiscal_year + 1, f.fiscal_year + 1 + a.forecast_years))

        # Base-year ratios used as defaults where assumptions are None.
        base_gross_margin = f.gross_profit / f.revenue
        base_sga_pct = f.sga / f.revenue
        base_da_pct = f.depreciation_amortization / f.revenue
        base_capex_pct = (f.capex / f.revenue) if f.capex else base_da_pct
        base_dso = self._days(f.accounts_receivable, f.revenue)
        base_dio = self._days(f.inventory, f.cogs)
        base_dpo = self._days(f.accounts_payable, f.cogs)
        tax_rate = a.tax_rate if a.tax_rate is not None else f.effective_tax_rate
        cost_of_debt = (a.cost_of_debt if a.cost_of_debt is not None
                        else self._implied_cost_of_debt())

        growth = a.series("revenue_growth", 0.06)
        gm = a.series("gross_margin", base_gross_margin)
        sga_pct = a.series("sga_pct_revenue", base_sga_pct)
        da_pct = a.series("da_pct_revenue", base_da_pct)
        capex_pct = a.series("capex_pct_revenue", base_capex_pct)
        dso = a.days_sales_outstanding if a.days_sales_outstanding is not None else base_dso
        dio = a.days_inventory_outstanding if a.days_inventory_outstanding is not None else base_dio
        dpo = a.days_payable_outstanding if a.days_payable_outstanding is not None else base_dpo

        # The model itemizes only the major balance-sheet drivers. Everything
        # else (goodwill, intangibles, other assets/liabilities, minority
        # interest, etc.) is captured as a single constant "other net assets"
        # plug set so the base period balances; because all modeled flows tie
        # out period to period, the balance sheet then ties out every year.
        other_net_assets = (
            f.accounts_payable + f.total_debt + f.total_equity
            - f.cash - f.accounts_receivable - f.inventory - f.net_ppe)

        inc, bal, cfs = {}, {}, {}
        prev_rev = f.revenue
        prev_ar, prev_inv, prev_ap = f.accounts_receivable, f.inventory, f.accounts_payable
        prev_ppe, prev_cash = f.net_ppe, f.cash
        prev_debt, prev_equity = f.total_debt, f.total_equity

        for t, year in enumerate(years):
            revenue = prev_rev * (1 + growth[t])
            cogs = revenue * (1 - gm[t])
            gross = revenue - cogs
            sga = revenue * sga_pct[t]
            da = revenue * da_pct[t]
            ebit = gross - sga - da
            debt = max(prev_debt - a.annual_debt_repayment, 0.0)
            interest = cost_of_debt * ((prev_debt + debt) / 2.0)
            pretax = ebit - interest
            taxes = max(pretax, 0.0) * tax_rate
            net_income = pretax - taxes

            ar = dso / _DAYS * revenue
            inv = dio / _DAYS * cogs
            ap = dpo / _DAYS * cogs
            change_nwc = (ar - prev_ar) + (inv - prev_inv) - (ap - prev_ap)

            capex = revenue * capex_pct[t]
            ppe = prev_ppe + capex - da

            dividends = max(net_income, 0.0) * a.dividend_payout_ratio
            cfo = net_income + da - change_nwc
            cfi = -capex
            cff = (debt - prev_debt) - dividends
            net_change_cash = cfo + cfi + cff
            cash = prev_cash + net_change_cash
            equity = prev_equity + net_income - dividends

            inc[year] = {
                "Revenue": revenue, "COGS": cogs, "Gross Profit": gross,
                "SG&A": sga, "D&A": da, "EBIT": ebit,
                "Interest Expense": interest, "Pretax Income": pretax,
                "Taxes": taxes, "Net Income": net_income,
                "EBITDA": ebit + da,
            }
            bal[year] = {
                "Cash": cash, "Accounts Receivable": ar, "Inventory": inv,
                "Net PP&E": ppe, "Other Net Assets": other_net_assets,
                "Total Assets": cash + ar + inv + ppe + other_net_assets,
                "Accounts Payable": ap, "Total Debt": debt,
                "Total Equity": equity,
                "Total Liab. & Equity": ap + debt + equity,
            }
            cfs[year] = {
                "Net Income": net_income, "D&A": da, "Change in NWC": -change_nwc,
                "Cash from Operations": cfo, "Capex": cfi,
                "Cash from Investing": cfi, "Debt Issuance/(Repayment)": debt - prev_debt,
                "Dividends": -dividends, "Cash from Financing": cff,
                "Net Change in Cash": net_change_cash, "Ending Cash": cash,
            }

            prev_rev, prev_ar, prev_inv, prev_ap = revenue, ar, inv, ap
            prev_ppe, prev_cash, prev_debt, prev_equity = ppe, cash, debt, equity

        self._income = pd.DataFrame(inc)
        self._balance = pd.DataFrame(bal)
        self._cashflow = pd.DataFrame(cfs)
        return self

    @property
    def income_statement(self) -> pd.DataFrame:
        return self._require(self._income)

    @property
    def balance_sheet(self) -> pd.DataFrame:
        return self._require(self._balance)

    @property
    def cash_flow_statement(self) -> pd.DataFrame:
        return self._require(self._cashflow)

    def balance_check(self, tolerance: float = 1e-6) -> pd.Series:
        """Return per-year assets minus liabilities-plus-equity (~0 expected)."""
        bs = self.balance_sheet
        diff = bs.loc["Total Assets"] - bs.loc["Total Liab. & Equity"]
        return diff.abs().where(diff.abs() > tolerance, 0.0)

    def free_cash_flow_to_firm(self) -> pd.Series:
        """Unlevered FCF = EBIT*(1-tax) + D&A - Capex - change in NWC."""
        inc = self.income_statement
        cfs = self.cash_flow_statement
        tax_rate = (self.a.tax_rate if self.a.tax_rate is not None
                    else self.fin.effective_tax_rate)
        nopat = inc.loc["EBIT"] * (1 - tax_rate)
        # cfs "Change in NWC" is stored as a cash effect (negative when NWC grows)
        return nopat + inc.loc["D&A"] + cfs.loc["Capex"] + cfs.loc["Change in NWC"]

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _days(balance_item: float, flow: float) -> float:
        return (balance_item / flow * _DAYS) if flow else 45.0

    def _implied_cost_of_debt(self) -> float:
        if self.fin.total_debt > 0 and self.fin.interest_expense > 0:
            return min(self.fin.interest_expense / self.fin.total_debt, 0.12)
        return 0.05

    @staticmethod
    def _require(frame: pd.DataFrame | None) -> pd.DataFrame:
        if frame is None:
            raise RuntimeError("Call build() before accessing statements.")
        return frame
