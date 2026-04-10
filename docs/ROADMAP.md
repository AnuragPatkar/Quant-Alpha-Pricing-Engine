# Roadmap

Future development, enhancements, and strategic direction.

---

## Vision

Quant Alpha Pricing Engine will evolve into a **modular, production-grade quantitative finance platform** with institutional-quality pricing, risk analytics, and deployment flexibility.

---

## Planned Features (Phases)

### Phase 2: American Options & Advanced Pricing (Q2 2024)

**Target**: Complete support for American option pricing and improved accuracy.

- [ ] **American option optimization**: Early exercise optimization using optimal boundary methods
- [ ] **Trinomial lattice**: More accurate than binomial for short-dated options
- [ ] **Finite difference methods**: PDE solver for comparison and exotic extensions
- [ ] **Dividend interpolation**: Full dividend yield curves instead of discrete payments
- [ ] **Stochastic rates**: Local rate volatility (if multi-curve available)

**New modules**:
- `pricing/barrier.py` — Barrier options (knock-in, knock-out)
- `pricing/finite_diff.py` — PDE solver for American options

**Testing**: 100+ new test cases, regression benchmarks.

---

### Phase 3: Volatility Surface & Calibration (Q3 2024)

**Target**: Market-realistic vol smile/skew and model calibration.

- [ ] **SABR model**: Two-state stochastic vol model with smile dynamics
- [ ] **Local volatility**: Dupire local vol from option chain
- [ ] **Vol smile fitting**: Parametric (SABR) vs non-parametric (spline) surface fitting
- [ ] **Volatility clustering**: Auto-regressive models (ARCH/GARCH)
- [ ] **Realized vol**: Bootstrap from historical time series
- [ ] **Vol surface evolution**: Time-dependent surface with theta tracking

**Libraries**: scipy.optimize (calibration), statsmodels (GARCH)

**Data format**: Market option chain ingestion and IV extraction (build on existing pipeline).

---

### Phase 4: REST API & Microservices (Q4 2024)

**Target**: Remote pricing and risk queries via HTTP/gRPC.

- [ ] **FastAPI service**: Async HTTP endpoints for pricing, Greeks, risk calculations
- [ ] **Request/response schemas**: Pydantic models with OpenAPI docs
- [ ] **Authentication**: API key validation, rate limiting
- [ ] **Caching layer**: Redis for frequent queries
- [ ] **gRPC alternative**: High-performance alternative to REST
- [ ] **Docker containerization**: Images for easy deployment

**New modules**:
- `api/fastapi_app.py` — REST API server
- `api/grpc_service.py` — gRPC server

**Example endpoints**:
```
POST /price
  {spot, strike, maturity, rate, vol, option_type} → {price, delta, gamma, vega}

POST /portfolio/risk
  {positions, limits} → {greeks, var, stress, breaches}

POST /vol/surface/interpolate
  {strikes[], maturities[], vols[,]} → {surface_interpolator}
```

---

### Phase 5: GPU Acceleration (H1 2025)

**Target**: 10M+ path Monte Carlo on GPU.

- [ ] **CuPy backend**: GPU-accelerated NumPy replacement
- [ ] **CUDA kernels**: Custom Sobol, antithetic, control variate kernels
- [ ] **Throughput**: 100x speedup for large Monte Carlo runs
- [ ] **Memory management**: GPU memory allocation, transfer optimization

**Use case**: Real-time pricing farms (100k+ options/second).

**Libraries**: CuPy, NVIDIA CUDA Toolkit.

---

### Phase 6: Multi-Asset & Exotic Derivatives (H2 2025)

**Target**: Beyond vanilla single-stock options.

- [ ] **Basket options**: Multi-stock weighted options
- [ ] **Spread options**: Option on difference (e.g., calendar spreads)
- [ ] **Asian options**: Path-dependent averaging
- [ ] **Lookback options**: Path-dependent min/max
- [ ] **Callable bonds**: Fixed income optionality
- [ ] **Equity index options**: SPX, VIX volatility derivatives

**Model additions**:
- Correlation matrices (multi-stock covariance)
- Jump-diffusion for crash modeling
- Stochastic interest rates

---

## Bug Fixes & Quality Improvements (Ongoing)

### Current Known Issues

- [ ] **MC dividend handling**: Implement discrete dividend paths
- [ ] **Vol surface edges**: Improve extrapolation beyond boundary strikes
- [ ] **Flat correlation**: Spot-vol ρ currently fixed at -0.75 (should adapt)
- [ ] **Single-threaded pricing**: Numba JIT is current-thread only
- [ ] **VaR tail estimation**: 500k samples may miss 0.01% worst-case

### Refactoring & Technical Debt

- [ ] **Configuration system**: Move from YAML to dataclass-based config
- [ ] **Logging**: Structured JSON logging for log aggregation
- [ ] **Error handling**: Custom exception hierarchy (PricingError, RiskError, etc.)
- [ ] **Documentation**: Sphinx auto-docs from docstrings
- [ ] **Caching**: LRU cache for Greeks, repeated pricing calls

---

## Deprecations & Breaking Changes

### Upcoming Deprecations

| Feature | Current | Deprecated | Removed |
|---------|---------|------------|---------|
| YAML config | v0.1 | v0.3 | v0.5 |
| MarketDataStore.get() | v0.1 | v0.2 | v0.3 |
| `instrument.vol` mutable | v0.1 | v0.2 | v0.3 |

### Migration Path

**Example: YAML → Dataclass config**

**Before (v0.1)**:
```python
from config.app_config import load_config
cfg = load_config()  # Reads YAML
```

**After (v0.2-v0.3)**:
```python
from quant_alpha.config import AppConfig
cfg = AppConfig.from_file("config.toml")  # TOML or JSON
```

**Removal (v0.5)**:
```python
# YAML support removed; use TOML/JSON only
```

---

## Dependency Management

### Current Stack
- Python 3.11+
- NumPy, SciPy, Pandas
- Numba, Streamlit
- Pydantic, PyYAML

### Proposed Additions (Future)

| Phase | Library | Purpose | Version |
|-------|---------|---------|---------|
| 2 | scipy | PDE solvers | ≥1.10 |
| 3 | scikit-learn | vol smile fitting | ≥1.3 |
| 4 | FastAPI | REST API | ≥0.100 |
| 4 | Redis | Caching | ≥4.0 |
| 5 | CuPy | GPU acceleration | ≥12.0 |

### Deprecation Schedule

| Library | Current | Min Version | Reason |
|---------|---------|-------------|--------|
| PyYAML | 6.0 | 5.1 | Config parsing |
| Numba | 0.57+ | 0.50 | JIT compilation |
| NumPy | 1.24+ | 1.20 | Vectorization |

---

## Performance Targets (v1.0)

### Latency SLAs

| Operation | Current | v0.3 | v0.5 | v1.0 |
|-----------|---------|------|------|------|
| BS price (single) | 0.15ms | 0.10ms | 0.08ms | 0.05ms |
| Lattice (500) | 3.2ms | 2.8ms | 2.2ms | 1.5ms |
| MC (131k) | 15ms | 12ms | 8ms | 5ms |
| Portfolio Greeks (100 pos) | 1.5ms | 1.0ms | 0.8ms | 0.5ms |
| Risk report (100 pos) | 2.5s | 1.5s | 0.5s | 0.2s |

### Throughput

| Metric | v0.3 | v1.0 (Target) | Method |
|--------|------|---------------|--------|
| Prices/sec | 6,700 | 20,000 | Single CPU |
| Prices/sec | 100k | 500k | 8 CPU cores |
| Prices/sec | 1M | 10M | GPU |

---

## Documentation & Training

### Planned Content

- [ ] **Video tutorials**: Getting started, pricing walkthrough, risk setup
- [ ] **Jupyter notebooks**: Examples (single option, portfolios, strategies)
- [ ] **Interactive dashboard**: Streamlit for exploration
- [ ] **Research papers**: Pricing methodology validation
- [ ] **Case studies**: Real-world applications (hedging, trading)

---

## Community & Contributions

### Contribution Guidelines

1. **GitHub issues**: Feature requests, bug reports
2. **Pull requests**: Code contributions (80%+ test coverage required)
3. **Discussions**: Design decisions, roadmap input
4. **Sponsorship**: Donations for priority features

### Governance

- **Maintainer**: Anurag Patkar (primary)
- **Collaborators**: TBD (subject to contribution level)
- **Decision process**: Issue discussion → design doc → implementation → review

---

## Success Metrics (v1.0)

- [ ] **50+ GitHub stars**
- [ ] **80%+ test coverage**
- [ ] **Sub-1ms pricing (BS)**
- [ ] **Sub-10ms risk reporting (100 pos)**
- [ ] **10 community contributors**
- [ ] **3+ academic citations** (if published)
- [ ] **Used in production** (1+ institutional desk)

---

## Pricing Example: American Option (Planned)

**Current (v0.1)**:
```python
# Only European support
opt = VanillaOption(..., exercise=ExerciseType.EUROPEAN)
price = AnalyticBSEngine().price(opt)  # Fast
```

**Planned (v0.2)**:
```python
# American option pricing via optimal boundary
opt = VanillaOption(..., exercise=ExerciseType.AMERICAN)
price = BoundaryMethodEngine(steps=500).price(opt)  # Slow but accurate
# or
price = CRRLatticeEngine(steps=500, richardson=True).price(opt)  # Lattice also supports American
```

---

## Risk Enhancements (Future)

**Current (v0.1)**:
- Delta-Gamma-Vega VaR (linear approximation)
- Fixed spot-vol correlation (−0.75)
- 1-day horizon only

**Planned (v0.3)**:
- Full + cva risk (credit exposure)
- Multi-curve yield dynamics
- Adaptive correlation (regime detection)
- Multi-horizon reporting (1D, 5D, 10D, 1M)
- Incremental VaR (per-position contribution)

---

## Investment Areas (If Funded)

If project receives funding or sponsorship:

1. **Performance engineering**: 50% GPU acceleration goal
2. **Documentation**: Video content, courses, certifications
3. **Quality**: Formal verification, fuzzing, property-based testing
4. **Community**: Workshops, hackathons, educational grants
5. **Integration**: Bloomberg, Reuters, market data partnerships

---

## Contact & Feedback

- **GitHub Issues**: Feature requests, bug reports: [issues](https://github.com/Anuragpatkar/quant_alpha_pricing_engine/issues)
- **Discussions**: Ideas & suggestions: [discussions](https://github.com/Anuragpatkar/quant_alpha_pricing_engine/discussions)
- **Email**: contact@yourdomain.com (maintain your own contact)

---

**Last Updated**: April 2024 | **Version**: v0.1.0 Roadmap
