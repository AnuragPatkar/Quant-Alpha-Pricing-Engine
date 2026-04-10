
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.pricing.analytic import AnalyticBSEngine
from quant_alpha.pricing.lattice import CRRLatticeEngine
from quant_alpha.pricing.simulation import MonteCarloEngine
from quant_alpha.pricing.implied_vol import implied_vol

inst = VanillaOption(
    spot=100, strike=100, maturity=1.0, rate=0.05, vol=0.2,
    option_type=OptionType.CALL, exercise=ExerciseType.EUROPEAN
)

bs = AnalyticBSEngine().price(inst)
crr = CRRLatticeEngine(steps=800, richardson=True).price(inst)
mc = MonteCarloEngine(n_paths=120000, use_sobol=True, antithetic=True, control_variate=True).price(inst)
iv = implied_vol(bs, inst)

print("Analytic BS:", bs)
print("CRR+Richardson:", crr)
print("MonteCarlo:", mc)
print("Implied Vol from BS price:", iv)
