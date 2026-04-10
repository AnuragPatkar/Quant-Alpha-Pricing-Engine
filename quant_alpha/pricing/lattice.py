import numpy as np
from quant_alpha.pricing.engine import PricingEngine
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType

class CRRLatticeEngine(PricingEngine):
    def __init__(self, steps: int = 500, richardson: bool = True):
        self.steps = steps
        self.richardson = richardson

    def _price_n(self, inst: VanillaOption, n: int) -> float:
        S, K, T, r, sigma = inst.spot, inst.strike, inst.maturity, inst.rate, inst.vol
        
        # Dividend adjustment (PV)
        pv_divs = sum(d.amount * np.exp(-r * d.t) for d in inst.dividends if d.t <= T)
        # Sanity check: total PV of dividends should not exceed spot
        if pv_divs > S * 1.01:
            raise ValueError(
                f"Total PV of dividends ${pv_divs:.2f} exceeds spot ${S:.2f}. "
                f"Dividend structure is invalid (possibly negative dividends or data error)."
            )
        S_adj = max(S - pv_divs, 1e-12)
        
        dt = T / n
        u = np.exp(sigma * np.sqrt(dt))
        d = 1.0 / u
        
        # Risk-neutral probability
        fwd = np.exp(r * dt)
        p = (fwd - d) / (u - d)
        
        # Validate probability is in (0,1)
        if not (0 <= p <= 1):
            raise ValueError(f"Invalid risk-neutral probability {p}: check rates and volatility")
        
        disc = 1.0 / fwd

        prices = np.array([S_adj * (u ** j) * (d ** (n - j)) for j in range(n + 1)])
        vals = np.maximum(prices - K, 0.0) if inst.option_type == OptionType.CALL else np.maximum(K - prices, 0.0)

        for i in range(n - 1, -1, -1):
            vals = disc * (p * vals[1:i+2] + (1 - p) * vals[0:i+1])
            if inst.exercise == ExerciseType.AMERICAN:
                prices_at_t = np.array([S_adj * (u ** j) * (d ** (i - j)) for j in range(i + 1)])
                ex = np.maximum(prices_at_t - K, 0.0) if inst.option_type == OptionType.CALL else np.maximum(K - prices_at_t, 0.0)
                vals = np.maximum(vals, ex)
        return float(vals[0])

    def price(self, inst: VanillaOption) -> float:
        pn = self._price_n(inst, self.steps)
        if not self.richardson:
            return pn
        p2n = self._price_n(inst, 2 * self.steps)
        return 2.0 * p2n - pn
