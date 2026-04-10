import numpy as np
from quant_alpha.risk.greeks_portfolio import aggregate_greeks
from quant_alpha.risk.models import Portfolio

def delta_gamma_vega_var(
    portfolio: Portfolio,
    spot: float,
    spot_daily_vol: float,
    iv_daily_vol_abs: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
    correlation_spot_vol: float = -0.75,
    seed: int | None = None,
) -> float:
    """Calculate Delta-Gamma-Vega VaR with spot-vol correlation.
    
    Args:
        correlation_spot_vol: Correlation between spot and vol changes (typically -0.7 to -0.9)
        seed: Optional seed for reproducibility
    
    Returns:
        VaR (positive number even if portfolio profitable)
    """
    if seed is not None:
        np.random.seed(seed)
    
    g = aggregate_greeks(portfolio)
    h = np.sqrt(horizon_days)
    sigma_s = spot * spot_daily_vol * h
    sigma_v = iv_daily_vol_abs * h

    n = 500_000  # Increased for better tail accuracy at 99% confidence
    
    # Generate correlated normal variables: spot and vol moves are negatively correlated
    z1 = np.random.standard_normal(n)
    z2 = np.random.standard_normal(n)
    
    dS = sigma_s * z1
    dvol = sigma_v * (correlation_spot_vol * z1 + 
                      np.sqrt(max(0.0, 1.0 - correlation_spot_vol**2)) * z2)

    # Delta-Gamma-Vega approximation
    pnl = g.delta * dS + 0.5 * g.gamma * (dS ** 2) + g.vega * dvol
    
    # Calculate loss quantile (negative for losses)
    q_loss = np.percentile(pnl, (1 - confidence) * 100.0)
    
    # Return magnitude of loss (positive VaR even if q_loss > 0)
    return float(-q_loss)
