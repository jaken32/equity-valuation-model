"""Equity valuation toolkit: three-statement projection and DCF.

Public API:
    >>> from valuation import value_ticker
    >>> result = value_ticker("AAPL")
"""
from __future__ import annotations

from .model.assumptions import Assumptions
from .model.three_statement import ThreeStatementModel
from .model.dcf import DCFValuation, DCFResult
from .pipeline import value_ticker

__all__ = [
    "Assumptions",
    "ThreeStatementModel",
    "DCFValuation",
    "DCFResult",
    "value_ticker",
]

__version__ = "1.0.0"
