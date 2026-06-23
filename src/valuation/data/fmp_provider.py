"""Optional data provider backed by Financial Modeling Prep.

Provides cleaner, pre-normalized statements than Yahoo Finance. Requires a free
API key, supplied via the ``FMP_API_KEY`` environment variable or the
constructor.
"""
from __future__ import annotations

import os

from .base import CompanyFinancials, DataError, DataProvider

_BASE = "https://financialmodelingprep.com/api/v3"
_MM = 1e-6


class FMPProvider(DataProvider):
    """Fetch statements via Financial Modeling Prep (API key required)."""

    name = "fmp"

    def __init__(self, api_key: str | None = None, timeout: int = 20) -> None:
        self.api_key = api_key or os.environ.get("FMP_API_KEY", "")
        self.timeout = timeout

    def fetch(self, ticker: str) -> CompanyFinancials:
        if not self.api_key:
            raise DataError(
                "FMP provider requires an API key. Set FMP_API_KEY or pass "
                "api_key=..., or use the default yfinance provider instead."
            )
        try:
            import requests
        except ImportError as exc:  # pragma: no cover
            raise DataError("requests is required for the FMP provider.") from exc

        def get(endpoint: str, **params):
            params["apikey"] = self.api_key
            resp = requests.get(f"{_BASE}/{endpoint}", params=params,
                                timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                raise DataError(f"FMP returned no data for '{ticker}'.")
            return data

        income = get(f"income-statement/{ticker}", limit=5)
        balance = get(f"balance-sheet-statement/{ticker}", limit=1)
        cashflow = get(f"cash-flow-statement/{ticker}", limit=1)
        quote = get(f"quote/{ticker}")[0]
        profile = get(f"profile/{ticker}")[0]

        i, b, c = income[0], balance[0], cashflow[0]

        snapshot = CompanyFinancials(
            ticker=ticker.upper(),
            name=profile.get("companyName", ticker.upper()),
            currency=i.get("reportedCurrency", "USD"),
            fiscal_year=int(str(i.get("calendarYear", "0"))),
            revenue=i["revenue"] * _MM,
            cogs=i["costOfRevenue"] * _MM,
            sga=(i.get("sellingGeneralAndAdministrativeExpenses", 0.0)
                 + i.get("researchAndDevelopmentExpenses", 0.0)) * _MM,
            depreciation_amortization=i.get("depreciationAndAmortization", 0.0) * _MM,
            interest_expense=abs(i.get("interestExpense", 0.0)) * _MM,
            tax_expense=i.get("incomeTaxExpense", 0.0) * _MM,
            pretax_income=i.get("incomeBeforeTax", i.get("netIncome", 0.0)) * _MM,
            net_income=i["netIncome"] * _MM,
            cash=b.get("cashAndCashEquivalents", 0.0) * _MM,
            accounts_receivable=b.get("netReceivables", 0.0) * _MM,
            inventory=b.get("inventory", 0.0) * _MM,
            net_ppe=b.get("propertyPlantEquipmentNet", 0.0) * _MM,
            accounts_payable=b.get("accountPayables", 0.0) * _MM,
            total_debt=b.get("totalDebt", 0.0) * _MM,
            total_equity=b.get("totalStockholdersEquity", 0.0) * _MM,
            capex=abs(c.get("capitalExpenditure", 0.0)) * _MM,
            share_price=float(quote.get("price", 0.0)),
            shares_outstanding=float(quote.get("sharesOutstanding", 0.0)) * _MM,
            beta=float(profile.get("beta") or 1.0),
            revenue_history={
                int(str(row.get("calendarYear", "0"))): row["revenue"] * _MM
                for row in income if row.get("calendarYear")
            },
        )
        snapshot.validate()
        return snapshot
