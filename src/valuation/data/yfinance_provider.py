"""Default, zero-configuration data provider backed by Yahoo Finance.

Yahoo's line-item labels are inconsistent across tickers and change over time,
so every field is resolved against a list of candidate labels with explicit
fallbacks rather than a single hardcoded key.
"""
from __future__ import annotations

from typing import Iterable

from .base import CompanyFinancials, DataError, DataProvider

_MM = 1e-6  # raw currency units -> millions


def _first(series_index: Iterable[str], *candidates: str) -> str | None:
    labels = list(series_index)
    for candidate in candidates:
        for label in labels:
            if label.lower() == candidate.lower():
                return label
    return None


class YFinanceProvider(DataProvider):
    """Fetch statements via the ``yfinance`` package (no API key required)."""

    name = "yfinance"

    def fetch(self, ticker: str) -> CompanyFinancials:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise DataError(
                "yfinance is not installed. Run: pip install yfinance"
            ) from exc

        tk = yf.Ticker(ticker)
        income = tk.income_stmt
        balance = tk.balance_sheet
        cashflow = tk.cashflow
        if income is None or income.empty or balance is None or balance.empty:
            raise DataError(f"No statement data returned for '{ticker}'.")

        col_i = income.columns[0]
        col_b = balance.columns[0]
        col_c = cashflow.columns[0] if cashflow is not None and not cashflow.empty else None

        def g(frame, col, *candidates, default=0.0) -> float:
            if frame is None or frame.empty or col is None:
                return default
            label = _first(frame.index, *candidates)
            if label is None:
                return default
            value = frame.loc[label, col]
            try:
                return float(value) if value == value else default  # NaN check
            except (TypeError, ValueError):
                return default

        revenue = g(income, col_i, "Total Revenue", "Operating Revenue")
        cogs = g(income, col_i, "Cost Of Revenue", "Cost Of Goods Sold",
                 default=revenue - g(income, col_i, "Gross Profit", default=revenue))
        da = g(cashflow, col_c, "Depreciation And Amortization",
               "Depreciation Amortization Depletion") or g(
            income, col_i, "Reconciled Depreciation")
        sga = g(income, col_i, "Selling General And Administration",
                "Selling General And Administrative") + g(
            income, col_i, "Research And Development")
        if sga == 0.0:
            # Back into operating expense from EBIT when components are absent.
            ebit = g(income, col_i, "Operating Income", "EBIT")
            sga = max(revenue - cogs - da - ebit, 0.0)

        pretax = g(income, col_i, "Pretax Income", "Pre Tax Income",
                   default=g(income, col_i, "Net Income"))
        tax = g(income, col_i, "Tax Provision", "Income Tax Expense")
        net_income = g(income, col_i, "Net Income",
                       "Net Income Common Stockholders")
        interest = abs(g(income, col_i, "Interest Expense",
                         "Interest Expense Non Operating"))

        info = self._safe_info(tk)
        price = self._price(tk, info)
        shares = self._shares(tk, info)
        beta = float(info.get("beta") or 1.0)

        fy = getattr(col_i, "year", None) or 0

        snapshot = CompanyFinancials(
            ticker=ticker.upper(),
            name=info.get("longName") or info.get("shortName") or ticker.upper(),
            currency=info.get("financialCurrency") or "USD",
            fiscal_year=int(fy),
            revenue=revenue * _MM,
            cogs=cogs * _MM,
            sga=sga * _MM,
            depreciation_amortization=da * _MM,
            interest_expense=interest * _MM,
            tax_expense=tax * _MM,
            pretax_income=pretax * _MM,
            net_income=net_income * _MM,
            cash=g(balance, col_b, "Cash And Cash Equivalents",
                   "Cash Cash Equivalents And Short Term Investments") * _MM,
            accounts_receivable=g(balance, col_b, "Accounts Receivable",
                                  "Receivables") * _MM,
            inventory=g(balance, col_b, "Inventory") * _MM,
            net_ppe=g(balance, col_b, "Net PPE", "Net Property Plant Equipment") * _MM,
            accounts_payable=g(balance, col_b, "Accounts Payable", "Payables") * _MM,
            total_debt=g(balance, col_b, "Total Debt",
                         default=(g(balance, col_b, "Long Term Debt")
                                  + g(balance, col_b, "Current Debt"))) * _MM,
            total_equity=g(balance, col_b, "Stockholders Equity",
                           "Total Equity Gross Minority Interest") * _MM,
            capex=abs(g(cashflow, col_c, "Capital Expenditure",
                        "Purchase Of PPE")) * _MM,
            share_price=price,
            shares_outstanding=shares,
            beta=beta if beta > 0 else 1.0,
            revenue_history=self._revenue_history(income),
        )
        snapshot.validate()
        return snapshot

    @staticmethod
    def _safe_info(tk) -> dict:
        try:
            return tk.info or {}
        except Exception:  # pragma: no cover - network/library variability
            return {}

    @staticmethod
    def _price(tk, info: dict) -> float:
        try:
            price = tk.fast_info.get("last_price")
            if price:
                return float(price)
        except Exception:  # pragma: no cover
            pass
        return float(info.get("currentPrice") or info.get("previousClose") or 0.0)

    @staticmethod
    def _shares(tk, info: dict) -> float:
        try:
            shares = tk.fast_info.get("shares")
            if shares:
                return float(shares) * _MM
        except Exception:  # pragma: no cover
            pass
        return float(info.get("sharesOutstanding") or 0.0) * _MM

    @staticmethod
    def _revenue_history(income) -> dict[int, float]:
        label = _first(income.index, "Total Revenue", "Operating Revenue")
        if label is None:
            return {}
        history = {}
        for col in income.columns:
            try:
                history[int(col.year)] = float(income.loc[label, col]) * _MM
            except (TypeError, ValueError, AttributeError):
                continue
        return history
