"""Forecast drivers and valuation parameters.

Every value here is an explicit, user-editable assumption. Where an assumption
is left as ``None`` the model derives it from the base-year financials so the
projection starts from the company's actual operating profile.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Sequence


@dataclass
class Assumptions:
    """Drivers for the three-statement projection and the DCF.

    Ratio assumptions accept either a single value (held flat across the
    horizon) or a per-year sequence of length ``forecast_years``.
    """

    forecast_years: int = 5

    # --- Operating drivers (None => derive from base year) ---
    revenue_growth: float | Sequence[float] = 0.06
    gross_margin: float | Sequence[float] | None = None
    sga_pct_revenue: float | Sequence[float] | None = None
    da_pct_revenue: float | Sequence[float] | None = None
    capex_pct_revenue: float | Sequence[float] | None = None
    tax_rate: float | None = None

    # --- Working capital (days; None => derive from base year) ---
    days_sales_outstanding: float | None = None
    days_inventory_outstanding: float | None = None
    days_payable_outstanding: float | None = None

    # --- Capital structure / financing ---
    cost_of_debt: float | None = None          # None => interest_expense / debt
    annual_debt_repayment: float = 0.0          # absolute, in millions
    dividend_payout_ratio: float = 0.0

    # --- DCF parameters ---
    risk_free_rate: float = 0.043
    equity_risk_premium: float = 0.055
    beta_override: float | None = None
    terminal_growth: float = 0.025
    exit_ev_ebitda: float | None = None         # alternative terminal method
    mid_year_convention: bool = True

    # --- Sensitivity grid ---
    wacc_sensitivity: Sequence[float] = field(
        default_factory=lambda: [-0.01, -0.005, 0.0, 0.005, 0.01])
    growth_sensitivity: Sequence[float] = field(
        default_factory=lambda: [-0.01, -0.005, 0.0, 0.005, 0.01])

    def __post_init__(self) -> None:
        if self.forecast_years < 1:
            raise ValueError("forecast_years must be >= 1.")
        if self.terminal_growth >= 0.10:
            raise ValueError("terminal_growth looks too high (>= 10%).")

    def series(self, name: str, base_default: float) -> list[float]:
        """Resolve an assumption to a per-year list of length forecast_years.

        ``None`` falls back to ``base_default`` (typically a base-year ratio).
        """
        value = getattr(self, name)
        if value is None:
            value = base_default
        if isinstance(value, (int, float)):
            return [float(value)] * self.forecast_years
        seq = list(value)
        if len(seq) != self.forecast_years:
            raise ValueError(
                f"Assumption '{name}' has {len(seq)} values; "
                f"expected {self.forecast_years}.")
        return [float(v) for v in seq]

    @classmethod
    def from_dict(cls, data: dict) -> "Assumptions":
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown assumption keys: {sorted(unknown)}.")
        return cls(**data)
