"""Option pricing engine implementations using strategy pattern.

Engines support European and American vanilla options with optional discrete
dividends. Implementations must handle edge cases (T→0, σ→0, extreme moneyness)
and return finite positive prices.

All pricing engines validate instruments before pricing and raise ValueError
for invalid inputs (spot ≤ 0, strike ≤ 0, maturity ≤ 0, vol < 0, etc.).
"""

from abc import ABC, abstractmethod
from quant_alpha.instrument import VanillaOption

class PricingEngine(ABC):
    """Abstract base class for option pricing engines.
    
    Implementations must:
    - Validate instruments before pricing
    - Handle dividend adjustments via present value
    - Return strictly positive prices
    - Handle edge cases (T→0 returns intrinsic value, σ→0 limits to forward pricing)
    - Raise ValueError for invalid inputs
    
    Attributes:
        None (pure interface)
    """
    
    @abstractmethod
    def price(self, inst: VanillaOption) -> float:
        """Price a vanilla option.
        
        Args:
            inst: VanillaOption contract with spot, strike, maturity, rate, vol, etc.
            
        Returns:
            Option price (strictly positive).
            
        Raises:
            ValueError: If instrument validation fails or numerical instability detected.
        """
        ...
