"""Black-Scholes Greeks calculations with vectorized operations.

Provides fast vectorized computation of Greeks (delta, gamma, vega) using numpy
broadcasting for portfolio aggregation. Handles edge cases (near-zero vol/time)
with numerical guards.
"""

import numpy as np
from scipy.stats import norm

def bs_greeks_vectorized(
    S: float | np.ndarray,
    K: float | np.ndarray,
    T: float | np.ndarray,
    r: float,
    sigma: float | np.ndarray,
    is_call: bool = True,
) -> tuple[np.ndarray | float, np.ndarray | float, np.ndarray | float, np.ndarray, np.ndarray]:
    """Compute Black-Scholes Greeks using vectorized numpy operations.
    
    Handles numpy broadcasting: inputs can be scalars or arrays of compatible shapes.
    All array inputs broadcast together to a common output shape.
    
    Args:
        S: Spot price (scalar or array)
        K: Strike price (scalar or array, must broadcast with S)
        T: Maturity time in years (scalar or array, must broadcast with S)
        r: Risk-free rate (scalar only)
        sigma: Volatility (scalar or array, must broadcast with S)
        is_call: Is this a call option? (default True)
        
    Returns:
        Tuple of (delta, gamma, vega, d1, d2) where:
        - delta: Delta sensitivity (∂price/∂S)
        - gamma: Gamma (∂²price/∂S²) 
        - vega: Vega per 1% volatility change
        - d1, d2: Intermediate d1, d2 values for price recovery
        
        All returns broadcast to common shape of input arrays.
        
    Notes:
        - Vectorized for portfolio aggregation (all Greeks in single call)
        - Guards against numerical instability: safe_sigma=max(σ, 1e-8), safe_T=max(T, 1e-6)
        - Gamma handles zero-volatility edge case with np.where()
    """
    S, K, T, sigma = map(np.asarray, (S, K, T, sigma))
    
    # Guard against edge cases
    safe_sigma = np.maximum(sigma, 1e-8)
    safe_T = np.maximum(T, 1e-6)
    
    d1 = (np.log(S/K) + (r + 0.5*safe_sigma*safe_sigma)*safe_T)/(safe_sigma*np.sqrt(safe_T))
    d2 = d1 - safe_sigma*np.sqrt(safe_T)
    delta = norm.cdf(d1) if is_call else norm.cdf(d1) - 1
    
    # Avoid division by zero in gamma
    gamma = np.where(safe_sigma > 1e-8, norm.pdf(d1)/(S*safe_sigma*np.sqrt(safe_T)), 0.0)
    vega = S*norm.pdf(d1)*np.sqrt(safe_T) / 100.0  # Per 1% vol
    
    return delta, gamma, vega, d1, d2
