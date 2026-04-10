"""Risk models and portfolios.

This module defines core risk management data structures:
- Position: Single instrument + quantity
- Portfolio: Collection of positions
- RiskLimits: Enforcement bounds for Greeks and Value-at-Risk
"""

from dataclasses import dataclass, field
from typing import List
from pydantic import BaseModel, Field
from quant_alpha.instrument import VanillaOption

@dataclass(frozen=True)
class Position:
    """Single position in a portfolio.
    
    Attributes:
        id: Unique identifier within portfolio
        instrument: VanillaOption contract (spot, strike, maturity, etc.)
        quantity: Number of contracts (can be negative for shorts)
    """
    id: str
    instrument: VanillaOption
    quantity: float

@dataclass
class Portfolio:
    """Collection of positions forming a book.
    
    Attributes:
        name: Portfolio identifier
        positions: List of Position objects (mutable, append via add())
    """
    name: str
    positions: List[Position] = field(default_factory=list)

    def add(self, p: Position) -> None:
        """Append a position to the portfolio."""
        self.positions.append(p)

class RiskLimits(BaseModel):
    """Risk limit thresholds with validation.
    
    All limits are enforced as absolute values. For example, max_abs_delta=5000
    means portfolio delta must be in [-5000, +5000].
    
    Attributes:
        max_abs_delta: Absolute delta limit (delta per $1 spot move)
        max_abs_gamma: Absolute gamma limit (delta change per $1 spot move)
        max_abs_vega: Absolute vega limit (4% vol move sensitivity)
        max_var_1d_99: Value-at-Risk limit at 99% confidence, 1-day horizon
        max_stress_loss: Maximum acceptable loss under stress scenarios
    """
    max_abs_delta: float = Field(gt=0, description="Absolute delta limit")
    max_abs_gamma: float = Field(gt=0, description="Absolute gamma limit")
    max_abs_vega: float = Field(gt=0, description="Absolute vega limit (per 1% vol)")
    max_var_1d_99: float = Field(gt=0, description="99% VaR limit over 1 day")
    max_stress_loss: float = Field(gt=0, description="Max loss under stress scenarios")
