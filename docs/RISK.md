# Risk Framework

Comprehensive guide to portfolio risk measurement, monitoring, and limits enforcement.

---

## Overview

The risk framework provides institutional-grade portfolio analytics:

- **Greeks aggregation**: Fast vectorized delta, gamma, vega calculations
- **Value-at-Risk (VaR)**: Delta-Gamma-Vega VaR with spot-vol correlation
- **Scenario stress testing**: Customizable shock ladders and piecewise analysis
- **Limit enforcement**: Real-time breach detection and alerting

```
Portfolio
  ├─→ aggregate_greeks() → {delta, gamma, vega}
  ├─→ delta_gamma_vega_var() → 99% 1-day loss estimate
  ├─→ ScenarioEngine().ladder() → Stress P&L under shocks
  └─→ evaluate_limits() → Overall risk report with breach flags
```

---

## Core Data Structures

### Position

Single instrument holding:

```python
@dataclass(frozen=True)
class Position:
    id: str                      # Unique identifier
    instrument: VanillaOption    # Underlying option contract
    quantity: float              # Count (can be negative for shorts)
```

**Frozen**: Immutable to prevent accidental mutations in shared state.

**Example**:
```python
pos1 = Position(
    id="SPY_C100_JUN",
    instrument=VanillaOption(100, 100, 0.5, 0.05, 0.20, OptionType.CALL, ExerciseType.EUROPEAN),
    quantity=250
)
```

### Portfolio

Collection of positions:

```python
@dataclass
class Portfolio:
    name: str                     # Portfolio identifier
    positions: List[Position]     # Mutable list of positions
    
    def add(self, p: Position) -> None:
        """Append position to portfolio."""
        self.positions.append(p)
```

**Example**:
```python
portfolio = Portfolio(name="EQUITIES_DESK")
portfolio.add(Position(id="P1", instrument=opt1, quantity=100))
portfolio.add(Position(id="P2", instrument=opt2, quantity=-50))
```

### RiskLimits

Risk limit thresholds with Pydantic validation:

```python
class RiskLimits(BaseModel):
    """Risk limit thresholds. All limits are absolute values."""
    
    max_abs_delta: float = Field(gt=0, description="Absolute delta limit (per $1 spot move)")
    max_abs_gamma: float = Field(gt=0, description="Absolute gamma limit")
    max_abs_vega: float = Field(gt=0, description="Absolute vega limit (per 1% vol)")
    max_var_1d_99: float = Field(gt=0, description="99% 1-day VaR limit")
    max_stress_loss: float = Field(gt=0, description="Max loss under stress")
```

**Example**:
```python
limits = RiskLimits(
    max_abs_delta=5000,         # ±$5,000 per $1 spot move
    max_abs_gamma=300,          # ±300 delta per $1 spot move
    max_abs_vega=25000,         # ±$25,000 per 1% vol move
    max_var_1d_99=500000,       # 99% 1-day loss cap at $500k
    max_stress_loss=750000      # Worst-case scenario cap at $750k
)
```

---

## Greeks: Portfolio Aggregation

### Definition

**Greeks** measure option price sensitivity to market parameters:

| Greek | Formula | Interpretation | Range |
|-------|---------|-----------------|-------|
| **Δ (Delta)** | ∂P/∂S | Change in price per $1 spot move | [0, 1] calls |
| **Γ (Gamma)** | ∂²P/∂S² | Change in delta per $1 spot move | ≥ 0 |
| **ν (Vega)** | ∂P/∂σ | Change in price per 1% vol move | ≥ 0 |

### Calculation

`greeks_portfolio.py` aggregates Greeks across all positions:

```python
def aggregate_greeks(portfolio: Portfolio) -> AggregatedGreeks:
    """Sum Greeks across all positions (vectorized)."""
    
    greeks_list = []
    for position in portfolio.positions:
        # Compute Greeks for single position's instrument
        delta, gamma, vega, _, _ = bs_greeks_vectorized(
            S=position.instrument.spot,
            K=position.instrument.strike,
            T=position.instrument.maturity,
            r=position.instrument.rate,
            sigma=position.instrument.vol,
            is_call=(position.instrument.option_type == OptionType.CALL)
        )
        
        # Scale by quantity
        greeks_list.append({
            'delta': float(delta * position.quantity),
            'gamma': float(gamma * position.quantity),
            'vega': float(vega * position.quantity)
        })
    
    # Sum all positions
    total = {k: sum(g[k] for g in greeks_list) for k in ['delta', 'gamma', 'vega']}
    
    return AggregatedGreeks(
        delta=total['delta'],
        gamma=total['gamma'],
        vega=total['vega']
    )
```

### Example: Portfolio Greeks

```python
portfolio = Portfolio(name="SAMPLE")
portfolio.add(Position("C100_250q", VanillaOption(100, 100, 0.25, 0.06, 0.22, CALL, EUR), 250))
portfolio.add(Position("P95_180q", VanillaOption(100, 95, 0.25, 0.06, 0.24, PUT, EUR), -180))

agg = aggregate_greeks(portfolio)

print(f"Portfolio Delta: {agg.delta:.2f}")   # e.g., +3250.45
print(f"Portfolio Gamma: {agg.gamma:.4f}")   # e.g., +12.30
print(f"Portfolio Vega:  {agg.vega:.2f}")    # e.g., +18500.00
```

**Assumption**: Positions are **independent** (no correlation between Greeks). Appropriate for single-stock portfolios; not suitable for portfolios with correlated underlyings.

---

## Value-at-Risk (VaR)

### Principle

Estimate maximum loss at given confidence level over specified horizon.

**Definition**: 
$$\text{VaR}_{99\%} = \text{loss magnitude at 99th percentile} = P(L > \text{VaR}) = 0.01$$

Where $L$ = loss (negative PnL).

### Delta-Gamma-Vega VaR

In `var.py`: Approximate PnL using Greeks under bivariate normal market moves.

#### Method

**Step 1**: Define market move distributions
- Spot move: $dS \sim N(0, (\sigma_S^2 \cdot h))$ where $\sigma_S$ = daily spot vol, $h$ = horizon
- Vol move: $dV \sim N(0, (\sigma_V^2 \cdot h))$ where $\sigma_V$ = daily IV vol

**Step 2**: Introduce correlation
$$\text{corr}(dS, dV) = -0.75 \quad \text{(spot down, vol up)}$$

Generate correlated samples:
```python
z1 = np.random.standard_normal(n)  # Independent
z2 = np.random.standard_normal(n)  # Independent

dS = sigma_s * np.sqrt(h) * z1
dV = sigma_v * np.sqrt(h) * (rho * z1 + np.sqrt(1 - rho**2) * z2)
```

**Step 3**: Approximate portfolio PnL
$$\Delta \text{PnL} = \Delta \cdot dS + \frac{1}{2}\Gamma(dS)^2 + \nu \cdot dV$$

**Step 4**: Find loss quantile
```python
pnl = delta*dS + 0.5*gamma*(dS**2) + vega*dV
loss_1pct = -np.percentile(pnl, 1.0)  # Flip sign for loss
```

### Implementation

```python
def delta_gamma_vega_var(
    portfolio: Portfolio,
    spot: float,
    spot_daily_vol: float,
    iv_daily_vol_abs: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
    correlation_spot_vol: float = -0.75,
    seed: int | None = None,
) -> float:
    """
    Calculate Delta-Gamma-Vega Value-at-Risk.
    
    Args:
        portfolio: Collection of positions
        spot: Current spot price
        spot_daily_vol: Daily spot volatility (e.g., 0.012 = 1.2%)
        iv_daily_vol_abs: Daily IV volatility in absolute terms (e.g., 0.01 = 100 bps)
        confidence: VaR confidence level (default 0.99 = 99%)
        horizon_days: Risk horizon in days (default 1)
        correlation_spot_vol: Spot-vol correlation (default -0.75)
        seed: Random seed for reproducibility
    
    Returns:
        VaR in dollar terms (positive number)
    
    Raises:
        ValueError: If inputs are out of bounds
    """
    
    if seed is not None:
        np.random.seed(seed)
    
    # Get portfolio Greeks
    g = aggregate_greeks(portfolio)
    
    # Scale variances by horizon
    h = np.sqrt(horizon_days)
    sigma_s = spot * spot_daily_vol * h      # Dollar spot vol
    sigma_v = iv_daily_vol_abs * h            # IV vol
    
    # Monte Carlo samples for tail accuracy
    n = 500_000
    
    # Uncorrelated standard normals
    z1 = np.random.standard_normal(n)
    z2 = np.random.standard_normal(n)
    
    # Correlated market moves
    dS = sigma_s * z1
    dvol = sigma_v * (correlation_spot_vol * z1 + 
                      np.sqrt(max(0.0, 1.0 - correlation_spot_vol**2)) * z2)
    
    # Delta-Gamma-Vega approximation
    pnl = g.delta * dS + 0.5 * g.gamma * (dS ** 2) + g.vega * dvol
    
    # Loss quantile: (1 - confidence) percentile
    q_loss = np.percentile(pnl, (1 - confidence) * 100.0)
    
    # VaR is magnitude of loss (positive)
    return float(-q_loss) if q_loss < 0 else 0.0
```

### Example

```python
portfolio = Portfolio(name="SAMPLE")
portfolio.add(Position("C100_250q", opt_call, 250))
portfolio.add(Position("P95_180q", opt_put, -180))

var_99 = delta_gamma_vega_var(
    portfolio=portfolio,
    spot=100.0,
    spot_daily_vol=0.012,        # 1.2% daily spot vol
    iv_daily_vol_abs=0.01,       # 1% vol point daily move
    confidence=0.99,
    horizon_days=1
)

print(f"99% 1-day VaR: ${var_99:,.0f}")  # e.g., $124,680
```

### Interpretation

"With 99% confidence, we will not lose more than **$124,680** in the next trading day under normal market conditions."

### Assumptions & Limitations

1. **Normality**: Market moves distributed normally (breaks in crashes)
2. **Greeks constant**: Delta/gamma/vega assumed fixed over horizon (violated with large moves)
3. **Fixed correlation**: Spot-vol ρ = −0.75 always (actually regime-dependent)
4. **Linear approximation**: Vega treatment assumes parallel vol shift (ignores skew/smile)
5. **No path dependence**: Single spot & vol levels, not full price path
6. **Tail risk underestimation**: 500k samples may miss extreme tails (<0.1%)

**When it works**: Normal market days with ≤5% moves.

**When it breaks**: Crashes (2008, March 2020), Vol explosions, Gap events, Liquidity crises.

---

## Scenario Stress Testing

### Overview

Evaluate portfolio P&L under hypothetical but realistic market shocks.

### Shock Definition

`ScenarioShock` in `scenario.py`:

```python
@dataclass(frozen=True)
class ScenarioShock:
    name: str                  # Scenario identifier
    dspot_pct: float           # Spot move as % (e.g., -0.08 = -8%)
    dvol_abs: float            # Absolute vol point move (e.g., 0.06 = +600 bps)
    drate_abs: float = 0.0     # Rate move (absolute, e.g., 0.01 = +100 bps)
    horizon_days: float = 0.0  # Days elapsed for theta decay
```

### Scenario Engine

```python
class ScenarioEngine:
    """Apply shocks to portfolio and compute PnL."""
    
    def portfolio_pnl(self, portfolio: Portfolio, shock: ScenarioShock) -> float:
        """Compute shocked P&L under single scenario."""
        
        base_pnl = 0.0
        shocked_pnl = 0.0
        pricer = AnalyticBSEngine()
        
        for position in portfolio.positions:
            # Base PnL: current market price
            base_price = pricer.price(position.instrument)
            base_pnl += position.quantity * base_price
            
            # Shocked PnL: reprice under scenario
            shocked_opt = VanillaOption(
                spot=max(1e-8, position.instrument.spot * (1.0 + shock.dspot_pct)),
                strike=position.instrument.strike,
                maturity=max(1e-6, position.instrument.maturity - shock.horizon_days / 365.0),
                rate=position.instrument.rate + shock.drate_abs,
                vol=max(1e-6, position.instrument.vol + shock.dvol_abs),
                option_type=position.instrument.option_type,
                exercise=position.instrument.exercise,
                dividends=position.instrument.dividends
            )
            shocked_price = pricer.price(shocked_opt)
            shocked_pnl += position.quantity * shocked_price
        
        return shocked_pnl - base_pnl  # P&L = shocked - base
```

### Stress Ladder Example

```python
scenarios = [
    ScenarioShock("NORMAL_DAY", dspot_pct=0.01, dvol_abs=-0.005),
    ScenarioShock("SPOT_DOWN_1", dspot_pct=-0.01, dvol_abs=0.01),
    ScenarioShock("SPOT_DOWN_3", dspot_pct=-0.03, dvol_abs=0.02),
    ScenarioShock("VOL_SPIKE_1", dspot_pct=-0.00, dvol_abs=0.05),
    ScenarioShock("CRASH_8_VOL_UP_6", dspot_pct=-0.08, dvol_abs=0.06),
    ScenarioShock("THETA_DECAY", dspot_pct=0.0, dvol_abs=0.0, horizon_days=1),
]

results = ScenarioEngine().ladder(portfolio, scenarios)

for result in results:
    print(f"{result['scenario']:25} PnL: ${result['pnl']:>10,.0f}")
```

**Sample output**:
```
NORMAL_DAY                 PnL: $-12,340
SPOT_DOWN_1               PnL: $-45,670
SPOT_DOWN_3               PnL: $-98,450
VOL_SPIKE_1               PnL: $-15,230
CRASH_8_VOL_UP_6          PnL: $-187,450
THETA_DECAY               PnL: $-2,100
```

---

## Risk Limit Evaluation

### All-in-One Function

`limits.py` combines Greeks, VaR, scenarios, and breach checking:

```python
def evaluate_limits(
    portfolio: Portfolio,
    limits: RiskLimits,
    spot: float,
    spot_daily_vol: float,
    iv_daily_vol_abs: float,
    stress_scenarios: List[ScenarioShock],
) -> Dict[str, Any]:
    """
    Comprehensive risk report: Greeks, VaR, stress, breaches.
    
    Returns:
        {
            'greeks': {'delta': ..., 'gamma': ..., 'vega': ...},
            'var_1d_99': float,              # Dollar VaR
            'stress': [                      # Scenario results
                {'scenario': str, 'pnl': float},
                ...
            ],
            'worst_stress_loss_abs': float,  # Magnitude of worst loss
            'breaches': [str, ...],          # Limit violations
            'ok': bool                       # All limits satisfied?
        }
    """
    
    # Calculate Greeks
    g = aggregate_greeks(portfolio)
    
    # Calculate VaR
    var_1d_99 = float(delta_gamma_vega_var(...))
    
    # Run stress scenarios
    scen_raw = ScenarioEngine().ladder(portfolio, stress_scenarios)
    scen = [{"scenario": x["scenario"], "pnl": float(x["pnl"])} for x in scen_raw]
    worst_loss = max(abs(x["pnl"]) for x in scen if x["pnl"] < 0)
    
    # Check limits
    breaches = []
    
    if abs(g.delta) > limits.max_abs_delta:
        breaches.append("DELTA_LIMIT")
    if abs(g.gamma) > limits.max_abs_gamma:
        breaches.append("GAMMA_LIMIT")
    if abs(g.vega) > limits.max_abs_vega:
        breaches.append("VEGA_LIMIT")
    if var_1d_99 > limits.max_var_1d_99:
        breaches.append("VAR_1D_99_LIMIT")
    if worst_loss > limits.max_stress_loss:
        breaches.append("STRESS_LOSS_LIMIT")
    
    return {
        "greeks": {
            "delta": float(g.delta),
            "gamma": float(g.gamma),
            "vega": float(g.vega),
        },
        "var_1d_99": var_1d_99,
        "stress": scen,
        "worst_stress_loss_abs": worst_loss,
        "breaches": breaches,
        "ok": len(breaches) == 0,
    }
```

### Example: Full Risk Report

```python
# Build portfolio
portfolio = build_demo_portfolio()

# Set limits
limits = RiskLimits(
    max_abs_delta=5000,
    max_abs_gamma=300,
    max_abs_vega=20000,
    max_var_1d_99=250000,
    max_stress_loss=400000
)

# Define shocks
scenarios = [
    ScenarioShock("SPOT_DOWN_3_VOL_UP_2", dspot_pct=-0.03, dvol_abs=0.02),
    ScenarioShock("CRASH_8_VOL_UP_6", dspot_pct=-0.08, dvol_abs=0.06),
]

# Evaluate
report = evaluate_limits(
    portfolio=portfolio,
    limits=limits,
    spot=100.0,
    spot_daily_vol=0.012,
    iv_daily_vol_abs=0.01,
    stress_scenarios=scenarios
)

# Check report
if report['ok']:
    print(f"✓ All limits satisfied")
    print(f"  Delta: {report['greeks']['delta']:.0f} (limit: {limits.max_abs_delta})")
    print(f"  VaR 99%: ${report['var_1d_99']:,.0f} (limit: ${limits.max_var_1d_99:,.0f})")
else:
    print(f"✗ BREACHES: {', '.join(report['breaches'])}")
    for breach in report['breaches']:
        print(f"  {breach}: action required")
```

---

## Risk Monitoring in Production

### Real-Time Dashboard

```python
import streamlit as st
from quant_alpha.risk.limits import evaluate_limits

# Live market feed → update portfolio
store.subscribe(symbol, callback=update_portfolio_spot_vol)

# Risk calculation loop (every 5 seconds)
st.title("Portfolio Risk Monitor")
placeholder = st.empty()

while True:
    report = evaluate_limits(portfolio, limits, spot, spot_vol, iv_vol, scenarios)
    
    with placeholder.container():
        col1, col2, col3 = st.columns(3)
        col1.metric("Delta", f"{report['greeks']['delta']:.0f}")
        col2.metric("Gamma", f"{report['greeks']['gamma']:.4f}")
        col3.metric("Vega", f"{report['greeks']['vega']:.0f}")
        
        if not report['ok']:
            st.error(f"BREACH: {report['breaches']}")
        else:
            st.success("All limits OK")
    
    time.sleep(5.0)
```

### Alert System

```python
def alert_on_breach(report: Dict) -> None:
    """Send alerts when limits breached."""
    
    if not report['ok']:
        breaches = ", ".join(report['breaches'])
        
        # Slack notification
        slack_message = f"🚨 RISK BREACH: {breaches}\n"
        slack_message += f"Delta: {report['greeks']['delta']:.0f}\n"
        slack_message += f"VaR 99%: ${report['var_1d_99']:,.0f}"
        
        send_slack_alert(slack_message)
        
        # Email notification
        send_email(
            to="risk-team@company.com",
            subject=f"Risk Alert: {breaches}",
            body=json.dumps(report, indent=2)
        )
```

---

## Model Risk & Caveats

### Known Issues

1. **Linear Greeks assumption**: Breaks for >10% moves or >50% vol changes
2. **Spot-vol correlation**: Fixed at -0.75; actual ρ varies by regime
3. **Tail underestimation**: 500k MC samples miss extreme quantiles (<0.01%)
4. **No jump risk**: VaR assumes continuous paths; ignores gap opens
5. **Single curve**: No multi-curve yield, no basis risk, no FX correlation
6. **No convexity**: Gamma treated as constant; actual gamma changes with spot

### Complementary Risk Measures

Use alongside Quant Alpha:
- **Stressed VaR**: Historical stress periods (2008, 2020, etc.)
- **Expected Shortfall (ES)**: Average loss beyond VaR percentile
- **Component VaR**: Marginal contribution of each position
- **Scenario analysis**: Extreme but specific hypothetical moves
- **Backtesting**: Compare realized losses to VaR forecasts

### Governance & Escalation

```
Greek breach
  → Rebalance position
  → Monitor hourly

VaR breach
  → Reduce position size
  → Increase monitoring
  → Daily report

Stress breach
  → Immediate reduction
  → Risk committee alert
  → Executive escalation
```

---

## References

- Jorion (2007): *Value at Risk: The New Benchmark for Managing Financial Risk*
- Hull (2018): *Options, Futures and Other Derivatives*
- Basel Accords: Internal Models Approach (IMA) for market risk capital
- Dowd (2007): *Measuring Market Risk*

---
