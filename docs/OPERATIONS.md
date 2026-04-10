# Operations Guide

Deployment, monitoring, performance optimization, and operational best practices.

---

## Environment Setup

### Development Environment

```bash
# Clone repository
git clone https://github.com/Anuragpatkar/quant_alpha_pricing_engine.git
cd quant_alpha_pricing_engine

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# or
.\.venv\Scripts\Activate.ps1     # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Verify installation
pytest -q
mypy quant_alpha/
ruff check quant_alpha/
```

### Staging/Production Setup

```bash
# Same as dev, but use prod config
export APP_ENV=prod    # Unix
# or
$env:APP_ENV="prod"    # PowerShell

# Verify with prod settings
python -c "from config.app_config import load_config; print(load_config())"
```

---

## Configuration Management

### Config File Locations

- **App config**: `config/app_config.yaml` — Environment-specific settings
- **Logging config**: `config/logging.yaml` — Log levels, handlers, formatters
- **Runtime overrides**: Environment variables (by design, currently YAML-only)

### Configuration Hierarchy

```yaml
# Default (in code)
{
  max_mc_paths: 131072,
  log_level: "INFO"
}

# Override by environment (app_config.yaml)
environments:
  dev:
    streamlit:
      max_mc_paths: 131072    # Dev: lower
    risk:
      log_level: DEBUG
  prod:
    streamlit:
      max_mc_paths: 262144    # Prod: higher
    risk:
      log_level: WARNING

# Runtime override (future: environment variables)
export MAX_MC_PATHS=524288
```

### Loading Configuration

```python
from config.app_config import load_config

config = load_config()
env = config.app.env  # "dev", "staging", or "prod"

# Access environment-specific settings
if env == "prod":
    max_paths = config.environments["prod"].streamlit.max_mc_paths  # 262144
```

---

## Logging & Monitoring

### Structured Logging Setup

```python
import logging
from quant_alpha.utils.logger import setup_logger

logger = setup_logger(__name__)

# Levels: DEBUG < INFO < WARNING < ERROR < CRITICAL
logger.debug("Low-level event: x={x}")
logger.info("Important milestone: instrument validated")
logger.warning("Potential issue: vol surface extrapolation")
logger.error("Operational failure: API timeout after 5 retries", exc_info=True)
logger.critical("System malfunction: circuit breaker open")
```

### Logging Best Practices

1. **Log request + response**: API calls, pricing requests
2. **Log rejections**: Validation failures, limit breaches
3. **Log timing**: Slow operations (>100ms), bottlenecks
4. **Avoid sensitive data**: No passwords, no API keys in logs
5. **Use exc_info=True**: For exception details

**Example**:
```python
logger.info(f"Pricing {len(portfolio.positions)} positions")
start = time.time()
pnl = engine.price(instrument)
elapsed = time.time() - start
logger.debug(f"Price computed in {elapsed*1000:.1f}ms: ${pnl:.2f}")
```

### Monitored Metrics

| Metric | Target | Alert |
|--------|--------|-------|
| API response time | <500ms | >2s |
| Data freshness | <5s old | >30s |
| Pricing latency | <50ms | >200ms |
| Risk report time | <10s | >30s |
| Error rate | 0% | >1% |
| Memory usage | <500MB | >2GB |

---

## Performance Optimization

### Profiling Pricing Engines

```bash
python scripts/profile_engine.py
```

**Output**:
```
Profiling 10,000 prices per engine...

AnalyticBSEngine:
  Total: 1.23s, per-option: 0.123ms, percentiles: p50=0.082ms, p95=0.156ms, p99=0.201ms

CRRLatticeEngine (500 steps, Richardson):
  Total: 31.2s, per-option: 3.12ms, percentiles: p50=2.95ms, p95=3.45ms, p99=3.89ms

MonteCarloEngine (131k paths, Sobol, antithetic, control variate):
  Total: 152.1s, per-option: 15.21ms, percentiles: p50=14.89ms, p95=16.23ms, p99=17.45ms
```

### Latency SLAs

| Engine | Target | Accuracy |
|--------|--------|----------|
| Analytic | <1ms | ±0% (reference) |
| Lattice | <5ms | ±0.1% |
| MC | <20ms | ±0.05 bps |

### Memory Optimization

```python
# Cache intermediate Greeks calculations
@functools.lru_cache(maxsize=1000)
def get_greeks(spot, strike, T, r, vol, is_call):
    return bs_greeks_vectorized(spot, strike, T, r, vol, is_call)

# Clear cache periodically (market moves invalidate cached values every tick)
if time.time() - last_clear > 60:  # Clear every minute
    get_greeks.cache_clear()
    last_clear = time.time()
```

### Numba JIT Benefits

Compilation overhead amortized over many calls:

```python
# First call: ~100ms (compilation)
result1 = _gbm_terminal_vectorized(100, 0.05, 0.2, 0.25, z)

# Succ. calls: <1ms (compiled code)
result2 = _gbm_terminal_vectorized(100, 0.05, 0.2, 0.25, z)
```

**Production setting**: Compile during startup; cache compiled functions.

---

## Scaling Deployments

### Single-Machine Deployment

```
┌─────────────────┐
│  Streamlit App  │
│  (Web UI)       │
└────────┬────────┘
         │
  ┌──────▼──────────┐
  │  Python Process │
  │  - Pricing      │
  │  - Risk calc    │
  │  - Data ingress │
  └────────┬────────┘
           │
    ┌──────▼───────┐
    │ SQLite/JSON  │
    │   (local)    │
    └──────────────┘
```

**Suitable for**: Single trader, research, backtesting (<100 positions).

### Multi-Machine Deployment (Future)

```
┌────────────────────────┐
│  Load Balancer         │
│  (reverse proxy)       │
└───────────┬────────────┘
            │
    ┌───────┴────────┬──────────┐
    │                │          │
┌───▼──────┐  ┌──────▼──┐  ┌────▼───┐
│Pricing   │  │ Pricing  │  │Pricing │
│ Svc 1    │  │  Svc 2   │  │ Svc 3  │
└───┬──────┘  └──────┬───┘  └────┬───┘
    │                │          │
    └────────┬───────┴──────────┘
             │
      ┌──────▼──────────┐
      │  Central Cache  │
      │  (Redis)        │
      └─────────────────┘
```

**For**: Institutional desks, multi-trader, real-time feeds.

---

## CLI Operations

### Risk Report Generation

```bash
python scripts/risk_report.py

# Output: JSON summary
{
  "greeks": {
    "delta": 3250.5,
    "gamma": 12.3,
    "vega": 18500.0
  },
  "var_1d_99": 124680,
  "stress": [...],
  "breaches": [],
  "ok": true
}
```

### Engine Profiling

```bash
python scripts/profile_engine.py

# Summary latencies printed to stdout
```

### Quick Sanity Check

```bash
python scripts/quick_check.py

# Verifies:
# - All dependencies importable
# - BS pricing reasonable
# - Greeks aggregation works
# - Risk calculation completes
```

---

## Monitoring & Alerting

### Health Check Endpoint (Future: FastAPI)

```
GET /health
{
  "status": "OK",
  "data_age_sec": 2.1,
  "symbols_updated": 47,
  "last_error": null,
  "var_timestamp": "2024-04-10T15:32:15Z",
  "memory_mb": 145.2
}
```

### Alert Conditions

```python
def continuous_monitoring(store: MarketDataStore):
    """Background monitoring thread."""
    
    while True:
        # Check data freshness
        age = time.time() - store._last_update
        if age > 300:  # 5 minutes stale
            alert("DATA_STALE", f"No updates for {age}s")
        
        # Check error rate
        errors = store.stats.get('callback_errors', 0)
        if errors > 100:
            alert("HIGH_ERROR_RATE", f"{errors} callback errors")
        
        # Check memory
        mem_mb = psutil.Process().memory_info().rss / 1e6
        if mem_mb > 1000:
            alert("HIGH_MEMORY", f"{mem_mb}MB (limit: 1GB)")
        
        time.sleep(60)
```

---

## Troubleshooting

### Common Issues

#### 1. Import Error: `ModuleNotFoundError: No module named 'quant_alpha'`

**Cause**: Not in virtual environment or not installed.

**Fix**:
```bash
source .venv/bin/activate
pip install -e .  # Editable install
```

#### 2. Numba JIT Error: `numba.core.errors.CompilationError`

**Cause**: Type mismatch in JIT function.

**Fix**: Ensure all inputs to `@njit` functions are numpy arrays or scalars.

```python
# Bad: Passing list
z = [1.0, 2.0, 3.0]
result = _gbm_terminal_vectorized(..., z)  # ERROR

# Good: Convert to numpy
z = np.array([1.0, 2.0, 3.0])
result = _gbm_terminal_vectorized(..., z)  # OK
```

#### 3. Slow Pricing (>100ms)

**Check profiling**:
```bash
python -m cProfile -s cumtime scripts/profile_engine.py
```

**Common causes**:
- Richardson extrapolation doubling lattice steps
- Monte Carlo with too few variance reduction techniques
- Volume of options being priced

**Fix**:
- Use Analytic BS where possible (not American, not exotic)
- Increase MC path count if variance too high (control variates help)

#### 4. VaR Spikes Unexpectedly

**Cause**: Market move correlation assumption might be violated; tail event happened.

**Diagnostic**:
```python
# Check correlation in last 500 ticks
spot_returns = np.diff(np.log(spot_prices))
vol_changes = np.diff(iv_levels)
corr = np.corrcoef(spot_returns, vol_changes)[0, 1]
logger.info(f"Observed spot-vol correlation: {corr:.3f} (model: -0.75)")
```

---

## Deployment Checklist

- [ ] All tests pass: `pytest -q`
- [ ] Type checking passes: `mypy quant_alpha/`
- [ ] Linting passes: `ruff check quant_alpha/`
- [ ] Coverage acceptable: `pytest --cov=quant_alpha --cov-report=term-missing` (≥80%)
- [ ] Profile acceptable: `python scripts/profile_engine.py` (latencies <SLA)
- [ ] Risk report works: `python scripts/risk_report.py` (no errors)
- [ ] Config validated: `python -c "from config import load_config; load_config()"`
- [ ] No hardcoded credentials: grep for passwords/API keys
- [ ] Documentation updated: README, docstrings, comments
- [ ] Changelog updated: Version bumped, changes documented

---

## Maintenance

### Regular Tasks

**Daily**:
- Monitor error logs
- Check data freshness
- Verify Greeks/VaR accuracy

**Weekly**:
- Review slow query logs
- Update market data feeds if needed

**Monthly**:
- Refactor code smells
- Update dependencies (security)
- Review & update limits

**Quarterly**:
- Backtest model accuracy
- Stress test with historical scenarios
- Review roadmap progress

---

## Disaster Recovery

### Backup Strategy

```bash
# Daily automated backups
0 2 * * * tar -czf /backup/quant_alpha_$(date +%Y%m%d).tar.gz /path/to/project/

# Store in S3 (cloud backup)
aws s3 sync /backup s3://my-backups/quant-alpha/
```

### Recovery Procedure

```bash
# Restore from backup
tar -xzf /backup/quant_alpha_20240410.tar.gz -C /path/to/restore/

# Re-initialize venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests to verify
pytest -q
```

---

## References

- **Monitoring**: Prometheus + Grafana (cloud observability)
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **CI/CD**: GitHub Actions, GitLab CI, Jenkins
- **Containerization**: Docker for reproducible environments
- **Orchestration**: Kubernetes for multi-machine scaling

---
