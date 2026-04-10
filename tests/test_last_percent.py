from typing import cast
from quant_alpha.types import Tick
from quant_alpha.data.observers import TickObserver
from quant_alpha.pricing.analytic import AnalyticBSEngine
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType

class DummyObserver:
    def on_tick(self, symbol: str, tick):
        self.last = (symbol, tick)

def test_types_tick_usage():
    t: Tick = {"symbol": "NIFTY", "ltp": 22500.0}
    assert t["symbol"] == "NIFTY"
    assert t["ltp"] > 0

def test_observer_protocol_runtime_shape():
    obs = DummyObserver()
    cast(TickObserver, obs)  # structural compatibility check
    obs.on_tick("NIFTY", {"ltp": 1})
    assert obs.last[0] == "NIFTY"

def test_analytic_zero_vol_branch():
    inst = VanillaOption(
        100, 100, 1.0, 0.05, 0.0, OptionType.CALL, ExerciseType.EUROPEAN
    )
    p = AnalyticBSEngine().price(inst)
    assert p >= 0