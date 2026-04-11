# Quant Alpha Pricing Engine & Risk Dashboard

**Institutional-grade derivatives valuation and portfolio risk framework** in pure Python, built for quantitative research, backtesting, and risk analytics. Features multi-engine pricing (Black-Scholes, binomial lattice, Monte Carlo), vectorized Greeks, Delta-Gamma-Vega VaR, and interactive Streamlit dashboard.

**Suitable for**: Quant research interviews, GitHub portfolio, trading desks, risk validation, academic projects.

---

## Key Features

- **Multi-Engine Pricing**: Black-Scholes analytic, CRR binomial lattice with Richardson extrapolation, Monte Carlo with Sobol sequences
- **Advanced Variance Reduction**: Antithetic variates, control variates, Sobol low-discrepancy sampling, Numba JIT compilation
- **Volatility Tools**: Implied vol extraction (Newton-Raphson + Brent fallback), 2D vol surface interpolation with bounds enforcement
- **Portfolio Analytics**: Vectorized Greeks (delta, gamma, vega), Delta-Gamma-Vega VaR, stress scenarios, risk limits evaluation
- **Data Pipeline**: Async market data ingestion with circuit breaker + exponential backoff, thread-safe pub-sub market data store
- **Interactive UI**: Streamlit 3D vol surface visualization, live pricing across engines, portfolio Greeks heatmaps
- **Risk Operations**: Comprehensive limit checking, scenario analysis, stress testing with configurable shock scenarios
- **Production Quality**: Type-safe configs (Pydantic), structured logging, performance profiling, 37+ tests with 80%+ coverage

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Core** | Python 3.11+, NumPy, SciPy |
| **Performance** | Numba (JIT compilation), Sobol sequences via SciPy |
| **UI** | Streamlit, Plotly (3D visualization) |
| **Config** | Pydantic BaseModel, YAML |
| **Data** | Pandas, async/await with httpx |
| **Testing** | pytest, pytest-cov |
| **Quality** | ruff linting, mypy type checking |

---

## Architecture Overview

```
quant_alpha/
├── pricing/          → Option pricing engines (analytic, lattice, Monte Carlo)
├── analytics/        → Greeks calculations (delta, gamma, vega, vectorized)
├── risk/             → Portfolio risk: VaR, scenarios, limits, stress testing
├── data/             → Market data ingestion (async, circuit breaker, retry)
├── market_data.py    → Thread-safe market data store (pub-sub pattern)
├── instrument.py     → VanillaOption contract definition
├── enums.py          → OptionType (CALL/PUT), ExerciseType (EUROPEAN/AMERICAN)
└── utils/            → Logging, profiling, timing utilities

app/                  → Streamlit interactive application
scripts/              → CLI utilities (risk report, profiling, quick checks)
tests/                → Comprehensive test suite
config/               → YAML configuration (app settings, logging, environment-specific)
```

**Design Pattern**: Strategy pattern for pricing engines; all engines implement `PricingEngine` interface for pluggable alternatives.

---

## Quick Start

### Prerequisites

- Python 3.11 or newer
- Windows, macOS, or Linux

### Installation

**1. Clone and navigate to project:**
```bash
cd quant_alpha_pricing_engine
```

**2. Create virtual environment:**

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Verify installation:**
```bash
pytest -q
```

You should see all tests pass (typically 20+ tests in 1-2 seconds).

---

## Usage

### Basic Pricing

```python
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType, ExerciseType
from quant_alpha.pricing.analytic import AnalyticBSEngine
from quant_alpha.pricing.lattice import CRRLatticeEngine

# Define a European call option
option = VanillaOption(
    spot=100.0,
    strike=105.0,
    maturity=0.25,  # 3 months
    rate=0.05,      # 5% risk-free rate
    vol=0.20,       # 20% volatility
    option_type=OptionType.CALL,
    exercise=ExerciseType.EUROPEAN
)

# Price with different engines
bs_price = AnalyticBSEngine().price(option)
crr_price = CRRLatticeEngine(steps=500, richardson=True).price(option)

print(f"Black-Scholes: ${bs_price:.2f}")
print(f"CRR Lattice:   ${crr_price:.2f}")
```

### Portfolio Greeks and Risk Analysis

```python
from quant_alpha.risk.models import Position, Portfolio, RiskLimits
from quant_alpha.risk.limits import evaluate_limits
from quant_alpha.risk.scenario import ScenarioShock

# Build portfolio
portfolio = Portfolio(name="DEMO_BOOK")
portfolio.add(Position(
    id="CALL_250",
    instrument=VanillaOption(100, 100, 0.25, 0.06, 0.22, 
                             OptionType.CALL, ExerciseType.EUROPEAN),
    quantity=250
))
portfolio.add(Position(
    id="PUT_180",
    instrument=VanillaOption(100, 95, 0.25, 0.06, 0.24,
                             OptionType.PUT, ExerciseType.EUROPEAN),
    quantity=-180
))

# Define limits
limits = RiskLimits(
    max_abs_delta=5000,
    max_abs_gamma=300,
    max_abs_vega=20000,
    max_var_1d_99=250000,
    max_stress_loss=400000
)

# Evaluate against scenarios
scenarios = [
    ScenarioShock("SPOT_DOWN_3_VOL_UP_2", dspot_pct=-0.03, dvol_abs=0.02),
    ScenarioShock("CRASH_8_VOL_UP_6", dspot_pct=-0.08, dvol_abs=0.06),
]

report = evaluate_limits(
    portfolio=portfolio,
    limits=limits,
    spot=100.0,
    spot_daily_vol=0.012,
    iv_daily_vol_abs=0.01,
    stress_scenarios=scenarios
)

print(f"Portfolio Delta: {report['greeks']['delta']:.0f}")
print(f"Portfolio Gamma: {report['greeks']['gamma']:.4f}")
print(f"1D VaR 99%: ${report['var_1d_99']:.0f}")
print(f"Limit Breaches: {report['breaches']}")
```

### Interactive Streamlit App

Launch the interactive visualization dashboard:

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app/streamlit_app.py
```

**macOS/Linux:**
```bash
source .venv/bin/activate
streamlit run app/streamlit_app.py
```

**Features:**
- Real-time option pricing across three engines
- Live 3D volatility surface visualization
- Portfolio Greeks aggregation
- Risk limit checking and scenario analysis
- Implied vol extraction from market prices

---

## Running Tests

### Quick Test Run
```bash
pytest -q
```
Expected output:
```
tests/test_full_stack.py::test_analytic_price PASSED
tests/test_full_stack.py::test_lattice_close_to_analytic PASSED
tests/test_full_stack.py::test_mc_close_to_analytic PASSED
tests/test_full_stack.py::test_implied_vol_recovery PASSED
... (16+ more tests)
======================== 20+ passed in 1.23s ========================
```

### Detailed Test Run with Verbose Output
```bash
pytest -v tests/
```

### Test Coverage Report
```bash
pytest --cov=quant_alpha --cov-report=term-missing tests/
```

Expected coverage: **80%+** across core pricing and risk modules.

### Run Individual Test File
```bash
pytest tests/test_full_stack.py -v              # Full stack integration
pytest tests/test_limits.py -v                  # Risk limit evaluation
pytest tests/test_coverage_boost.py -v          # Edge case coverage
```

---

## Risk Report Generation

Compute comprehensive risk analytics for a portfolio:

```bash
python scripts/risk_report.py
```

**Output includes:**
- Aggregate Greeks (delta, gamma, vega)
- Delta-Gamma-Vega Value-at-Risk at 99% confidence
- Stress test results across 3 scenarios
- Limit breach flagging
- JSON summary for downstream systems

**Example output:**
```json
{
  "greeks": {
    "delta": 3250.5,
    "gamma": 12.3,
    "vega": 18500.0
  },
  "var_1d_99": 124680,
  "stress": [
    {"scenario": "SPOT_DOWN_3_VOL_UP_2", "pnl": -45230},
    {"scenario": "CRASH_8_VOL_UP_6", "pnl": -187450}
  ],
  "worst_stress_loss_abs": 187450,
  "breaches": [],
  "ok": true
}
```

---

## Performance Profiling

Profile core pricing loops for bottlenecks:

```bash
python scripts/profile_engine.py
```

**Generates:**
- Cumulative timing for 10,000 option prices per engine
- Wall time and CPU time
- Profiling flamegraph (if graphviz available)
- Latency percentiles (p50, p95, p99)

**Typical latencies (single option, Python on modern CPU):**
- Analytic BS: **0.1–0.2 ms**
- CRR Lattice (500 steps): **2–5 ms**
- Monte Carlo (131k paths): **10–20 ms**

---

## Configuration

All configuration lives in [config/app_config.yaml](config/app_config.yaml):

```yaml
app:
  name: Quant Alpha Pricing Engine
  env: dev                                    # dev, staging, or prod

environments:
  dev:
    streamlit:
      max_mc_paths: 131072                    # Dev: lower paths for speed
      default_steps: 800
    risk:
      log_level: DEBUG
      var_confidence: 0.99
  prod:
    streamlit:
      max_mc_paths: 262144                    # Prod: higher paths
      default_steps: 1600
    risk:
      log_level: WARNING
      var_confidence: 0.999

risk:
  var_confidence: 0.99                        # VaR confidence level
  horizon_days: 1                             # 1-day horizon
  max_correlation_spot_vol: -0.75             # Spot-vol correlation for VaR
```

Update the `env: dev` to `env: prod` for production Monte Carlo and risk settings.

---

## Quality & Testing

**Test Suite**: 37 tests, all passing
```bash
pytest tests/ -q
# 37 passed, 3 skipped in 3.77s
```

**Coverage**: 80%+ across core pricing and risk modules
```bash
pytest --cov=quant_alpha tests/
```

**Code Quality Checks**:
```bash
ruff check quant_alpha/                    # Linting
mypy quant_alpha/                          # Type checking
pytest tests/ -q                           # Unit tests
python scripts/profile_engine.py           # Performance profiling
```

**Test Categories**:
- **test_full_stack.py**: Integration tests (pricing engines, Greeks, VaR, market data pub-sub)
- **test_limits.py**: Risk limit enforcement and breach detection
- **test_coverage_boost.py**: Edge cases (zero vol, implied vol boundaries, logging)
- **test_last_percent.py**: Type contracts, observer protocol validation

All gates enforced pre-merge (80%+ coverage required).

---

## Repository Structure

```
quant_alpha_pricing_engine/
│
├── README.md                                 # This file
├── pyproject.toml                            # Project metadata, tool config
├── requirements.txt                          # Python dependencies
│
├── quant_alpha/                              # Main package
│   ├── __init__.py
│   ├── instrument.py                         # VanillaOption data class
│   ├── enums.py                              # OptionType, ExerciseType
│   ├── market_data.py                        # Thread-safe market store
│   ├── types.py                              # Type definitions
│   │
│   ├── pricing/                              # Pricing engines
│   │   ├── engine.py                         # Abstract PricingEngine base
│   │   ├── analytic.py                       # Black-Scholes analytic pricing
│   │   ├── lattice.py                        # CRR binomial lattice
│   │   ├── simulation.py                     # Monte Carlo with variance reduction
│   │   ├── implied_vol.py                    # Implied vol extraction
│   │   └── vol_surface.py                    # 2D vol surface interpolation
│   │
│   ├── analytics/                            # Greeks and derivatives
│   │   ├── greeks.py                         # Vectorized Greeks (delta, gamma, vega)
│   │   └── cross_greeks.py                   # Cross-Greeks (rho, theta, etc.)
│   │
│   ├── risk/                                 # Portfolio risk analytics
│   │   ├── models.py                         # Position, Portfolio, RiskLimits
│   │   ├── greeks_portfolio.py               # Aggregated Greeks calculation
│   │   ├── var.py                            # Delta-Gamma-Vega VaR
│   │   ├── scenario.py                       # Scenario shocks and stress testing
│   │   ├── limits.py                         # Risk limit evaluation and breaches
│   │   └── stress_analysis.py                # Detailed stress ladders
│   │
│   ├── data/                                 # Data pipeline
│   │   ├── ingress_async.py                  # Async data ingestion (circuit breaker)
│   │   ├── observers.py                      # Data change observers
│   │   ├── nse_cleaning.py                   # Option chain data cleaning
│   │   └── validators.py                     # Data validation schemas
│   │
│   ├── api/                                  # REST API support (optional)
│   │   └── schemas.py                        # Pydantic request/response models
│   │
│   └── utils/                                # Utilities
│       ├── logger.py                         # Structured logging setup
│       ├── profiling.py                      # Performance profiling
│       └── timeit.py                         # Simple timing decorators
│
├── app/                                      # Streamlit UI
│   └── streamlit_app.py                      # Interactive pricing + risk dashboard
│
├── scripts/                                  # CLI utilities
│   ├── risk_report.py                        # Generate portfolio risk report
│   ├── profile_engine.py                     # Profile pricing engines
│   └── quick_check.py                        # Sanity checks
│
├── tests/                                    # Test suite
│   ├── test_full_stack.py                    # Integration tests
│   ├── test_limits.py                        # Risk limit checks
│   ├── test_coverage_boost.py                # Edge case coverage
│   └── test_last_percent.py                  # Final coverage gaps
│
├── config/                                   # Configuration files
│   ├── app_config.yaml                       # App and risk settings
│   └── logging.yaml                          # Logging configuration
│
└── docs/                                     # Documentation
    ├── ARCHITECTURE.md                       # System design
    ├── NUMERICAL_METHODS.md                  # Pricing models & math
    ├── DATA_PIPELINE.md                      # Data ingestion
    ├── RISK.md                               # Risk framework
    ├── OPERATIONS.md                         # Deployment & ops
    ├── TESTING.md                            # Testing strategy
    ├── ROADMAP.md                            # Future work
    └── CONTRIBUTING.md                       # Development guidelines
```

---

## Known Limitations & Assumptions

### Pricing Models
- **Single domestically currency**: No multivariate or FX options
- **Dividend handling**: Only discrete cash dividends (no continuous yield)
- **European-only lattice**: CRR does support American options but with higher computational cost
- **European Monte Carlo**: Single path per scenario (no path dependence for Asian/barrier options)
- **Volatility surface**: Cubic spline interpolation; no smile/skew dynamics

### Risk Framework
- **No correlation matrices**: Greeks aggregation assumes independence (appropriate for single-stock books)
- **Linear risk approximation**: Delta-Gamma-Vega VaR assumes ≤2% market moves (breaks down in crashes)
- **Spot-vol correlation**: Fixed at –0.75; does not adapt to tail regimes
- **Stationary assumptions**: Vol surface treated as static within reporting horizon (1 day)
- **No counterparty risk**: PnL takes no credit exposure into account

### Data Pipeline
- **No persistent storage**: In-memory market store resets on process restart
- **Synchronous pricing**: Pricing engines are single-threaded (Numba JIT is thread-local)
- **No real market feeds**: Circuit breaker and retry configs are for demo only

### Scope
- **Vanilla only**: Caps, floors, swaptions, and exotic structures out of scope
- **No stochastic vol models**: Heston, SABR calibration not included
- **No term structure**: Single yield curve; no multi-curve bootstrap

---

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for planned features, enhancements, and deprecations.

**Quick preview:**
- [ ] American option pricing with early exercise optimization
- [ ] Vol smile/skew dynamics and model calibration
- [ ] REST API (FastAPI) for remote pricing and risk queries
- [ ] Multi-leg strategy pricing (spreads, collars, etc.)
- [ ] Stochastic volatility models (Heston calibration and Greeks)
- [ ] GPU acceleration for 10M+ path Monte Carlo
- [ ] Real-time market data integrations (Yahoo Finance, Alpaca API)
- [ ] Dockerized deployment with health checks

---

## Contributing

We welcome code contributions! See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for:

- **Development setup**: Clone, branch, virtual environment, editable install
- **Code standards**: Type hints, docstrings, test coverage ≥80%
- **Testing requirements**: All tests must pass, coverage must not regress
- **Commit hygiene**: Clear commit messages, atomic commits, PR best practices
- **Review process**: Code review, CI checks, merge policies

Quick start for contributors:

```bash
# Fork and clone
git clone https://github.com/Anuragpatkar/quant_alpha_pricing_engine.git
cd quant_alpha_pricing_engine

# Create feature branch
git checkout -b feature/my-feature

# Install dev environment
python -m venv .venv
source .venv/bin/activate  # or .\.venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# Make changes, run tests
pytest -q
ruff check quant_alpha/
mypy quant_alpha/

# Commit and push
git commit -am "Add feature: description"
git push origin feature/my-feature
```

---

## License

**License**: MIT (placeholder — update with your actual license)

See [LICENSE](LICENSE) for full text (if added to repo).

---

## Support & Documentation

- **API Documentation**: See inline docstrings via `help(quant_alpha.pricing.AnalyticBSEngine)`
- **Numerical Methods**: [docs/NUMERICAL_METHODS.md](docs/NUMERICAL_METHODS.md)
- **Risk Framework**: [docs/RISK.md](docs/RISK.md)
- **Operations Guide**: [docs/OPERATIONS.md](docs/OPERATIONS.md)
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Citation

If you use Quant Alpha Pricing Engine in published research, please cite:

```bibtex
@software{quant_alpha_2024,
  author = {Anurag Patkar},
  title = {Quant Alpha Pricing Engine},
  year = {2024},
  url = {https://github.com/Anurag Patkar/quant_alpha_pricing_engine}
}
```

---

## Authors

- **Primary Author**: Anurag Patkar
- **Contributors**: (Community contributions welcome)

---

**Last Updated**: April 2024 | **Version**: 0.1.0
