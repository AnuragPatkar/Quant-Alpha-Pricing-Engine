from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.risk.models import Position, Portfolio, RiskLimits
from quant_alpha.risk.scenario import ScenarioShock
from quant_alpha.risk.limits import evaluate_limits

def test_limits_output_shape():
    pf = Portfolio(name="t")
    pf.add(Position("1", VanillaOption(100,100,0.5,0.03,0.2,OptionType.CALL,ExerciseType.EUROPEAN), 200))
    lim = RiskLimits(max_abs_delta=1e9, max_abs_gamma=1e9, max_abs_vega=1e9, 
                     max_var_1d_99=1e9, max_stress_loss=1e9)
    out = evaluate_limits(pf, lim, 100, 0.01, 0.01, [ScenarioShock("s1", -0.02, 0.01)])
    assert "ok" in out and "breaches" in out and "var_1d_99" in out

def test_delta_limit_enforcement():
    """Verify delta limit breach detection."""
    pf = Portfolio(name="large_delta")
    # Create large delta position (calls have delta close to 1)
    pf.add(Position("big_call", VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL), 1000))
    
    # Tight limits should catch this
    lim = RiskLimits(max_abs_delta=100, max_abs_gamma=1e9, max_abs_vega=1e9, 
                     max_var_1d_99=1e9, max_stress_loss=1e9)
    out = evaluate_limits(pf, lim, 100, 0.01, 0.01, [ScenarioShock("test", 0, 0)])
    
    assert "DELTA_LIMIT" in out["breaches"]
    assert out["ok"] is False

def test_vega_limit_enforcement():
    """Verify vega limit breach detection."""
    pf = Portfolio(name="vega_book")
    # ATM options have maximum vega (~30 per contract, /100 for 1% vol = 0.30)
    pf.add(Position("atm_call", VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL), 10000))
    
    # Tight vega limit (for large position)
    lim = RiskLimits(max_abs_delta=1e9, max_abs_gamma=1e9, max_abs_vega=100,
                     max_var_1d_99=1e9, max_stress_loss=1e9)
    out = evaluate_limits(pf, lim, 100, 0.01, 0.01, [ScenarioShock("test", 0, 0)])
    
    assert "VEGA_LIMIT" in out["breaches"]
    assert out["ok"] is False

def test_var_limit_enforcement():
    """Verify 1D 99% VaR limit breach detection."""
    pf = Portfolio(name="var_test")
    pf.add(Position("call", VanillaOption(100, 100, 0.25, 0.05, 0.2, OptionType.CALL), 1000))
    
    # Very tight VaR limit
    lim = RiskLimits(max_abs_delta=1e9, max_abs_gamma=1e9, max_abs_vega=1e9,
                     max_var_1d_99=10.0, max_stress_loss=1e9)
    out = evaluate_limits(pf, lim, 100, 0.01, 0.01, [ScenarioShock("test", 0, 0)])
    
    assert "VAR_1D_99_LIMIT" in out["breaches"]
    assert out["ok"] is False
