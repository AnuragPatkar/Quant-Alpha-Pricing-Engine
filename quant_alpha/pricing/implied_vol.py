import logging
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm
from quant_alpha.instrument import VanillaOption
from quant_alpha.pricing.analytic import AnalyticBSEngine
from quant_alpha.enums import OptionType

logger = logging.getLogger(__name__)


def _vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if sigma <= 0 or T <= 0:
        return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * np.sqrt(T))
    return float(S * norm.pdf(float(d1)) * np.sqrt(T))


def implied_vol(price_mkt: float, inst: VanillaOption, tol: float = 1e-8, max_iter: int = 50) -> float:
    eng = AnalyticBSEngine()
    S, K, T, r = inst.spot, inst.strike, inst.maturity, inst.rate

    intrinsic = max(S - K, 0.0) if inst.option_type == OptionType.CALL else max(K - S, 0.0)
    if price_mkt < intrinsic * 0.999:
        raise ValueError(f"Market price {price_mkt} violates intrinsic {intrinsic}")

    sigma = float(max(inst.vol, 0.2))

    for _ in range(max_iter):
        test = VanillaOption(S, K, T, r, sigma, inst.option_type, inst.exercise, inst.dividends)
        model_px = float(eng.price(test))
        diff = model_px - price_mkt

        if abs(diff) < tol:
            return float(sigma)

        v = _vega(S, K, T, r, sigma)
        if v < 1e-8:
            break

        sigma_new = sigma - diff / v
        # Bound sigma movements to avoid divergence (prevent single-step doubling/halving)
        sigma = float(np.clip(sigma_new, sigma * 0.5, sigma * 2.0))
        # Guard against NaN or infinite values
        if not np.isfinite(sigma):
            break

    def f(sig: float) -> float:
        test = VanillaOption(S, K, T, r, sig, inst.option_type, inst.exercise, inst.dividends)
        return float(eng.price(test) - price_mkt)

    f_low = f(1e-8)
    f_high = f(5.0)

    if f_low * f_high > 0:
        logger.warning(
            f"IV solver bracketing failed: is_call={inst.option_type == OptionType.CALL}, "
            f"S={S:.1f}, K={K:.1f}, T={T:.4f}, market_price={price_mkt:.2f}. Returning boundary estimate."
        )
        result = float(1e-8 if abs(f_low) < abs(f_high) else 5.0)
        # Validate result is not NaN or infinite
        if not np.isfinite(result) or not np.isfinite(f(result)):
            raise ValueError(
                f"IV solver produced invalid estimate {result} for price {price_mkt} "
                f"(S={S}, K={K}, T={T}). Market price may be unbounded."
            )
        return result

    return float(brentq(f, 1e-8, 5.0, xtol=tol, maxiter=200))