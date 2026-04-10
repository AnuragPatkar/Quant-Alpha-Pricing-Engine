from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.risk.models import Position, Portfolio, RiskLimits
from quant_alpha.risk.scenario import ScenarioShock
from quant_alpha.risk.limits import evaluate_limits

def build_demo_portfolio() -> Portfolio:
    p = Portfolio(name="NIFTY_OPTIONS_BOOK")
    p.add(Position(
        id="C100_ATM",
        quantity=250.0,
        instrument=VanillaOption(spot=100, strike=100, maturity=0.25, rate=0.06, vol=0.22,
                                 option_type=OptionType.CALL, exercise=ExerciseType.EUROPEAN)
    ))
    p.add(Position(
        id="P95_OTM",
        quantity=-180.0,
        instrument=VanillaOption(spot=100, strike=95, maturity=0.25, rate=0.06, vol=0.24,
                                 option_type=OptionType.PUT, exercise=ExerciseType.EUROPEAN)
    ))
    return p

if __name__ == "__main__":
    portfolio = build_demo_portfolio()
    limits = RiskLimits(
        max_abs_delta=5000,
        max_abs_gamma=300,
        max_abs_vega=20000,
        max_var_1d_99=250000,
        max_stress_loss=400000,
    )
    scenarios = [
        ScenarioShock(name="SPOT_DOWN_3_VOL_UP_2", dspot_pct=-0.03, dvol_abs=0.02),
        ScenarioShock(name="SPOT_UP_3_VOL_DOWN_2", dspot_pct=0.03, dvol_abs=-0.02),
        ScenarioShock(name="CRASH_8_VOL_UP_6", dspot_pct=-0.08, dvol_abs=0.06),
    ]

    report = evaluate_limits(
        portfolio=portfolio,
        limits=limits,
        spot=100.0,
        spot_daily_vol=0.012,
        iv_daily_vol_abs=0.01,
        stress_scenarios=scenarios,
    )
    print(report)
