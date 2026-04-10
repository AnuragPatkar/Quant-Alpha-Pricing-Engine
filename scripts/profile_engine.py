import cProfile
import pstats
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.pricing.simulation import MonteCarloEngine
from quant_alpha.utils.timeit import TailLatencyMonitor

def workload():
    eng = MonteCarloEngine(n_paths=150_000, use_sobol=True, antithetic=True, control_variate=True)
    mon = TailLatencyMonitor(maxlen=10_000)
    inst = VanillaOption(
        spot=100.0, strike=100.0, maturity=0.5, rate=0.05, vol=0.2,
        option_type=OptionType.CALL, exercise=ExerciseType.EUROPEAN
    )
    for _ in range(100):
        mon.wrap(eng.price, inst)
    print("Latency summary:", mon.summary())

if __name__ == "__main__":
    prof = cProfile.Profile()
    prof.enable()
    workload()
    prof.disable()
    pstats.Stats(prof).sort_stats("cumtime").print_stats(20)
