import numpy as np
from dataclasses import dataclass
from scipy.stats import norm
from quant_alpha.enums import OptionType
from quant_alpha.risk.models import Portfolio

@dataclass
class AggregatedGreeks:
    delta: float
    gamma: float
    vega: float

def _d1(S, K, T, r, sigma):
    return (np.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * np.sqrt(T))

def position_greeks(inst):
    # Edge case guards: zero vol or zero time remaining
    if inst.maturity < 1e-6 or inst.vol < 1e-8:
        # Deep ITM/OTM with no time value: delta ∈ {0,1}, gamma≈0, vega≈0
        if inst.option_type == OptionType.CALL:
            delta = 1.0 if inst.spot > inst.strike else 0.0
        else:
            delta = -1.0 if inst.spot < inst.strike else 0.0
        return float(delta), 0.0, 0.0
    
    d1 = _d1(inst.spot, inst.strike, inst.maturity, inst.rate, inst.vol)
    delta = norm.cdf(d1) if inst.option_type == OptionType.CALL else norm.cdf(d1) - 1.0
    gamma = norm.pdf(d1) / (inst.spot * inst.vol * np.sqrt(inst.maturity))
    vega = inst.spot * norm.pdf(d1) * np.sqrt(inst.maturity)  # Per 1% vol change (1 percentage point)
    return float(delta), float(gamma), float(vega)

def aggregate_greeks(portfolio: Portfolio) -> AggregatedGreeks:
    d = g = v = 0.0
    for p in portfolio.positions:
        pd, pg, pv = position_greeks(p.instrument)
        d += p.quantity * pd
        g += p.quantity * pg
        v += p.quantity * pv
    return AggregatedGreeks(delta=d, gamma=g, vega=v)
