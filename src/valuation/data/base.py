"""Data layer: a normalized snapshot of company financials and the
provider interface used to obtain it.

The rest of the package depends only on :class:`CompanyFinancials`, never on a
specific data vendor. New sources are added by implementing
:class:`DataProvider`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CompanyFinancials:
    """Most-recent fiscal-year statements plus current market data.

    All monetary values are in millions of the reporting currency. Balance
    sheet items are period-end; income and cash-flow items are full-year.
    """

    ticker: str
    name: str
    currency: str
    fiscal_year: int

    # Income statement
    revenue: float
    cogs: float
    sga: float                 # operating expense excluding D&A
    depreciation_amortization: float
    interest_expense: float
    tax_expense: float
    pretax_income: float
    net_income: float

    # Balance sheet
    cash: float
    accounts_receivable: float
    inventory: float
    net_ppe: float
    accounts_payable: float
    total_debt: float
    total_equity: float

    # Cash flow
    capex: float

    # Market data
    share_price: float
    shares_outstanding: float   # millions
    beta: float

    # Optional history for context, keyed by fiscal year
    revenue_history: dict[int, float] = field(default_factory=dict)

    @property
    def gross_profit(self) -> float:
        return self.revenue - self.cogs

    @property
    def ebit(self) -> float:
        return self.gross_profit - self.sga - self.depreciation_amortization

    @property
    def effective_tax_rate(self) -> float:
        if self.pretax_income == 0:
            return 0.21
        rate = self.tax_expense / self.pretax_income
        # Guard against distortions from one-off items / loss years.
        return min(max(rate, 0.0), 0.45)

    @property
    def market_cap(self) -> float:
        return self.share_price * self.shares_outstanding

    @property
    def net_debt(self) -> float:
        return self.total_debt - self.cash

    def validate(self) -> None:
        """Raise ``ValueError`` if the snapshot is unusable for modeling."""
        if self.revenue <= 0:
            raise ValueError(f"{self.ticker}: non-positive revenue ({self.revenue}).")
        if self.shares_outstanding <= 0:
            raise ValueError(f"{self.ticker}: missing shares outstanding.")
        if self.share_price <= 0:
            raise ValueError(f"{self.ticker}: missing share price.")


class DataProvider(ABC):
    """Interface for a source of :class:`CompanyFinancials`."""

    name: str = "abstract"

    @abstractmethod
    def fetch(self, ticker: str) -> CompanyFinancials:
        """Return a normalized snapshot for ``ticker`` or raise ``DataError``."""


class DataError(RuntimeError):
    """Raised when a provider cannot produce a usable snapshot."""
