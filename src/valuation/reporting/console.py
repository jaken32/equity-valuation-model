"""Plain-text rendering of model output for the terminal.

Deliberately dependency-free: formatting is done with pandas and standard
string operations so the tool runs without optional pretty-printing libraries.
"""
from __future__ import annotations

import pandas as pd

from ..data.base import CompanyFinancials
from ..model.dcf import DCFResult


def _fmt_millions(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(
        lambda col: col.map(lambda v: f"{v:,.0f}" if pd.notna(v) else "-"))


def _rule(title: str, width: int = 72) -> str:
    return f"\n{title}\n{'-' * width}"


def render(fin: CompanyFinancials, model_income: pd.DataFrame,
           model_balance: pd.DataFrame, model_cashflow: pd.DataFrame,
           fcf: pd.Series, result: DCFResult) -> str:
    """Return a full text report for a valuation run."""
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"{fin.name} ({fin.ticker}) - DCF Valuation")
    lines.append(f"Base fiscal year {fin.fiscal_year} | Currency {fin.currency} "
                 f"| Figures in millions")
    lines.append("=" * 72)

    lines.append(_rule("Income Statement (projected)"))
    lines.append(_fmt_millions(model_income).to_string())

    lines.append(_rule("Balance Sheet (projected)"))
    lines.append(_fmt_millions(model_balance).to_string())

    lines.append(_rule("Cash Flow Statement (projected)"))
    lines.append(_fmt_millions(model_cashflow).to_string())

    lines.append(_rule("Unlevered Free Cash Flow"))
    lines.append(_fmt_millions(fcf.to_frame("FCFF").T).to_string())

    lines.append(_rule("DCF Output"))
    rows = [
        ("Cost of equity", f"{result.cost_of_equity:.2%}"),
        ("After-tax cost of debt", f"{result.cost_of_debt_after_tax:.2%}"),
        ("WACC", f"{result.wacc:.2%}"),
        ("PV of explicit FCF", f"{result.pv_explicit_fcf:,.0f}"),
        ("PV of terminal value", f"{result.pv_terminal_value:,.0f}"),
        ("Terminal value % of EV", f"{result.terminal_value_pct:.1%}"),
        ("Enterprise value", f"{result.enterprise_value:,.0f}"),
        ("Less: net debt", f"{result.net_debt:,.0f}"),
        ("Equity value", f"{result.equity_value:,.0f}"),
        ("Shares outstanding (mm)", f"{result.shares_outstanding:,.0f}"),
        ("Implied share price", f"{result.implied_share_price:,.2f}"),
        ("Current share price", f"{result.current_share_price:,.2f}"),
        ("Upside / (downside)", f"{result.upside:+.1%}"),
    ]
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        lines.append(f"  {label.ljust(width)}  {value.rjust(14)}")

    lines.append(_rule("Sensitivity - implied share price (WACC x terminal g)"))
    lines.append(result.sensitivity.apply(
        lambda col: col.map(lambda v: f"{v:,.2f}" if pd.notna(v) else "n/a")).to_string())

    lines.append("")
    lines.append("Note: outputs are model estimates driven by editable "
                 "assumptions, not investment advice.")
    return "\n".join(lines)
