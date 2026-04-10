"""Volatility surface interpolation with bounds checking.

Constructs a 2D cubic spline interpolation of implied volatility across
strike and maturity dimensions. Handles extrapolation safely and enforces
realistic volatility bounds to prevent numerical instability.
"""

import logging
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import CubicSpline

logger = logging.getLogger(__name__)

@dataclass
class VolSurface:
    """2D implied volatility surface with natural cubic spline interpolation.
    
    Attributes:
        strikes: Array of strike prices (sorted ascending)
        maturities: Array of maturity times in years (sorted ascending)
        vols: 2D array of shape (n_maturities, n_strikes) with IVs
        
    Notes:
        - All volatilities are clamped to [1e-6, 2.0] (0.01% to 200%)
        - IV bounds prevent numerical failures in pricing engines
        - Variance interpolation ensures T-θ monotonicity
    """
    strikes: np.ndarray
    maturities: np.ndarray
    vols: np.ndarray
    
    MIN_VOL = 1e-6   #: 0.01% floor
    MAX_VOL = 2.0    #: 200% ceiling

    def __post_init__(self):
        """Convert to numpy arrays and validate shapes."""
        self.strikes = np.asarray(self.strikes, dtype=float)
        self.maturities = np.asarray(self.maturities, dtype=float)
        self.vols = np.asarray(self.vols, dtype=float)
        
        if self.vols.shape != (len(self.maturities), len(self.strikes)):
            raise ValueError(f"vols shape {self.vols.shape} != ({len(self.maturities)}, {len(self.strikes)})")
        if len(self.strikes) < 3:
            raise ValueError("Need at least 3 strikes for cubic spline")
        if len(self.maturities) < 2:
            raise ValueError("Need at least 2 maturities")

    def _slice(self, t_idx: int):
        """Create cubic spline for IV at maturity index."""
        return CubicSpline(self.strikes, self.vols[t_idx, :], bc_type="natural")

    def iv(self, k: float, t: float) -> float:
        """Implied volatility at (strike, maturity) with bounds checking.
        
        Args:
            k: Strike price  
            t: Maturity time in years
            
        Returns:
            IV clamped to [MIN_VOL, MAX_VOL]
            
        Notes:
            - Logs warning when extrapolating far beyond surface bounds
            - Uses flat-forward for t < min_maturity or t > max_maturity
        """
        if k <= 0 or t <= 0:
            return self.MIN_VOL
        
        if t <= self.maturities[0]:
            # Extrapolating to/before first maturity
            if t < self.maturities[0] * 0.5:
                logger.warning(
                    f"Extrapolating IV far before surface: t={t:.4f} << min_maturity={self.maturities[0]:.4f}. "
                    f"Using flat-forward approximation."
                )
            raw = max(self.MIN_VOL, float(self._slice(0)(k)))
            return min(raw, self.MAX_VOL)
        
        if t >= self.maturities[-1]:
            # Extrapolating after last maturity
            if t > self.maturities[-1] * 2.0:
                logger.warning(
                    f"Extrapolating IV far after surface: t={t:.4f} >> max_maturity={self.maturities[-1]:.4f}. "
                    f"Using flat-forward approximation."
                )
            raw = max(self.MIN_VOL, float(self._slice(-1)(k)))
            return min(raw, self.MAX_VOL)
        
        hi = int(np.searchsorted(self.maturities, t))
        if hi >= len(self.maturities):
            hi = len(self.maturities) - 1
        lo = int(hi - 1)
        
        t0, t1 = self.maturities[lo], self.maturities[hi]
        s0 = np.clip(float(self._slice(lo)(k)), self.MIN_VOL, self.MAX_VOL)
        s1 = np.clip(float(self._slice(hi)(k)), self.MIN_VOL, self.MAX_VOL)
        
        w0 = s0 * s0 * t0
        w1 = s1 * s1 * t1
        alpha = (t - t0) / (t1 - t0)
        w = w0 + alpha * (w1 - w0)
        w = max(1e-12, w)
        
        result = float(np.sqrt(w / t))
        return min(result, self.MAX_VOL)
