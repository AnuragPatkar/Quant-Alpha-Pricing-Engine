from dataclasses import dataclass
from typing import List, Dict
from quant_alpha.instrument import VanillaOption
from quant_alpha.risk.models import Portfolio
from quant_alpha.pricing.analytic import AnalyticBSEngine

@dataclass(frozen=True)
class ScenarioShock:
    name: str
    dspot_pct: float
    dvol_abs: float
    drate_abs: float = 0.0
    horizon_days: float = 0.0  # Days elapsed for this scenario

class ScenarioEngine:
    def __init__(self):
        self.pricer = AnalyticBSEngine()

    def _repriced(self, inst: VanillaOption, s: ScenarioShock) -> VanillaOption:
        # Advance maturity by horizon_days
        new_maturity = max(1e-6, inst.maturity - s.horizon_days / 365.0)
        new_spot = max(1e-8, inst.spot * (1.0 + s.dspot_pct))
        new_vol = max(1e-6, inst.vol + s.dvol_abs)
        
        return VanillaOption(
            spot=new_spot,
            strike=inst.strike,
            maturity=new_maturity,
            rate=inst.rate + s.drate_abs,
            vol=new_vol,
            option_type=inst.option_type,
            exercise=inst.exercise,
            dividends=inst.dividends,
        )

    def portfolio_pnl(self, portfolio: Portfolio, scenario: ScenarioShock) -> float:
        base = 0.0
        shocked = 0.0
        for p in portfolio.positions:
            b = self.pricer.price(p.instrument)
            s = self.pricer.price(self._repriced(p.instrument, scenario))
            base += p.quantity * b
            shocked += p.quantity * s
        return shocked - base

    def ladder(self, portfolio: Portfolio, scenarios: List[ScenarioShock]) -> List[Dict]:
        out = []
        for s in scenarios:
            out.append({"scenario": s.name, "pnl": self.portfolio_pnl(portfolio, s)})
        return out
