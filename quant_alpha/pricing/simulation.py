"""Monte Carlo option pricing engine with variance reduction.

Uses Sobol sequences, antithetic variates, and control variates to reduce
variance and improve convergence for European option pricing.
"""

import numpy as np
from numba import njit
from scipy.stats import qmc, norm
from quant_alpha.pricing.engine import PricingEngine
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType

@njit(cache=True)
def _gbm_terminal(S0: float, r: float, sigma: float, T: float, z: float) -> float:
    """Compute terminal stock price under GBM.
    
    Args:
        S0: Initial stock price
        r: Risk-free rate
        sigma: Volatility
        T: Time to maturity
        z: Standard normal draw
        
    Returns:
        Terminal stock price St = S0 * exp((r - 0.5*σ²)T + σ√T * z)
    """
    return float(S0 * np.exp((r - 0.5 * sigma * sigma) * T + sigma * np.sqrt(T) * z))

@njit(cache=True)
def _gbm_terminal_vectorized(S0: float, r: float, sigma: float, T: float, z: np.ndarray) -> np.ndarray:
    """Vectorized terminal stock price computation.
    
    Computes GBM terminal values for all paths in one pass, enabling Numba JIT
    optimization and avoiding Python loops.
    
    Args:
        S0: Initial stock price
        r: Risk-free rate
        sigma: Volatility
        T: Time to maturity
        z: Array of standard normal draws (n_paths,)
        
    Returns:
        Array of terminal prices (n_paths,)
    """
    n = z.shape[0]
    st = np.empty(n)
    drift = (r - 0.5 * sigma * sigma) * T
    diffusion = sigma * np.sqrt(T)
    
    for i in range(n):
        st[i] = S0 * np.exp(drift + diffusion * z[i])
    
    return st

class MonteCarloEngine(PricingEngine):
    def __init__(self, n_paths: int = 200_000, use_sobol: bool = True, antithetic: bool = True, control_variate: bool = True, seed: int | None = None):
        """Initialize Monte Carlo engine.
        
        Args:
            n_paths: Number of sample paths (>= 1024 for Sobol balance)
            use_sobol: Use Sobol low-discrepancy sequence (else pseudo-random)
            antithetic: Include antithetic variates (double effective paths)
            control_variate: Use stock price as control variate (reduce variance)
            seed: Random seed for reproducibility (applies to pseudo-random only)
        """
        self.n_paths = n_paths
        self.use_sobol = use_sobol
        self.antithetic = antithetic
        self.control_variate = control_variate
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)

    def _normal_draws(self, n: int) -> np.ndarray:
        if self.use_sobol:
            n_power2 = 2 ** int(np.ceil(np.log2(n)))
            sampler = qmc.Sobol(d=1, scramble=True)
            u = sampler.random(n_power2).reshape(-1)[:n]
            u = np.clip(u, 1e-12, 1 - 1e-12)
            return np.asarray(norm.ppf(u), dtype=float)
        return np.asarray(np.random.standard_normal(n), dtype=float)

    def price(self, inst: VanillaOption) -> float:
        """Price a European option via Monte Carlo simulation.
        
        Uses Sobol low-discrepancy sequences (or pseudo-random if disabled),
        antithetic variates (sample both z and -z), and stock price control
        variate to reduce variance and improve convergence.
        
        Args:
            inst: VanillaOption to price
            
        Returns:
            Option price as float
        """
        inst.validate()
        n = self.n_paths // 2 if self.antithetic else self.n_paths
        z = self._normal_draws(n)
        if self.antithetic:
            z = np.concatenate([z, -z])

        # Adjust spot for dividends (present value)
        spot_adj = inst.spot - sum(d.amount * np.exp(-inst.rate * d.t) 
                                    for d in inst.dividends if d.t <= inst.maturity)
        spot_adj = max(spot_adj, 1e-12)
        
        # Vectorized GBM generation: all paths computed in one JIT'd call
        st = _gbm_terminal_vectorized(spot_adj, inst.rate, inst.vol, inst.maturity, z)

        payoff = np.maximum(st - inst.strike, 0.0) if inst.option_type == OptionType.CALL else np.maximum(inst.strike - st, 0.0)

        if self.control_variate:
            ctrl = st
            # Expectation of terminal spot under risk-neutral measure (using ORIGINAL spot, not dividend-adjusted)
            exp_ctrl = inst.spot * np.exp(inst.rate * inst.maturity)
            cov = np.cov(payoff, ctrl, ddof=1)[0, 1]
            varc = np.var(ctrl, ddof=1)
            b = 0.0 if varc < 1e-16 else cov / varc
            payoff = payoff - b * (ctrl - exp_ctrl)

        return float(np.exp(-inst.rate * inst.maturity) * payoff.mean())
