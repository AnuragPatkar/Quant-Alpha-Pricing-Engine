import tempfile
from pathlib import Path
import numpy as np
import pytest

from quant_alpha.api.schemas import PriceRequest
from quant_alpha.analytics.greeks import bs_greeks_vectorized
from quant_alpha.analytics.cross_greeks import vanna_volga
from quant_alpha.utils.timeit import TailLatencyMonitor
from quant_alpha.utils.logger import setup_logging
from quant_alpha.utils.profiling import run_profile
from quant_alpha.pricing.vol_surface import VolSurface
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.pricing.implied_vol import implied_vol

def test_price_request_schema():
    req = PriceRequest(
        spot=100, strike=100, maturity=1.0, rate=0.05, vol=0.2, option_type="call"
    )
    assert req.spot == 100

def test_greeks_and_cross_greeks():
    d, g, v, d1, d2 = bs_greeks_vectorized(
        S=np.array([100.0]), K=np.array([100.0]), T=np.array([1.0]), r=0.05, sigma=np.array([0.2]), is_call=True
    )
    assert d[0] > 0 and g[0] > 0 and v[0] > 0
    va, vo = vanna_volga(100, 100, 1.0, 0.05, 0.2)
    assert np.isfinite(va).all()
    assert np.isfinite(vo).all()

def test_timeit_monitor():
    m = TailLatencyMonitor()
    out = m.wrap(lambda x: x + 1, 2)
    assert out == 3
    s = m.summary()
    assert s["count"] == 1
    assert s["p50_ms"] is not None

def test_setup_logging_with_missing_file():
    setup_logging("non_existing_logging.yaml")  # should not crash

def test_setup_logging_with_yaml():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "logging.yaml"
        p.write_text(
            "version: 1\n"
            "disable_existing_loggers: false\n"
            "handlers:\n"
            "  console:\n"
            "    class: logging.StreamHandler\n"
            "root:\n"
            "  level: INFO\n"
            "  handlers: [console]\n"
        )
        setup_logging(str(p))  # should not crash

def test_run_profile_smoke():
    run_profile(lambda: sum(range(100)), top_n=1)

def test_vol_surface_more_paths():
    strikes = np.array([90, 100, 110], dtype=float)
    mats = np.array([0.25, 0.5], dtype=float)
    vols = np.array([[0.2, 0.21, 0.22], [0.19, 0.2, 0.23]], dtype=float)
    s = VolSurface(strikes, mats, vols)

    assert s.iv(100, 0.5) > 0
    assert s.iv(100, 0.1) > 0  # left maturity extrap
    assert s.iv(100, 1.0) > 0  # right maturity extrap

def test_implied_vol_branches():
    inst = VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL, ExerciseType.EUROPEAN)
    px = 10.450583572185565
    iv = implied_vol(px, inst)
    assert abs(iv - 0.2) < 1e-3

    with pytest.raises(ValueError):
        implied_vol(-1.0, inst)