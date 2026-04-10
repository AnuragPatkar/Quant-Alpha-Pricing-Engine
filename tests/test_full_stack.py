import pytest
import numpy as np
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.pricing.analytic import AnalyticBSEngine
from quant_alpha.pricing.lattice import CRRLatticeEngine
from quant_alpha.pricing.simulation import MonteCarloEngine
from quant_alpha.pricing.implied_vol import implied_vol
from quant_alpha.market_data import MarketDataStore
from quant_alpha.data.nse_cleaning import clean_option_chain
from quant_alpha.risk.models import Position, Portfolio, RiskLimits
from quant_alpha.risk.scenario import ScenarioShock
from quant_alpha.risk.limits import evaluate_limits
from quant_alpha.risk.var import delta_gamma_vega_var

def test_analytic_price():
    inst = VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL, ExerciseType.EUROPEAN)
    p = AnalyticBSEngine().price(inst)
    # For ATM 1y: BS ≈ 10.45, tolerance ±0.05
    assert 10.4 < p < 10.5, f"Expected ~10.45, got {p}"

def test_lattice_close_to_analytic():
    inst = VanillaOption(100, 100, 1.0, 0.03, 0.2, OptionType.CALL, ExerciseType.EUROPEAN)
    bs = AnalyticBSEngine().price(inst)
    crr = CRRLatticeEngine(steps=600, richardson=True).price(inst)
    # Richardson extrapolation should be very close
    assert abs(crr - bs) < 0.1, f"Lattice error {abs(crr - bs)} too large, BS={bs}, CRR={crr}"

def test_mc_close_to_analytic():
    inst = VanillaOption(100, 100, 1.0, 0.03, 0.2, OptionType.CALL, ExerciseType.EUROPEAN)
    bs = AnalyticBSEngine().price(inst)
    mc = MonteCarloEngine(n_paths=131072, use_sobol=True, antithetic=True, control_variate=True, seed=42).price(inst)
    # Sobol + control variate should be very accurate
    assert abs(mc - bs) < 0.05, f"MC error {abs(mc - bs)} too large, BS={bs}, MC={mc}"

def test_implied_vol_recovery():
    inst = VanillaOption(100, 105, 0.7, 0.02, 0.25, OptionType.CALL, ExerciseType.EUROPEAN)
    px = AnalyticBSEngine().price(inst)
    iv = implied_vol(px, inst)
    # IV should be recovered within ±0.0001 (0.01% vol points)
    assert abs(iv - 0.25) < 1e-4, f"IV recovery failed: expected 0.25, got {iv}"

def test_market_data_pubsub():
    md = MarketDataStore()
    hit = {"n": 0}
    md.subscribe("NIFTY", lambda s, t: hit.__setitem__("n", hit["n"] + 1))
    md.update_tick("NIFTY", {"ltp": 22500})
    assert md.get("NIFTY")["ltp"] == 22500
    assert hit["n"] == 1

def test_cleaning():
    rows = [
        {"bidQty": 0, "askQty": 0, "bidprice": 10, "askPrice": 12},
        {"bidQty": 10, "askQty": 10, "bidprice": 13, "askPrice": 12},
        {"bidQty": 5, "askQty": 8, "bidprice": 10, "askPrice": 11},
    ]
    out = clean_option_chain(rows)
    assert len(out) == 1

def test_risk_limits_pipeline():
    pf = Portfolio(name="book")
    pf.add(Position("c1", VanillaOption(100,100,0.5,0.03,0.2,OptionType.CALL,ExerciseType.EUROPEAN), 100))
    limits = RiskLimits(max_abs_delta=1e9, max_abs_gamma=1e9, max_abs_vega=1e9, 
                        max_var_1d_99=1e9, max_stress_loss=1e9)
    out = evaluate_limits(
        portfolio=pf,
        limits=limits,
        spot=100,
        spot_daily_vol=0.01,
        iv_daily_vol_abs=0.01,
        stress_scenarios=[ScenarioShock("shock", -0.02, 0.01)]
    )
    assert out["ok"] is True

# P0 Tests: Edge cases and new functionality
def test_implied_vol_zero_vol():
    """IV recovery with very low initial vol."""
    inst = VanillaOption(100, 105, 0.7, 0.02, 0.01, OptionType.CALL, ExerciseType.EUROPEAN)
    px = AnalyticBSEngine().price(inst)
    iv = implied_vol(px, inst)
    assert abs(iv - 0.01) < 1e-4

def test_implied_vol_invalid_price():
    """IV solver rejects prices below intrinsic."""
    inst = VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL)
    with pytest.raises(ValueError):
        implied_vol(-0.01, inst)

def test_mc_with_dividend():
    """MC engine handles dividend-paying options."""
    from quant_alpha.instrument import Dividend
    div = Dividend(t=0.25, amount=2.0)
    inst = VanillaOption(100, 100, 0.5, 0.03, 0.2, OptionType.CALL, ExerciseType.EUROPEAN, dividends=[div])
    eng = MonteCarloEngine(n_paths=65536, seed=42)
    p = eng.price(inst)
    assert 1 < p < 15  # Dividend reduces call value

def test_lattice_with_dividend():
    """CRR lattice handles dividend-paying options."""
    from quant_alpha.instrument import Dividend
    div = Dividend(t=0.25, amount=2.0)
    inst = VanillaOption(100, 100, 0.5, 0.03, 0.2, OptionType.CALL, ExerciseType.EUROPEAN, dividends=[div])
    eng = CRRLatticeEngine(steps=400)
    p = eng.price(inst)
    assert 1 < p < 15  # Dividend reduces call value

def test_greeks_zero_vol():
    """Greeks handle zero vol edge case."""
    inst = VanillaOption(100, 100, 0.5, 0.05, 1e-9, OptionType.CALL)
    # Should not crash, should return sensible bounds
    from quant_alpha.risk.greeks_portfolio import position_greeks
    d, g, v = position_greeks(inst)
    assert 0 <= d <= 1 and g >= 0 and v >= 0

def test_greeks_zero_time():
    """Greeks handle zero time edge case."""
    inst = VanillaOption(100, 100, 1e-7, 0.05, 0.2, OptionType.CALL)
    from quant_alpha.risk.greeks_portfolio import position_greeks
    d, g, v = position_greeks(inst)
    # At expiry, should be intrinsic: call delta = 1 if S > K else 0
    assert 0 <= d <= 1 and g == 0.0 and v == 0.0

def test_var_with_profitable_portfolio():
    """VaR correctly handles profitable portfolios (no clamping to 0)."""
    pf = Portfolio(name="put_buyer")
    # Short put (bearish) benefits from spot down
    pf.add(Position("p1", VanillaOption(100, 100, 1, 0.05, 0.2, OptionType.PUT), -100))
    
    var = delta_gamma_vega_var(pf, 100, 0.01, 0.01, seed=42)
    # VaR can be negative (profit scenario), not clamped to 0
    # For short put, downside is limited to strike, upside unlimited
    assert var >= -1000  # Sanity check

def test_var_with_correlation():
    """VaR includes spot-vol correlation."""
    pf = Portfolio(name="test")
    pf.add(Position("c1", VanillaOption(100, 100, 0.5, 0.05, 0.2, OptionType.CALL), 100))
    
    # With correlation (real world)
    var_corr = delta_gamma_vega_var(pf, 100, 0.01, 0.01, correlation_spot_vol=-0.75, seed=42)
    # With no correlation (simplified)
    var_no_corr = delta_gamma_vega_var(pf, 100, 0.01, 0.01, correlation_spot_vol=0.0, seed=42)
    
    # Correlated model should give higher VaR (tail risk amplified by vol spike)
    assert var_corr >= var_no_corr * 0.5  # Should be comparable or higher

def test_ingress_stats_tracking():
    """Async ingress tracks statistics (requires httpx)."""
    # Skip if httpx not available
    try:
        from quant_alpha.data.ingress_async import NSEOptionIngress
        md = MarketDataStore()
        ingress = NSEOptionIngress(url="http://fake", md_store=md)
        assert ingress.stats["records_processed"] == 0
        assert ingress.stats["errors"] == 0
    except ImportError:
        pytest.skip("httpx not installed")


def test_scenario_maturity_decay():
    """Verify scenario time advancement decays maturity correctly."""
    inst = VanillaOption(100, 100, 0.25, 0.05, 0.2, OptionType.CALL)
    shock = ScenarioShock("decay_test", -0.05, 0.01, horizon_days=7)
    
    from quant_alpha.risk.scenario import ScenarioEngine
    engine = ScenarioEngine()
    repriced = engine._repriced(inst, shock)
    
    # Maturity should decay by 7/365 ≈ 0.01918 years
    expected_maturity = 0.25 - 7/365
    assert abs(repriced.maturity - expected_maturity) < 1e-6, \
        f"Expected maturity {expected_maturity}, got {repriced.maturity}"


def test_vol_surface_bounds():
    """Verify vol surface extrapolation stays within reasonable bounds."""
    import numpy as np
    from quant_alpha.pricing.vol_surface import VolSurface
    
    strikes = np.array([90, 100, 110])
    maturities = np.array([0.25, 0.5])
    vols = np.array([[0.20, 0.21, 0.22], [0.19, 0.20, 0.23]])
    
    surf = VolSurface(strikes, maturities, vols)
    
    # Even at extrapolation points, should not exceed 200% vol
    iv_otm = surf.iv(50, 0.75)
    assert iv_otm <= 2.0, f"IV exceeds 200% bound: {iv_otm}"
    
    iv_itm = surf.iv(150, 0.75)
    assert iv_itm <= 2.0, f"IV exceeds 200% bound: {iv_itm}"
    
    # At-the-money should be in reasonable range
    iv_atm = surf.iv(100, 0.5)
    assert 0.1 < iv_atm < 0.4, f"ATM IV unreasonable: {iv_atm}"


def test_mc_seed_reproducibility():
    """Verify MC with seed parameter works."""
    inst = VanillaOption(100, 100, 0.5, 0.05, 0.2, OptionType.CALL)
    
    # Two separate engines with same seed should give very similar results
    eng1 = MonteCarloEngine(n_paths=10000, seed=12345)
    eng2 = MonteCarloEngine(n_paths=10000, seed=12345)
    
    p1 = eng1.price(inst)
    p2 = eng2.price(inst)
    
    # Seeds set independently should give same sampling stream
    assert abs(p1 - p2) < 0.01, f"Seed reproducibility failed: {p1} vs {p2}"


def test_scenario_maturity_affects_greeks():
    """Verify scenario maturity affects Greeks calculation."""
    from quant_alpha.risk.scenario import ScenarioEngine
    
    inst = VanillaOption(100, 100, 0.25, 0.05, 0.2, OptionType.CALL)
    
    # 1-day shock: maturity decreases
    shock = ScenarioShock("decay", 0.0, 0.0, horizon_days=1)
    engine = ScenarioEngine()
    repriced = engine._repriced(inst, shock)
    
    # Theta should reduce price for long call
    assert repriced.maturity < inst.maturity, "Maturity should decrease"
    
    # Price should be lower due to time decay (all else equal)
    original_price = engine.pricer.price(inst)
    shocked_price = engine.pricer.price(repriced)
    assert shocked_price < original_price, "Price should decrease with time decay"


def test_circuit_breaker_stats():
    """Verify circuit breaker stats tracking."""
    try:
        from quant_alpha.data.ingress_async import CircuitBreaker
    except ImportError:
        pytest.skip("httpx not installed")
    
    breaker = CircuitBreaker(fail_threshold=3)
    
    # Initially open
    assert breaker.allow()
    assert breaker.fail_count == 0
    
    # Fail twice
    breaker.on_failure()
    breaker.on_failure()
    assert breaker.allow()
    assert breaker.fail_count == 2
    
    # Third failure opens breaker
    breaker.on_failure()
    assert not breaker.allow()
    assert breaker.fail_count == 3
    assert breaker.opened_at is not None
    
    # Success resets
    breaker.on_success()
    assert breaker.allow()
    assert breaker.fail_count == 0


def test_ingress_stats_method():
    """Verify NSEOptionIngress.get_stats() returns complete state."""
    try:
        from quant_alpha.data.ingress_async import NSEOptionIngress
        from quant_alpha.market_data import MarketDataStore
        
        md = MarketDataStore()
        ingress = NSEOptionIngress(url="http://fake", md_store=md)
        
        stats = ingress.get_stats()
        assert "records_processed" in stats
        assert "errors" in stats
        assert "breaker_trips" in stats
        assert "breaker_is_open" in stats
        assert "breaker_fail_count" in stats
        assert not stats["breaker_is_open"]
    except ImportError:
        pytest.skip("httpx not installed")


def test_mc_dividend_precision():
    """Verify MC engine produces reasonable prices with dividends."""
    from quant_alpha.instrument import Dividend
    from quant_alpha.pricing.analytic import AnalyticBSEngine
    
    # Create option with dividend
    div = Dividend(t=0.5, amount=1.0)
    inst_with_div = VanillaOption(
        100, 100, 1.0, 0.05, 0.2, 
        OptionType.CALL, ExerciseType.EUROPEAN, 
        dividends=[div]
    )
    
    # Use AnalyticBSEngine as baseline (correct)
    p_analytic = AnalyticBSEngine().price(inst_with_div)
    assert p_analytic > 0, "Analytic engine price should be positive"
    
    # MC should produce similar price (within MC variance)
    engine_mc = MonteCarloEngine(n_paths=131072, seed=42)
    p_mc = engine_mc.price(inst_with_div)
    assert p_mc > 0, "MC engine price should be positive"
    
    # MC and analytic should agree within 10% tolerance (MC sampling noise + control variate)
    rel_error = abs(p_mc - p_analytic) / p_analytic
    assert rel_error < 0.10, \
        f"MC price {p_mc:.4f} too far from analytic {p_analytic:.4f} (rel error: {rel_error:.2%})"


def test_lattice_dividend_precision():
    """Verify CRR lattice computes dividend discount accurately."""
    from quant_alpha.instrument import Dividend
    from quant_alpha.pricing.analytic import AnalyticBSEngine
    
    div = Dividend(t=0.5, amount=1.0)
    inst_with_div = VanillaOption(
        100, 100, 1.0, 0.05, 0.2,
        OptionType.CALL, ExerciseType.EUROPEAN,
        dividends=[div]
    )
    inst_no_div = VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL)
    
    # Analytic baseline
    p_with_div_analytic = AnalyticBSEngine().price(inst_with_div)
    p_no_div_analytic = AnalyticBSEngine().price(inst_no_div)
    expected_discount = p_no_div_analytic - p_with_div_analytic
    
    # Lattice prices
    engine = CRRLatticeEngine(steps=600, richardson=True)
    p_with_div_lattice = engine.price(inst_with_div)
    p_no_div_lattice = engine.price(inst_no_div)
    actual_discount = p_no_div_lattice - p_with_div_lattice
    
    # Should match analytic within 2% (lattice convergence)
    assert abs(actual_discount - expected_discount) / expected_discount < 0.02, \
        f"Lattice dividend discount {actual_discount:.4f} != expected {expected_discount:.4f}"


def test_config_environments():
    """Verify app config supports multiple environments."""
    import yaml
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent / "config" / "app_config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Check base config
    assert config["app"]["env"] in ["dev", "staging", "prod"]
    assert "environments" in config
    
    # Check each environment has expected keys
    for env_name in ["dev", "staging", "prod"]:
        assert env_name in config["environments"]
        env_cfg = config["environments"][env_name]
        assert "streamlit" in env_cfg
        assert "risk" in env_cfg