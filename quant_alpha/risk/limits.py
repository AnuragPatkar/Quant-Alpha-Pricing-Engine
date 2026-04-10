from typing import Dict, Any, List
from quant_alpha.risk.models import Portfolio, RiskLimits
from quant_alpha.risk.greeks_portfolio import aggregate_greeks
from quant_alpha.risk.var import delta_gamma_vega_var
from quant_alpha.risk.scenario import ScenarioEngine, ScenarioShock

def evaluate_limits(
    portfolio: Portfolio,
    limits: RiskLimits,
    spot: float,
    spot_daily_vol: float,
    iv_daily_vol_abs: float,
    stress_scenarios: List[ScenarioShock],
    correlation_spot_vol: float = -0.75,
) -> Dict[str, Any]:
    g = aggregate_greeks(portfolio)
    var_1d_99 = float(delta_gamma_vega_var(
        portfolio=portfolio,
        spot=spot,
        spot_daily_vol=spot_daily_vol,
        iv_daily_vol_abs=iv_daily_vol_abs,
        confidence=0.99,
        horizon_days=1,
        correlation_spot_vol=correlation_spot_vol,
    ))

    scen_raw = ScenarioEngine().ladder(portfolio, stress_scenarios)
    scen = [{"scenario": x["scenario"], "pnl": float(x["pnl"])} for x in scen_raw]

    worst = min((x["pnl"] for x in scen), default=0.0)
    stress_loss = float(abs(min(0.0, worst)))

    breaches = []
    if abs(g.delta) > limits.max_abs_delta:
        breaches.append("DELTA_LIMIT")
    if abs(g.gamma) > limits.max_abs_gamma:
        breaches.append("GAMMA_LIMIT")
    if abs(g.vega) > limits.max_abs_vega:
        breaches.append("VEGA_LIMIT")
    if var_1d_99 > limits.max_var_1d_99:
        breaches.append("VAR_1D_99_LIMIT")
    if stress_loss > limits.max_stress_loss:
        breaches.append("STRESS_LOSS_LIMIT")

    return {
        "greeks": {
            "delta": float(g.delta),
            "gamma": float(g.gamma),
            "vega": float(g.vega),
        },
        "var_1d_99": var_1d_99,
        "stress": scen,
        "worst_stress_loss_abs": stress_loss,
        "breaches": breaches,
        "ok": len(breaches) == 0,
    }