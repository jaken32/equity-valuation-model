# Equity Valuation Model
[![tests](https://github.com/jaken32/equity-valuation-model/actions/workflows/main.yml/badge.svg)](https://github.com/jaken32/equity-valuation-model/actions/workflows/main.yml)
A command-line tool and Python library that takes a stock ticker, builds a
linked three-statement projection, and runs a discounted cash-flow (DCF)
valuation with a WACC × terminal-growth sensitivity table. Output is rendered to
the terminal and, optionally, to a formatted Excel workbook.

The design goal is a valuation that is *auditable*: every forecast line is
driven by an explicit, editable assumption, the projected balance sheet ties out
by construction, and the enterprise-to-equity bridge is shown in full.

## What it does

1. Pulls the most recent annual income statement, balance sheet, and cash-flow
   statement plus current market data for a ticker.
2. Projects an integrated three-statement model over a configurable horizon
   (default five years), driven by assumptions for growth, margins,
   working-capital days, capex, and financing.
3. Computes unlevered free cash flow, discounts it at the WACC, and adds a
   terminal value (Gordon growth or an exit EV/EBITDA multiple).
4. Bridges enterprise value to an implied share price and compares it to the
   current price.
5. Produces a sensitivity grid of implied price across WACC and terminal growth.

## Architecture

```
equity-valuation-model/
├── config/
│   └── default_assumptions.yaml      # editable forecast drivers
├── src/valuation/
│   ├── data/                         # data layer (vendor-agnostic)
│   │   ├── base.py                   #   CompanyFinancials + DataProvider interface
│   │   ├── yfinance_provider.py      #   default, no API key
│   │   └── fmp_provider.py           #   optional, Financial Modeling Prep
│   ├── model/
│   │   ├── assumptions.py            # forecast drivers and DCF parameters
│   │   ├── three_statement.py        # linked IS / BS / CF projection
│   │   └── dcf.py                    # WACC, FCFF discounting, terminal value
│   ├── reporting/
│   │   ├── console.py                # text report
│   │   └── excel.py                  # formatted .xlsx export
│   ├── config.py                     # YAML loading
│   ├── pipeline.py                   # ticker -> valuation orchestration
│   └── cli.py                        # argparse entry point
└── tests/                            # pytest suite (runs offline)
```

The rest of the package depends only on the `CompanyFinancials` snapshot, never
on a specific data vendor. Adding a new source (e.g. SEC EDGAR) means
implementing one `DataProvider.fetch` method.

## Installation

Requires Python 3.10+.

```bash
git clone https://github.com/jaken32/equity-valuation-model.git
cd equity-valuation-model
pip install -e .
```

For development (tests included):

```bash
pip install -e ".[dev]"
```

## Usage

### Command line

```bash
# Default run against Yahoo Finance (no API key needed)
equity-dcf AAPL

# Custom assumptions and an Excel workbook
equity-dcf NVDA --config my_assumptions.yaml --excel nvda_valuation.xlsx

# Use Financial Modeling Prep instead
equity-dcf MSFT --provider fmp --api-key $FMP_API_KEY
```

You can also run it as a module: `python -m valuation AAPL`.

### As a library

```python
from valuation import value_ticker, Assumptions

run = value_ticker(
    "AAPL",
    assumptions=Assumptions(revenue_growth=[0.08, 0.07, 0.06, 0.05, 0.04],
                            terminal_growth=0.025),
)

print(run.result.implied_share_price, run.result.upside)
print(run.model.income_statement)
print(run.result.sensitivity)
```

## Methodology

**Three-statement linkage.** Revenue compounds at the assumed growth rate. COGS,
SG&A, D&A, and capex are driven off revenue; receivables, inventory, and payables
off working-capital days. Net PP&E rolls forward as prior PP&E plus capex less
depreciation. Retained earnings roll forward through net income less dividends.
Cash is solved from the cash-flow statement and carried to the balance sheet, so
the balance sheet ties out each period (verified numerically by
`ThreeStatementModel.balance_check`). Balance-sheet items the model does not
itemize are captured as a single constant "other net assets" plug fixed at the
base period.

**Free cash flow.** Unlevered FCF (FCFF) = EBIT × (1 − tax) + D&A − capex −
change in net working capital.

**Discount rate.** WACC weights the CAPM cost of equity
(risk-free + β × equity risk premium) and the after-tax cost of debt by market
values of equity and debt.

**Terminal value.** Gordon growth by default; an exit EV/EBITDA multiple is used
instead if `exit_ev_ebitda` is set. Mid-year discounting is applied by default.

**Sensitivity.** Implied share price is recomputed across a grid of WACC and
terminal-growth offsets around the base case.

## Configuration

All assumptions live in a YAML file (see `config/default_assumptions.yaml`).
Ratio fields left as `null` are derived from the company's most recent reported
year, so the projection starts from its actual operating profile. Any field
accepts a single value (held flat) or a list of length `forecast_years`.

| Field | Meaning |
| --- | --- |
| `forecast_years` | Length of the explicit forecast horizon |
| `revenue_growth` | Annual revenue growth (scalar or per-year list) |
| `gross_margin`, `sga_pct_revenue`, `da_pct_revenue`, `capex_pct_revenue` | Income-statement and capex drivers as a share of revenue |
| `tax_rate` | Effective tax rate |
| `days_sales_outstanding`, `days_inventory_outstanding`, `days_payable_outstanding` | Working-capital assumptions |
| `cost_of_debt`, `annual_debt_repayment`, `dividend_payout_ratio` | Financing assumptions |
| `risk_free_rate`, `equity_risk_premium`, `beta_override` | Cost-of-equity inputs |
| `terminal_growth`, `exit_ev_ebitda`, `mid_year_convention` | Terminal-value and discounting settings |
| `wacc_sensitivity`, `growth_sensitivity` | Offsets for the sensitivity grid |

## Data providers

- **yfinance** (default): free, no key. Yahoo's line-item labels vary, so each
  field is resolved against candidate labels with fallbacks.
- **Financial Modeling Prep** (`--provider fmp`): cleaner normalized statements;
  requires a free API key via `--api-key` or the `FMP_API_KEY` environment
  variable.

## Testing

```bash
pytest
```

The suite runs fully offline against a synthetic, internally consistent snapshot
(no network calls), covering statement linkage, the balance-sheet identity, the
equity bridge, terminal-value methods, and the sensitivity grid.

## Limitations

This is a generalized model, not a substitute for a hand-built, company-specific
one. It assumes a single consolidated business (no segment build), holds debt
flat unless a repayment schedule is set, and does not model share issuance,
buybacks, leases, or deferred taxes explicitly. Output quality is bounded by the
quality of the input assumptions and the source data. A standard FCFF DCF will
not reproduce premium multiples that the market assigns for reasons outside the
model. Results are estimates for analysis and learning, not investment advice.

## License

MIT. See [LICENSE](LICENSE).
