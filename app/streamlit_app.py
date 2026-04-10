import logging
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import yaml
from pydantic import BaseModel, Field

from quant_alpha.enums import ExerciseType, OptionType
from quant_alpha.instrument import VanillaOption
from quant_alpha.pricing.analytic import AnalyticBSEngine
from quant_alpha.pricing.implied_vol import implied_vol
from quant_alpha.pricing.lattice import CRRLatticeEngine
from quant_alpha.pricing.simulation import MonteCarloEngine
from quant_alpha.risk.limits import evaluate_limits
from quant_alpha.risk.models import Portfolio, Position, RiskLimits
from quant_alpha.risk.scenario import ScenarioShock

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Page config (must be first Streamlit command)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Quant Alpha Pricing Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Config models
# -----------------------------------------------------------------------------
class StreamlitConfig(BaseModel):
    max_mc_paths: int = Field(default=131072, gt=0, description="Maximum Monte Carlo paths")
    default_steps: int = Field(default=800, gt=0, description="Default lattice steps")


class RiskConfig(BaseModel):
    log_level: str = Field(default="INFO", description="Logging level")
    var_confidence: float = Field(default=0.99, ge=0.9, le=0.999, description="VaR confidence")


class EnvironmentConfig(BaseModel):
    streamlit: StreamlitConfig = Field(default_factory=StreamlitConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)


class AppConfig(BaseModel):
    app: dict = Field(..., description="App configuration")
    environments: dict[str, EnvironmentConfig] = Field(..., description="Environment configurations")


@st.cache_resource
def load_config() -> AppConfig:
    """Load YAML config from config/app_config.yaml, with intelligent path resolution.
    
    Tries multiple strategies:
    1. Parent directory (standard layout: app/ and config/ are siblings)
    2. Current directory (running from project root)
    3. importlib.resources (Python 3.9+) for package installation
    4. Fallback to app subdirectory
    """
    # Try standard project layout: app/ and config/ are siblings
    config_path = Path(__file__).resolve().parent.parent / "config" / "app_config.yaml"
    
    if not config_path.exists():
        # Try config in current working directory
        alt_path = Path.cwd() / "config" / "app_config.yaml"
        if alt_path.exists():
            config_path = alt_path
        else:
            # Try local fallback
            fallback = Path(__file__).resolve().parent / "config" / "app_config.yaml"
            if fallback.exists():
                config_path = fallback
            else:
                raise FileNotFoundError(
                    f"Config file not found. Tried:\n"
                    f"  1. {Path(__file__).resolve().parent.parent / 'config' / 'app_config.yaml'}\n"
                    f"  2. {Path.cwd() / 'config' / 'app_config.yaml'}\n"
                    f"  3. {fallback}\n"
                    f"Please ensure config/app_config.yaml exists in project root."
                )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return AppConfig(**raw)


# -----------------------------------------------------------------------------
# Session state defaults (dark-only theme)
# -----------------------------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state.theme = "Dark"
if "run_mode" not in st.session_state:
    st.session_state.run_mode = "Balanced"
if "show_raw_json" not in st.session_state:
    st.session_state.show_raw_json = True

# -----------------------------------------------------------------------------
# CSS Theme (dark only) + hide Streamlit header chrome
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }

    :root {
      --bg-base: #070b16;
      --bg-grad-1: rgba(56,208,255,0.14);
      --bg-grad-2: rgba(124,156,255,0.18);
      --text: #ecf2ff;
      --muted: #a8b3cf;
      --panel: rgba(255,255,255,0.05);
      --panel-border: rgba(255,255,255,0.14);
      --hero: linear-gradient(135deg, rgba(124,156,255,0.20), rgba(56,208,255,0.10));
      --tab-bg: rgba(255,255,255,0.04);
      --metric-bg: rgba(255,255,255,0.04);
      --metric-border: rgba(255,255,255,0.12);
      --primary-btn-text: #061021;
    }

    html, body, [class*="css"] {
      font-family: "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: var(--text);
    }

    .stApp {
      background:
        radial-gradient(1100px 650px at 5% -10%, var(--bg-grad-1), transparent 60%),
        radial-gradient(1000px 520px at 100% 0%, var(--bg-grad-2), transparent 55%),
        linear-gradient(180deg, var(--bg-base) 0%, var(--bg-base) 100%);
    }

    .block-container {
      max-width: 1400px !important;
      padding-top: 0.9rem !important;
      padding-bottom: 2rem !important;
      padding-left: 2rem !important;
      padding-right: 2rem !important;
    }

    section[data-testid="stSidebar"] .block-container {
      padding-top: 1rem !important;
      padding-left: 1rem !important;
      padding-right: 1rem !important;
    }

    .qa-hero {
      width: 100%;
      box-sizing: border-box;
      margin: 0 0 1rem 0;
      padding: 1.1rem 1.25rem;
      border-radius: 16px;
      border: 1px solid var(--panel-border);
      background: var(--hero);
      backdrop-filter: blur(8px);
    }

    .qa-title {
      margin: 0;
      font-size: 1.95rem;
      font-weight: 800;
      line-height: 1.2;
      letter-spacing: -0.01em;
      color: var(--text);
    }

    .qa-subtitle {
      margin: .35rem 0 0 0;
      font-size: .98rem;
      color: var(--muted);
    }

    .section-label {
      font-size: .82rem;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: #8fa8e6;
      margin-bottom: .4rem;
      font-weight: 700;
    }

    .badge {
      display: inline-block;
      padding: .24rem .55rem;
      border-radius: 999px;
      font-size: .75rem;
      font-weight: 700;
      border: 1px solid transparent;
      vertical-align: middle;
    }

    .ok {
      background: rgba(25,195,125,.14);
      border-color: rgba(25,195,125,.45);
      color: #9dffd7;
    }

    .bad {
      background: rgba(255,93,115,.14);
      border-color: rgba(255,93,115,.45);
      color: #ffc0c8;
    }

    .stTabs [data-baseweb="tab-list"] { gap: .45rem; }
    .stTabs [data-baseweb="tab"] {
      background: var(--tab-bg);
      border-radius: 10px 10px 0 0;
      border: 1px solid var(--panel-border);
      padding: .42rem .85rem;
      font-weight: 600;
    }

    div[data-testid="stMetric"] {
      background: var(--metric-bg);
      border: 1px solid var(--metric-border);
      border-radius: 14px;
      padding: .5rem .75rem;
    }

    button[kind="primary"] {
      border-radius: 12px !important;
      border: 1px solid rgba(255,255,255,.20) !important;
      background: linear-gradient(135deg, #6e8fff 0%, #38d0ff 100%) !important;
      color: var(--primary-btn-text) !important;
      font-weight: 700 !important;
    }

    .stMarkdown p:empty {
      display: none;
      margin: 0;
      padding: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Cached business logic
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def compute_analytics(spot, strike, maturity, rate, vol, opt_type, steps, n_paths):
    inst = VanillaOption(
        spot=spot,
        strike=strike,
        maturity=maturity,
        rate=rate,
        vol=vol,
        option_type=OptionType.CALL if opt_type == "call" else OptionType.PUT,
        exercise=ExerciseType.EUROPEAN,
    )
    inst.validate()

    bs = AnalyticBSEngine().price(inst)
    crr = CRRLatticeEngine(steps=steps, richardson=True).price(inst)
    mc = MonteCarloEngine(n_paths=n_paths, use_sobol=True, antithetic=True, control_variate=True).price(inst)

    try:
        iv = implied_vol(bs, inst)
    except Exception:
        iv = None

    return {
        "black_scholes": float(bs),
        "binomial_tree_crr": float(crr),
        "monte_carlo": float(mc),
        "implied_vol": float(iv) if iv is not None else None,
        "mc_minus_bs": float(mc - bs),
        "crr_minus_bs": float(crr - bs),
    }

# -----------------------------------------------------------------------------
# App init
# -----------------------------------------------------------------------------
config = load_config()
env = config.app.get("env", "dev")
env_cfg = config.environments.get(env, EnvironmentConfig())

# -----------------------------------------------------------------------------
# Sidebar Workspace (cleaned)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Workspace")
    st.caption("Run mode and quick references")

    selected_mode = st.selectbox(
        "Run Mode",
        options=["Balanced", "Fast", "Accurate"],
        index=["Balanced", "Fast", "Accurate"].index(st.session_state.run_mode),
        key="run_mode_selector",
    )
    st.session_state.run_mode = selected_mode

    st.session_state.show_raw_json = st.toggle(
        "Show raw JSON outputs",
        value=st.session_state.show_raw_json,
    )

    st.markdown("#### Engine Stack")
    st.markdown("- Black-Scholes (Analytic)")
    st.markdown("- Binomial Tree (CRR + Richardson)")
    st.markdown("- Monte Carlo (Sobol + Antithetic + Control Variate)")
    st.caption(f"Mode: {st.session_state.run_mode}")

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="qa-hero">
      <p class="qa-title">Quant Alpha Pricing & Risk Dashboard</p>
      <p class="qa-subtitle">
        Environment: <span class="badge ok">{env.upper()}</span>
        &nbsp;Institutional-style option pricing, volatility analytics, and portfolio risk controls.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2, tab3 = st.tabs(["✅ Option Pricing", "🌀 Vol Surface", "🧯 Portfolio Risk"])

# -----------------------------------------------------------------------------
# Tab 1 - Pricing
# -----------------------------------------------------------------------------
with tab1:
    st.markdown('<div class="section-label">Model Inputs</div>', unsafe_allow_html=True)

    mode = st.session_state.run_mode
    if mode == "Fast":
        default_steps = max(200, env_cfg.streamlit.default_steps // 2)
        default_paths = 65536
    elif mode == "Accurate":
        default_steps = min(2000, int(env_cfg.streamlit.default_steps * 1.5))
        default_paths = 262144
    else:
        default_steps = env_cfg.streamlit.default_steps
        default_paths = min(env_cfg.streamlit.max_mc_paths, 131072)

    c1, c2, c3 = st.columns(3)

    with c1:
        spot = st.number_input("Spot", value=100.0, min_value=0.01, step=1.0)
        strike = st.number_input("Strike", value=100.0, min_value=0.01, step=1.0)
        maturity = st.number_input("Maturity (years)", value=1.0, min_value=1e-4, step=0.05)

    with c2:
        rate = st.number_input("Rate", value=0.05, format="%.6f", step=0.005)
        vol = st.number_input("Vol", value=0.2, min_value=1e-6, format="%.6f", step=0.01)
        opt = st.selectbox("Option Type", ["call", "put"])

    with c3:
        steps = st.slider("CRR Steps", 100, 2000, int(default_steps), 100)
        path_choices = [65536, 131072, 262144]
        if default_paths not in path_choices:
            default_paths = 131072
        n_paths = st.selectbox("MC Paths (Sobol-friendly)", path_choices, index=path_choices.index(default_paths))

    if st.button("Run Pricing", type="primary"):
        with st.spinner("Running pricing engines..."):
            try:
                result = compute_analytics(spot, strike, maturity, rate, vol, opt, steps, n_paths)

                st.markdown('<div class="section-label">Pricing Outputs</div>', unsafe_allow_html=True)
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Black-Scholes", f"{result['black_scholes']:.6f}")
                m2.metric("Binomial Tree (CRR)", f"{result['binomial_tree_crr']:.6f}", delta=f"{result['crr_minus_bs']:+.6f}")
                m3.metric("Monte Carlo", f"{result['monte_carlo']:.6f}", delta=f"{result['mc_minus_bs']:+.6f}")
                m4.metric("Implied Vol", f"{result['implied_vol']:.6f}" if result["implied_vol"] is not None else "N/A")

                if st.session_state.show_raw_json:
                    st.caption("Raw pricing output")
                    st.json(result)

                st.success("✅ Pricing complete (cached).")

            except ValueError as e:
                st.error(f"Invalid inputs: {e}")
            except Exception as e:
                st.error(f"Pricing failed: {e}")

# -----------------------------------------------------------------------------
# Tab 2 - Vol surface
# -----------------------------------------------------------------------------
with tab2:
    st.markdown('<div class="section-label">3D Volatility Surface</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        base_vol = st.slider("Base Vol", 0.05, 0.80, 0.18, 0.01)
    with c2:
        smile_curvature = st.slider("Smile Curvature", 0.00, 0.50, 0.12, 0.01)
    with c3:
        term_slope = st.slider("Term Slope", -0.10, 0.20, 0.03, 0.01)
    with c4:
        skew = st.slider("Skew", -0.30, 0.30, 0.00, 0.01)

    k = np.linspace(0.7, 1.3, 35)   # moneyness
    t = np.linspace(0.05, 2.0, 35)  # maturity
    K, T = np.meshgrid(k, t)

    # Dynamic surface
    V = base_vol + smile_curvature * (K - 1.0) ** 2 + term_slope * np.sqrt(T) + skew * (K - 1.0)
    V = np.clip(V, 0.01, 3.0)

    fig = go.Figure(data=[go.Surface(x=K, y=T, z=V, colorscale="Viridis", showscale=True)])
    fig.update_layout(
        template="plotly_dark",
        margin=dict(l=0, r=0, t=10, b=0),
        scene=dict(
            xaxis_title="Moneyness (K/S)",
            yaxis_title="Maturity (Years)",
            zaxis_title="Implied Vol",
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)
# -----------------------------------------------------------------------------
# Tab 3 - Dynamic Portfolio Risk
# -----------------------------------------------------------------------------
with tab3:
    st.markdown('<div class="section-label">Portfolio Risk Snapshot</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        qty_call = st.number_input("Call Qty", value=250, step=10)
        call_strike = st.number_input("Call Strike", value=100.0, step=1.0)
    with c2:
        qty_put = st.number_input("Put Qty", value=-180, step=10)
        put_strike = st.number_input("Put Strike", value=95.0, step=1.0)
    with c3:
        risk_spot = st.number_input("Underlying Spot", value=100.0, min_value=0.01)
        risk_maturity = st.number_input("Maturity (years)", value=0.25, min_value=1e-4)

    r1, r2, r3 = st.columns(3)
    with r1:
        call_vol = st.number_input("Call Vol", value=0.22, min_value=1e-6, format="%.4f")
        put_vol = st.number_input("Put Vol", value=0.24, min_value=1e-6, format="%.4f")
    with r2:
        risk_rate = st.number_input("Risk-free Rate", value=0.06, format="%.4f")
        spot_daily_vol = st.number_input("Spot Daily Vol", value=0.012, min_value=1e-6, format="%.4f")
    with r3:
        iv_daily_vol_abs = st.number_input("IV Daily Vol (abs)", value=0.01, min_value=1e-6, format="%.4f")
        stress_mult = st.slider("Stress Multiplier", 1.0, 3.0, 1.0, 0.1)

    if st.button("Run Risk Report", type="primary"):
        with st.spinner("Running risk engine..."):
            try:
                pf = Portfolio(name="user_portfolio")
                pf.add(
                    Position(
                        "C_USER",
                        VanillaOption(
                            risk_spot, call_strike, risk_maturity, risk_rate, call_vol,
                            OptionType.CALL, ExerciseType.EUROPEAN
                        ),
                        qty_call,
                    )
                )
                pf.add(
                    Position(
                        "P_USER",
                        VanillaOption(
                            risk_spot, put_strike, risk_maturity, risk_rate, put_vol,
                            OptionType.PUT, ExerciseType.EUROPEAN
                        ),
                        qty_put,
                    )
                )

                limits = RiskLimits(
                    max_abs_delta=5000,
                    max_abs_gamma=300,
                    max_abs_vega=20000,
                    max_var_1d_99=250000,
                    max_stress_loss=400000,
                )

                scenarios = [
                    ScenarioShock("SPOT_DOWN_3_VOL_UP_2", -0.03 * stress_mult, 0.02 * stress_mult, horizon_days=1),
                    ScenarioShock("SPOT_UP_3_VOL_DOWN_2", 0.03 * stress_mult, -0.02 * stress_mult, horizon_days=1),
                    ScenarioShock("CRASH_8_VOL_UP_6", -0.08 * stress_mult, 0.06 * stress_mult, horizon_days=1),
                ]

                out = evaluate_limits(
                    portfolio=pf,
                    limits=limits,
                    spot=risk_spot,
                    spot_daily_vol=spot_daily_vol,
                    iv_daily_vol_abs=iv_daily_vol_abs,
                    stress_scenarios=scenarios,
                )

                breaches = out.get("breaches", [])
                if breaches:
                    st.markdown('<span class="badge bad">LIMIT BREACH</span>', unsafe_allow_html=True)
                    st.error(f"Breaches: {', '.join(breaches)}")
                else:
                    st.markdown('<span class="badge ok">ALL LIMITS OK</span>', unsafe_allow_html=True)
                    st.success("✅ All limits are within threshold.")

                if st.session_state.show_raw_json:
                    st.caption("Risk output")
                    st.json(out)

            except Exception as e:
                st.error(f"Risk calculation failed: {e}")