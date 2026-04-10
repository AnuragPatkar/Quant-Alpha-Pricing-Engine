import numpy as np
from scipy.stats import norm
from quant_alpha.pricing.engine import PricingEngine
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType

class AnalyticBSEngine(PricingEngine):
    def _adj_spot_for_dividends(self, inst: VanillaOption) -> float:
        pv_divs = sum(d.amount * np.exp(-inst.rate * d.t) for d in inst.dividends if d.t <= inst.maturity)
        return float(max(1e-12, inst.spot - pv_divs))

    def price(self, inst: VanillaOption) -> float:
        inst.validate()
        S = self._adj_spot_for_dividends(inst)
        K, T, r, sigma = inst.strike, inst.maturity, inst.rate, inst.vol

        # Guard against degenerate cases
        if T < 1e-6:
            # At expiry: intrinsic value only
            if inst.option_type == OptionType.CALL:
                return float(max(S - K, 0.0))
            return float(max(K - S, 0.0))
        
        if sigma < 1e-8:
            # Forward pricing with no volatility
            fwd = S * np.exp(r * T)
            if inst.option_type == OptionType.CALL:
                return float(np.exp(-r * T) * max(fwd - K, 0.0))
            return float(np.exp(-r * T) * max(K - fwd, 0.0))

        d1 = (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if inst.option_type == OptionType.CALL:
            return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
        return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))