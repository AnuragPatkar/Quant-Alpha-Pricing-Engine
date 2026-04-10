# System Architecture

Production-grade quantitative derivatives pricing framework with clean layered design and Strategy pattern for pluggable pricing engines.

## Design Principles

1. **Separation of Concerns**: Pricing, risk analytics, and data pipelines are decoupled—pricing engines know nothing about risk or market data
2. **Strategy Pattern**: All pricing engines implement `PricingEngine` interface for pluggable alternatives
3. **Functional Design**: Pure functions where possible; minimal mutable state in core pricing loops
4. **Type Safety**: Full type hints; Pydantic for config validation; no implicit conversions
5. **Vectorization**: NumPy operations for portfolio-scale computing; Numba JIT for hot paths

---

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    UI Layer                                   │
│         (Streamlit Web Dashboard)                            │
│         - Option pricing widget                              │
│         - Vol surface 3D plot                                │
│         - Portfolio Greeks heatmap                           │
│         - Risk limit monitor                                 │
└────────────────┬──────────────────────────────────────────────┘
                 │
┌────────────────┴──────────────────────────────────────────────┐
│              Business Logic Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   Pricing    │  │  Analytics   │  │     Risk     │        │
│  │  (engines)   │  │   (greeks)   │  │ (VaR, limits)│        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└────────────────┬──────────────────────────────────────────────┘
                 │
┌────────────────┴──────────────────────────────────────────────┐
│              Data & Market Layer                               │
│  ┌──────────────────────┐  ┌──────────────────────┐           │
│  │   Market Data Store  │  │   Vol Surface &      │           │
│  │  (pub-sub, threads)  │  │   Option Chain       │           │
│  └──────────────────────┘  └──────────────────────┘           │
└────────────────┬──────────────────────────────────────────────┘
                 │
┌────────────────┴──────────────────────────────────────────────┐
│         Async Data Ingestion Layer                             │
│   (HTTP, circuit breaker, retry logic)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Modules

### 1. **Pricing Engines** (`quant_alpha/pricing/`)

**Design Pattern**: **Strategy Pattern**

All pricing engines inherit from abstract `PricingEngine` base class and implement `price(inst: VanillaOption) -> float`.

#### `engine.py` — Base Interface
```python
class PricingEngine(ABC):
    @abstractmethod
    def price(self, inst: VanillaOption) -> float:
        """Price a vanilla option. Must validate inputs and return positive price."""
```

#### `analytic.py` — Black-Scholes Analytic
- **Purpose**: Fast, closed-form pricing for European options
- **Method**: Standard Black-Scholes formula with d1, d2  
- **Dividend handling**: Historical dividend amounts adjusted via PV
- **Speed**: O(1) — sub-millisecond per option
- **Use case**: Benchmark pricing, Greeks calculation basis, risk reporting

```python
AnalyticBSEngine().price(option)  # ~0.1-0.2 ms
```

#### `lattice.py` — CRR Binomial Lattice
- **Purpose**: American option pricing + model comparison benchmark
- **Method**: Cox-Ross-Rubinstein lattice with optional Richardson extrapolation
- **Steps**: Configurable (default 500); Richardson doubles and extrapolates for accuracy
- **Dividend handling**: Discrete dividends adjusted at payment dates
- **Speed**: O(n²) where n = lattice steps (~2-5 ms for 500 steps)
- **Use case**: American options, validation against BS, early-exercise value estimation

```python
CRRLatticeEngine(steps=500, richardson=True).price(option)  # ~3 ms
```

#### `simulation.py` — Monte Carlo
- **Purpose**: Flexible path-dependent pricing with variance reduction
- **Methods**:
  - **Sobol sequences**: Low-discrepancy quasi-random numbers (vs pseudo-random)
  - **Antithetic variates**: Generate +z and -z pairs for mean cancellation
  - **Control variates**: Use analytical BS price as control to reduce variance
  - **Numba JIT**: Vectorized terminal price computation
- **Paths**: Configurable (default 131k paths for 99th quantile accuracy)
- **Dividend handling**: Not yet implemented for path-dependent logic
- **Speed**: O(n) where n = paths (~10-20 ms for 131k paths)
- **Accuracy**: Sobol + control variate achieves ±0.05 vs BS for European options

```python
MonteCarloEngine(n_paths=131072, use_sobol=True, antithetic=True, 
                 control_variate=True, seed=42).price(option)  # ~15 ms
```

#### `implied_vol.py` — Implied Volatility Extraction
- **Purpose**: Recover market implied vol from observed option price
- **Method**: Hybrid Newton-Raphson + Brent root-finding
  1. Newton-Raphson with vega-based step (fast initial convergence)
  2. Falls back to Brent method if vega becomes too small
- **Bounds**: σ ∈ [1e-8, 10.0] to prevent divergence
- **Convergence**: Tolerance 1e-8, max 50 iterations
- **Use case**: Bootstrapping vol surfaces from market data

```python
iv = implied_vol(market_price=10.5, instrument=option)  # σ ≈ 0.250
```

#### `vol_surface.py` — Volatility Surface
- **Purpose**: 2D cubic spline interpolation across strikes and maturities
- **Data structure**: (n_maturities, n_strikes) grid of implied vols
- **Interpolation**: Natural cubic splines in each dimension
- **Bounds**: Vol clamped to [1e-6, 2.0] to prevent numerical instability
- **Method**: `surface.iv(strike, maturity)` → σ via 2D interpolation
- **Use case**: Vol smile/skew representation, pricing off-grid strikes

```python
surface = VolSurface(strikes=[95, 100, 105, 110, 115],
                     maturities=[0.25, 0.5, 1.0],
                     vols=iv_grid)
sigma_at_105_0p5y = surface.iv(105, 0.5)  # Interpolated IV
```

---

### 2. **Analytics** (`quant_alpha/analytics/`)

#### `greeks.py` — Vectorized Greeks Calculation
- **Purpose**: Compute delta, gamma, vega for portfolios efficiently
- **Method**: Vectorized numpy operations (no Python loops)
- **Greeks**:
  - **Δ (delta)**: ∂price/∂S (directional sensitivity)
  - **Γ (gamma)**: ∂²price/∂S² (delta convexity)
  - **ν (vega)**: ∂price/∂σ (vol sensitivity per 1% move)
- **Broadcast**: All inputs can be scalars or arrays; outputs match shape
- **Edge cases**: Safe handling of T→0 and σ→0 cases
- **Speed**: Vectorized for 10k options in single call (~1 ms)

```python
delta, gamma, vega, d1, d2 = bs_greeks_vectorized(
    S=np.array([98, 100, 102]),
    K=100, T=0.25, r=0.05, sigma=0.20
)
```

#### `cross_greeks.py` — Higher-Order Greeks
- **Purpose**: Rho (rate sensitivity), theta (time decay), lambda decay
- **Implementation**: Analytical via closed-form derivatives or finite difference
- **Use case**: Interest rate hedging, theta P&L tracking

---

### 3. **Risk Framework** (`quant_alpha/risk/`)

#### `models.py` — Core Data Structures

**Position**: Single instrument + quantity
```python
@dataclass(frozen=True)
class Position:
    id: str                      # Unique position ID
    instrument: VanillaOption    # Option contract
    quantity: float              # Count (can be negative for shorts)
```

**Portfolio**: Collection of positions
```python
@dataclass
class Portfolio:
    name: str                    # Portfolio identifier
    positions: List[Position]    # Mutable position list
```

**RiskLimits**: Breach thresholds (Pydantic validated)
```python
class RiskLimits(BaseModel):
    max_abs_delta: float         # Delta limit in directional units ($)
    max_abs_gamma: float         # Gamma limit in convexity units
    max_abs_vega: float          # Vega limit per 1% vol move
    max_var_1d_99: float         # 99% 1-day Value-at-Risk limit
    max_stress_loss: float       # Worst-case scenario loss limit
```

#### `greeks_portfolio.py` — Portfolio Aggregation
- **Purpose**: Sum Greeks across all positions
- **Method**: For each position: Greeks × quantity, then sum
- **Result**: Aggregate delta, gamma, vega
- **Assumption**: No correlation between positions (appropriate for single-stock books)

```python
agg_greeks = aggregate_greeks(portfolio)
# agg_greeks.delta, .gamma, .vega
```

#### `var.py` — Delta-Gamma-Vega VaR
- **Purpose**: Estimate 1-day portfolio loss at 99% confidence
- **Method**: Monte Carlo with spot-vol correlation
  1. Sample spot moves: dS ~ N(0, spot_vol × √T)
  2. Sample vol moves: dV ~ N(0, iv_vol × √T) with ρ = -0.75 correlation
  3. Approximate PnL: ΔdS + ½Γ(dS)² + VdV
  4. Calculate loss quantile: P(PnL < loss) = 0.01
- **Samples**: 500k Monte Carlo paths for tail accuracy
- **Assumptions**:
  - Market moves are bivariate normal (breaks in crashes)
  - Greeks remain constant over 1-day horizon
  - Correlation spot-vol = -0.75 (typical but not universal)

```python
var_1d_99 = delta_gamma_vega_var(
    portfolio=portfolio,
    spot=100, spot_daily_vol=0.012,
    iv_daily_vol_abs=0.01,
    confidence=0.99, horizon_days=1
)  # → 124680 (units same as delta)
```

#### `scenario.py` — Scenario Shocks
- **Purpose**: Stress-test portfolio under hypothetical market moves
- **Shock structure**: Spot move (%), vol move (absolute), rate move (abs), horizon (days)
- **Method**: Reprice all positions under shocked market parameters, compute PnL
- **Scenarios**: User-defined shock ladder

```python
scenarios = [
    ScenarioShock(name="SPOT_DOWN_3_VOL_UP_2", 
                  dspot_pct=-0.03, dvol_abs=0.02),
    ScenarioShock(name="CRASH_8_VOL_UP_6",
                  dspot_pct=-0.08, dvol_abs=0.06)
]
pnls = ScenarioEngine().ladder(portfolio, scenarios)
```

#### `limits.py` — Limit Evaluation
- **Purpose**: Check portfolio against all risk limits in one call
- **Output**: Greeks, VaR, stress results, breach flags
- **Breach logic**: Any limit violation → flagged in `breaches` list

```python
report = evaluate_limits(
    portfolio=portfolio,
    limits=limits,
    spot=100.0,
    spot_daily_vol=0.012,
    iv_daily_vol_abs=0.01,
    stress_scenarios=scenarios
)
# report['breaches'] = [], report['ok'] = True if all OK
```

---

### 4. **Data Pipeline** (`quant_alpha/data/`)

#### `market_data.py` — Thread-Safe Market Store
- **Pattern**: Pub-sub (observer pattern)
- **Thread safety**: RLock on all read/write operations
- **Operations**:
  - `subscribe(symbol, callback)`: Register listener for symbol updates
  - `update_tick(symbol, tick)`: Atomically update and notify listeners
  - `get(symbol)`: Fetch latest tick
- **Error handling**: Callback errors logged, stats tracked, don't crash updates
- **Use case**: Real-time market data distribution to multiple consumers

```python
store = MarketDataStore()

def on_update(symbol, tick):
    print(f"{symbol}: {tick['price']}")

store.subscribe("AAPL", on_update)
store.update_tick("AAPL", {"price": 150.25, "vol": 0.18})
```

#### `ingress_async.py` — Async Data Ingestion
- **Pattern**: Circuit breaker + exponential backoff retry
- **Circuit breaker**: Tracks consecutive failures; opens after threshold, auto-resets after timeout
- **Retry logic**: Exponential backoff with jitter to prevent thundering herd
- **HTTP client**: async httpx for concurrent requests
- **Use case**: Fault-tolerant data fetching from APIs

```python
config = RetryConfig(max_retries=5, base_delay_sec=0.25, max_delay_sec=3.0)
breaker = CircuitBreaker(fail_threshold=5, reset_timeout_sec=15.0)
# Fetch with automatic retries and circuit breaking
data = await fetch_with_retry(url, config, breaker)
```

#### `nse_cleaning.py` — Option Chain Cleaning
- **Purpose**: Standardize NSE/India market option chain data format
- **Cleanings**: Remove stale quotes, validate bid-ask spreads, flag illiquid strikes
- **Output**: Canonical option DataFrame for downstream processing

#### `observers.py` — Data Change Listeners
- **Purpose**: React to market data updates (e.g., trigger repricing)
- **Pattern**: Observer interfaces for pluggable reactions

---

### 5. **Instrument Definition** (`quant_alpha/instrument.py`)

```python
@dataclass
class VanillaOption:
    spot: float              # Current underlying price
    strike: float            # Exercise price
    maturity: float          # Time to expiry (years)
    rate: float              # Risk-free rate (annual)
    vol: float               # Volatility (annual sigma)
    option_type: OptionType  # CALL or PUT
    exercise: ExerciseType   # EUROPEAN or AMERICAN
    dividends: List[Dividend] = field(default_factory=list)
    
    def validate(self):
        """Check all inputs are positive and reasonable."""
        assert self.spot > 0, "Spot must be positive"
        assert self.strike > 0, "Strike must be positive"
        assert self.maturity > 0, "Maturity must be positive"
        # ... etc
```

---

## Data Flow Diagrams

### Pricing Request
```
User Request
    ↓
Select Engine (Analytic/Lattice/MC)
    ↓
Create VanillaOption(spot, strike, T, r, vol, ...)
    ↓
engine.price(option)
    ├─→ Validate instrument
    ├─→ Adjust for dividends
    ├─→ Compute price (engine-specific)
    └─→ Return float (> 0)
    ↓
Display/Log Price
```

### Risk Reporting
```
Portfolio of Positions
    ├─→ aggregate_greeks(portfolio)
    │   └─→ Sum all position Greeks
    │
    ├─→ delta_gamma_vega_var(...)
    │   └─→ 500k Monte Carlo samples → 99th percentile loss
    │
    ├─→ ScenarioEngine().ladder(portfolio, scenarios)
    │   └─→ For each scenario: reprice portfolio → PnL
    │
    └─→ evaluate_limits(...)
        └─→ Check all Greeks, VaR, stress against limits
            └─→ Report breaches
```

### Async Data Ingestion
```
API Request
    ↓
CircuitBreaker.acquire() → Pass/Fail?
    ├─→ Fail: Return cached or raise
    └─→ Pass: proceed
        ↓
    httpx.get() with exponential backoff on failure
        ↓
    Success? → Update MarketDataStore.update_tick()
    Failure? → Log, increment retry counter, retry if budget remains
```

---

## Design Principles

### 1. **Strategy Pattern for Pricing**
All engines implement `PricingEngine` interface → pluggable, tested independently, easy to add new methods.

### 2. **Immutable Positions**
`Position` is frozen dataclass → prevents accidental mutation in multi-threaded contexts.

### 3. **Type Safety**
- Full type hints on all public functions
- Pydantic validators on config inputs
- MyPy type checking in CI

### 4. **Functional Risk Aggregation**
Greeks summed via pure functions (no class state); PnL ladder computed functionally (no side effects).

### 5. **Thread Safety at Boundaries**
- Market store uses RLock for concurrent updates
- Pricing engines are stateless (can call concurrently)
- Numba JIT functions are thread-local

### 6. **Fail-Fast Validation**
- All inputs validated on entry (`VanillaOption.validate()`)
- Edge cases (T→0, σ→0) handled explicitly with guards

### 7. **Configuration Externalization**
YAML configs for environment-specific behavior; Pydantic for validation.

---

## Performance Considerations

### Engine Speed Hierarchy
| Engine | Single Option | 10k Options |
|--------|---------------|------------|
| Analytic BS | 0.1 ms | 1 ms |
| CRR Lattice (500) | 3 ms | 30 s |
| Monte Carlo (131k) | 15 ms | 150 s |

**Implication**: Use MC for research; use BS for real-time risk.

### Memory Footprint
- Position: ~200 bytes
- Portfolio (100 positions): ~20 KB
- Vol surface (5×3×1000 grid): ~120 KB
- No persistent caching → memory-efficient

### Concurrency Notes
- Pricing engines: Safe to call concurrently (no shared state)
- Market store: Thread-safe via RLock
- Numba JIT: Compiles per-thread (first call slower, subsequent cached)

---

## Extension Points

### Adding a New Pricing Engine
1. Subclass `PricingEngine`
2. Implement `price(inst: VanillaOption) -> float`
3. Call `inst.validate()` at start
4. Add test case comparing to Analytic BS (tolerance ±5%)
5. Update `pyproject.toml` if new dependencies

### Adding a New Risk Measure
1. Implement as pure function: `def my_risk(...) -> float:`
2. Call from `evaluate_limits()` risk loop
3. Add to `RiskLimits` validation model
4. Test recovery under synthetic shocks

### Adding a New Greeks
1. Add formula to `greeks.py` (vectorized numpy)
2. Extend `aggregate_greeks()` dataclass
3. Update portfolio output schema

---

## Known Technical Debt

- [ ] MC engine doesn't handle discrete dividends (path-dependent issue)
- [ ] Vol surface extrapolation flat (no SABR/SVI dynamics)
- [ ] Single-threaded pricing (Numba JIT not thread-pooled)
- [ ] No caching layer for repeated pricing calls
- [ ] Risk limits checked sequentially, not in parallel

See [ROADMAP.md](ROADMAP.md) for details.

---
