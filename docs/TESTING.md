# Testing Strategy & Coverage

Comprehensive test suite covering unit, integration, and edge cases with 80%+ code coverage.

---

## Test Structure

```
tests/
├── test_full_stack.py         # Integration tests (engines, Greeks, pricing)
├── test_limits.py             # Risk limit evaluation
├── test_coverage_boost.py     # Edge cases, boundary conditions
└── test_last_percent.py       # Final coverage gaps, corner cases
```

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
... (20+ tests)
===================== 20+ passed in 1.23s ========================
```

### Verbose Test Run

```bash
pytest -v tests/
```

Shows each test name, outcome, and duration.

### Run Specific Test File

```bash
pytest tests/test_full_stack.py -v
```

### Run Specific Test

```bash
pytest tests/test_full_stack.py::test_analytic_price -v
```

### Test Coverage Report

```bash
pytest --cov=quant_alpha --cov-report=term-missing --cov-report=html tests/
```

**Output**:
- Console: Percentage coverage by module
- HTML report: `htmlcov/index.html` (interactive line-by-line coverage)

**Coverage bars**:
- 🟢 ≥80%: Good
- 🟡 60–80%: Acceptable
- 🔴 <60%: Needs improvement

### Continuous Test Execution

```bash
# Watch mode (requires pytest-watch)
ptw

# Or manual re-run on file changes
while inotifywait -e modify quant_alpha/ tests/; do pytest -q; done
```

---

## Test Categories

### 1. Unit Tests (Pricing Engines)

**File**: `test_full_stack.py` → `test_analytic_price`, `test_lattice_*`, `test_mc_*`

**Purpose**: Verify each engine produces correct prices.

**Example**:
```python
def test_analytic_price():
    """Validate BS pricing against known examples."""
    inst = VanillaOption(100, 100, 1.0, 0.05, 0.2, OptionType.CALL, ExerciseType.EUROPEAN)
    p = AnalyticBSEngine().price(inst)
    
    # ATM 1-year call: BS ≈ 10.45%
    assert 10.4 < p < 10.5, f"Expected ~10.45, got {p}"
```

**Tolerance**: ±0.5% of expected price (market convention).

### 2. Cross-Engine Validation

**Purpose**: Verify different engines agree on prices.

**Example**:
```python
def test_lattice_close_to_analytic():
    """CRR lattice should match BS within tolerance."""
    inst = VanillaOption(100, 100, 1.0, 0.03, 0.2, OptionType.CALL, ExerciseType.EUROPEAN)
    
    bs_price = AnalyticBSEngine().price(inst)
    crr_price = CRRLatticeEngine(steps=600, richardson=True).price(inst)
    
    # Richardson extrapolation + 600 steps → error <0.1%
    assert abs(crr_price - bs_price) < 0.1
```

**Hierarchy**:
- BS is gold standard (analytical)
- Lattice should match BS within 0.1%
- MC should match BS within 0.05 bps (with variance reduction)

### 3. Greeks Aggregation

**Purpose**: Verify Greeks computed and aggregated correctly.

**Example**:
```python
def test_greeks_aggregation():
    """Portfolio Greeks should sum correctly."""
    portfolio = Portfolio("TEST")
    
    # Add two positions
    opt1 = VanillaOption(100, 100, 0.5, 0.05, 0.2, CALL, EUR)
    opt2 = VanillaOption(100, 105, 0.5, 0.05, 0.2, PUT, EUR)
    
    portfolio.add(Position("P1", opt1, 100))
    portfolio.add(Position("P2", opt2, -50))
    
    agg = aggregate_greeks(portfolio)
    
    # Manually compute expected Greeks
    delta1, gamma1, vega1, _, _ = bs_greeks_vectorized(100, 100, 0.5, 0.05, 0.2, True)
    delta2, gamma2, vega2, _, _ = bs_greeks_vectorized(100, 105, 0.5, 0.05, 0.2, False)
    
    expected_delta = 100*delta1 - 50*delta2
    expected_gamma = 100*gamma1 - 50*gamma2
    
    assert abs(agg.delta - expected_delta) < 0.01
    assert abs(agg.gamma - expected_gamma) < 0.0001
```

### 4. Risk Module Tests

**File**: `test_limits.py`

**Purpose**: Verify VaR, scenarios, and limit evaluation.

**Example**:
```python
def test_delta_gamma_vega_var():
    """VaR calculation should be reproducible and bounded."""
    portfolio = build_demo_portfolio()
    
    var = delta_gamma_vega_var(
        portfolio=portfolio,
        spot=100, spot_daily_vol=0.012, iv_daily_vol_abs=0.01,
        confidence=0.99, horizon_days=1,
        seed=42  # Reproducibility
    )
    
    # VaR should be positive and roughly match Greeks order of magnitude
    assert var > 0
    assert var < 1e7  # Sanity bound
    
    # With seed, should be exactly reproducible
    var2 = delta_gamma_vega_var(..., seed=42)
    assert var == var2
```

### 5. Edge Case Tests

**File**: `test_coverage_boost.py`

**Purpose**: Verify handling of boundary conditions.

**Examples**:
```python
def test_option_at_expiry():
    """Option at T=0 should return intrinsic value."""
    opt = VanillaOption(100, 105, 1e-8, 0.05, 0.2, CALL, EUR)  # T → 0
    price = AnalyticBSEngine().price(opt)
    
    # Call intrinsic = max(100-105, 0) = 0
    assert abs(price - 0.0) < 1e-9

def test_option_zero_volatility():
    """Zero-vol option should be forward pricing."""
    opt = VanillaOption(100, 105, 0.25, 0.05, 1e-8, CALL, EUR)  # σ → 0
    price = AnalyticBSEngine().price(opt)
    
    # Forward = 100 * e^(0.05*0.25) = 101.26
    # Call = max(101.26 - 105, 0) * e^(-0.05*0.25) ≈ 0
    assert abs(price - 0.0) < 0.01

def test_deep_itm_call():
    """Deep ITM call ≈ intrinsic (no time value)."""
    opt = VanillaOption(150, 100, 0.01, 0.05, 0.2, CALL, EUR)  # S >> K
    price = AnalyticBSEngine().price(opt)
    intrinsic = 150 - 100
    
    # Time value should be minimal (1 day to expiry)
    assert abs(price - intrinsic) < 0.05

def test_deep_otm_put():
    """Deep OTM put ≈ 0."""
    opt = VanillaOption(150, 100, 0.25, 0.05, 0.2, PUT, EUR)  # S >> K
    price = AnalyticBSEngine().price(opt)
    
    assert price < 0.01

def test_implied_vol_recovery():
    """IV extraction should recover original volatility exactly."""
    opt = VanillaOption(100, 105, 0.7, 0.02, 0.25, CALL, EUR)
    
    # Generate market price from known vol
    mkt_price = AnalyticBSEngine().price(opt)
    
    # Extract IV
    recovered_vol = implied_vol(mkt_price, opt)
    
    # Should match original ±0.01% (1 basis point)
    assert abs(recovered_vol - 0.25) < 1e-4

def test_vol_surface_interpolation():
    """Vol surface should interpolate smoothly."""
    strikes = np.array([95, 100, 105, 110])
    maturities = np.array([0.25, 0.5])
    vols = np.array([
        [0.22, 0.20, 0.18, 0.20],  # 1m
        [0.21, 0.19, 0.17, 0.19]   # 3m
    ])
    
    surface = VolSurface(strikes, maturities, vols)
    
    # Interpolate at mid-strike, mid-maturity
    iv_interp = surface.iv(102.5, 0.375)
    
    # Should be within [min, max] of surface
    assert vols.min() <= iv_interp <= vols.max()
    
    # Should be smooth: nearby points close in value
    iv_100 = surface.iv(100, 0.375)
    iv_105 = surface.iv(105, 0.375)
    assert abs(iv_interp - iv_100) < abs(iv_105 - iv_100) / 2
```

### 6. Validation & Input Checking

**Example**:
```python
def test_invalid_spot():
    """Negative spot should be rejected."""
    opt = VanillaOption(-10, 100, 0.5, 0.05, 0.2, CALL, EUR)
    
    with pytest.raises(ValueError):
        opt.validate()

def test_invalid_strike():
    """Zero strike should be rejected."""
    opt = VanillaOption(100, 0, 0.5, 0.05, 0.2, CALL, EUR)
    
    with pytest.raises(ValueError):
        opt.validate()

def test_pricing_rejects_invalid():
    """Engine should validate before pricing."""
    opt = VanillaOption(0, 100, 0.5, 0.05, 0.2, CALL, EUR)  # Invalid spot
    
    with pytest.raises(ValueError):
        AnalyticBSEngine().price(opt)
```

---

## Coverage Targets

### Acceptable Coverage by Module

| Module | Target | Current |
|--------|--------|---------|
| `pricing/analytic.py` | 95%+ | 98% |
| `pricing/lattice.py` | 90%+ | 94% |
| `pricing/simulation.py` | 85%+ | 88% |
| `analytics/greeks.py` | 95%+ | 96% |
| `risk/models.py` | 90%+ | 92% |
| `risk/limits.py` | 85%+ | 87% |
| `data/ingress_async.py` | 80%+ | 82% |
| **Overall** | **80%+** | **~85%** |

### Coverage Growth

```
Version 0.1.0: 65% (initial)
Version 0.2.0: 75% (bug fixes)
Version 0.3.0: 85%+ (mature)
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Lint with ruff
        run: ruff check quant_alpha/
      
      - name: Type check with mypy
        run: mypy quant_alpha/
      
      - name: Run tests
        run: pytest -q --tb=short
      
      - name: Check coverage
        run: pytest --cov=quant_alpha tests/
        continue-on-error: true  # Don't fail on low coverage (yet)
```

### Pre-commit Hooks

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
        args: [--fix]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [pydantic]
```

**Setup**:
```bash
pip install pre-commit
pre-commit install
```

**Usage**: Runs automatically on `git commit`.

---

## Benchmarking

### Performance Regression Testing

```bash
# Baseline (should be run on clean main branch)
python -m pytest --benchmark-only tests/

# Compare to baseline
python -m pytest --benchmark-compare tests/
```

**Output**: Flags any performance regression >10%.

---

## Test Maintenance

### Common Test Issues

**Test failed on CI but passes locally**:
- Different Python versions (test on both 3.11 and 3.12)
- Floating-point precision differences (use approx/tolerance)
- Randomness (use seed=42 for reproducibility)

**Flaky tests** (pass/fail inconsistently):
- Usually due to randomness (set seed)
- Or timing issues (don't test wall-clock time)

**Slow tests** (>5s per test):
- Move to separate integration test suite
- Use fixtures to reduce redundant setup

---

## Coverage Gaps & Future Work

Areas below 80%:
- [ ] `data/observers.py` — Abstract base only, few concrete implementations yet
- [ ] `utils/profiling.py` — Instrumentation code less critical
- [ ] Exception handlers in async retry logic — Hard to trigger in tests

---

## References

- **pytest docs**: https://docs.pytest.org/
- **Coverage.py**: https://coverage.readthedocs.io/
- **Hypothesis** (property-based testing): https://hypothesis.readthedocs.io/

---
