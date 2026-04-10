# Contributing

Guidelines for contributing code, documentation, and ideas to Quant Alpha Pricing Engine.

---

## Code of Conduct

Be respectful, inclusive, and professional. Unacceptable behavior includes harassment, discrimination, and disrespect.

---

## Getting Started

### Fork & Clone

```bash
# Fork repository on GitHub, then clone your fork
git clone https://github.com/Anuragpatkar/quant_alpha_pricing_engine.git
cd quant_alpha_pricing_engine

# Add upstream remote
git remote add upstream https://github.com/original-owner/quant_alpha_pricing_engine.git
```

### Set Up Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# or
.\.venv\Scripts\Activate.ps1     # Windows PowerShell

# Install dependencies (includes dev tools)
pip install -r requirements.txt
pip install pytest-cov ruff mypy pre-commit  # Dev tools

# Set up pre-commit hooks (optional but recommended)
pre-commit install
```

### Verify Setup

```bash
# Run tests
pytest -q

# Check types
mypy quant_alpha/

# Lint
ruff check quant_alpha/
```

All should pass without errors.

---

## Development Workflow

### 1. Create Feature Branch

```bash
# Fetch latest upstream
git fetch upstream main
git checkout -b feature/your-feature upstream/main
```

**Branch naming**:
- `feature/` for new features
- `fix/` for bug fixes
- `docs/` for documentation
- `refactor/` for code improvements
- `perf/` for performance enhancements

### 2. Make Changes

**Code standards**:

#### Type Hints (Required)

```python
# Good ✓
def price(self, inst: VanillaOption) -> float:
    """Price an option."""
    ...

def aggregate_greeks(portfolio: Portfolio) -> AggregatedGreeks:
    """Sum Greeks across positions."""
    ...

# Bad ✗
def price(self, inst):  # Missing type hints
    ...

def calculate(x, y):  # No types, unclear purpose
    ...
```

#### Docstrings (Required)

```python
def delta_gamma_vega_var(
    portfolio: Portfolio,
    spot: float,
    spot_daily_vol: float,
    confidence: float = 0.99,
    horizon_days: int = 1,
) -> float:
    """Calculate Delta-Gamma-Vega Value-at-Risk.
    
    Approximates portfolio P&L using Greeks under bivariate normal
    spot and volatility moves, then finds loss quantile.
    
    Args:
        portfolio: Collection of positions to evaluate.
        spot: Current underlying price.
        spot_daily_vol: Daily spot volatility (e.g., 0.012 = 1.2%).
        confidence: VaR confidence level (default 0.99 = 99%);
                    must be in [0.9, 0.999].
        horizon_days: Risk horizon in days (default 1).
    
    Returns:
        Value-at-Risk in dollars (positive number representing
        maximum expected loss at given confidence level).
    
    Raises:
        ValueError: If inputs are invalid (negative vol, etc.).
    
    Examples:
        >>> var = delta_gamma_vega_var(portfolio, 100, 0.012, 0.99)
        >>> print(f"99% 1D VaR: ${var:,.0f}")
        99% 1D VaR: $124,680
    
    Notes:
        - Uses 500k Monte Carlo samples for tail accuracy.
        - Assumes spot and vol are bivariate normal with ρ = -0.75.
        - Greeks assumed constant over horizon (valid for ≤2% moves).
        
    See Also:
        aggregate_greeks: Portfolio Greeks aggregation.
        ScenarioEngine: For stress testing alternative.
    """
    ...
```

#### Code Style

```python
# Use ruff formatting
# Max line length: 100 characters
# Use explicit imports (avoid star imports)

# Good ✓
from scipy.stats import norm
from quant_alpha.instrument import VanillaOption
from quant_alpha.enums import OptionType

delta = norm.cdf(d1)

# Bad ✗
from scipy.stats import *
from quant_alpha.instrument import *

delta = cdf(d1)  # Ambiguous
```

#### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Good ✓
logger.info(f"Pricing {len(portfolio.positions)} positions")
logger.warning(f"Vol surface extrapolation at strike {strike}")
logger.error(f"Pricing failed for {instrument}", exc_info=True)

# Bad ✗
print(f"Pricing {len(positions)} positions")  # Use logger, not print
logger.debug(f"Position {pos}")  # Too verbose for debug
```

#### Comments

```python
# Good ✓
# Richardson extrapolation: combine two lattice prices for better accuracy
price_2n = _price_n(inst, 2 * self.steps)
return 2.0 * price_2n - price_n  # 2*P(2n) - P(n)

# Bad ✗
p2n = _price_n(inst, 2 * self.steps)  # unclear variable name
return 2 * p2n - pn  # what is this formula?
```

### 3. Write Tests

**Coverage requirement**: All new code must have ≥80% test coverage.

```python
# New feature: Heston volatility calculator
def test_heston_vol_smile():
    """Verify Heston surface produces realistic vol smile."""
    heston = HestonEngine(v0=0.04, kappa=2.0, theta=0.04, sigma=0.5)
    
    strikes = np.array([80, 90, 100, 110, 120])
    maturities = np.array([0.1, 0.25, 0.5])
    
    # Compute vol smile
    vols = np.zeros((len(maturities), len(strikes)))
    for i, T in enumerate(maturities):
        for j, K in enumerate(strikes):
            vols[i, j] = heston.implied_vol(spot=100, strike=K, T=T)
    
    # Check smile shape: higher vol at wings (OTM)
    atm_vol = vols[0, 2]  # ATM at first maturity
    otm_vol = vols[0, 0]  # OTM at strike 80
    
    assert otm_vol > atm_vol, "Smile not present: OTM should have higher vol"

def test_heston_vs_bs_convergence():
    """Heston with low vol-of-vol should approach BS."""
    bs = AnalyticBSEngine()
    heston = HestonEngine(v0=0.2, kappa=100, theta=0.2, sigma=0.01)  # Low vol-of-vol
    
    opt = VanillaOption(100, 100, 0.5, 0.05, 0.2, CALL, EUR)
    
    bs_price = bs.price(opt)
    heston_price = heston.price(opt)
    
    # Should be very close (within 1 bps)
    assert abs(heston_price - bs_price) < 0.01
```

**Test patterns**:

```python
# 1. Functional: "given X, when Y, then Z"
def test_given_itm_call_when_pricing_then_return_positive():
    opt = VanillaOption(110, 100, 0.5, 0.05, 0.2, CALL, EUR)
    price = AnalyticBSEngine().price(opt)
    assert price > 0

# 2. Property: "always true under all reasonable inputs"
@hypothesis.given(
    spot=floats(min_value=1, max_value=1000),
    strike=floats(min_value=1, max_value=1000),
)
def test_call_always_positive(spot, strike):
    opt = VanillaOption(spot, strike, 0.5, 0.05, 0.2, CALL, EUR)
    price = AnalyticBSEngine().price(opt)
    assert price >= 0

# 3. Regression: "matches known good output"
def test_regression_atm_price():
    # From market data or academic paper
    opt = VanillaOption(100, 100, 1.0, 0.05, 0.2, CALL, EUR)
    price = AnalyticBSEngine().price(opt)
    expected = 10.45  # From Table X in Hull (2018)
    assert abs(price - expected) < 0.05
```

### 4. Run Quality Checks

```bash
# Format code (ruff can auto-fix many issues)
ruff check --fix quant_alpha/

# Type checking
mypy quant_alpha/

# Test
pytest -q

# Coverage
pytest --cov=quant_alpha tests/
```

Example output:
```
TOTAL                                    182    30    84%
...
If coverage is <80%, add tests to cover gaps.
```

### 5. Commit Code

**Commit message style** (follows conventional commits):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

**Examples**:

```bash
# Good ✓
git commit -m "feat(pricing): Add Heston stochastic vol model

Implement HestonEngine with numerical integration via Tanh-Sinh quadrature.
Supports both European and American options via numerical methods.

Includes:
- Full Heston PDE solver
- Implied vol extraction via root-finding
- Vectorized computation for portfolio batching

Adds 15 new test cases covering edge cases and regression benchmarks.

Closes #42"

# Bad ✗
git commit -m "add heston"
git commit -m "WIP: debugging"
git commit -m "fix bug" --allow-empty  # No change in commit
```

### 6. Push & Create Pull Request

```bash
git push origin feature/your-feature
```

Go to GitHub and open a Pull Request (PR) with:

1. **Title**: Descriptive, matches commit message
2. **Description**: 
   - What problem does this solve?
   - How does it work (user perspective)?
   - Any limitations or TODOs?
3. **Checklist**:
   - [ ] Tests pass (`pytest -q`)
   - [ ] Types check (`mypy quant_alpha/`)
   - [ ] Linter passes (`ruff check quant_alpha/`)
   - [ ] Coverage maintained (≥80%)
   - [ ] Docstrings updated
   - [ ] CHANGELOG.md updated

**Example PR description**:

```markdown
## Description
Implements Heston stochastic volatility model for realistic vol smile pricing.

## Motivation
Current BS model assumes flat vol and can severely misprice OTM options.
Heston captures empirical vol smile (higher OTM vol) crucial for hedging.

## Changes
- New `HestonEngine` class in `pricing/heston.py`
- Numerical integration via Tanh-Sinh quadrature (oscillatory integrals)
- 2x slower than BS per option (~30ms), but 5% more accurate on OTM

## Testing
- 12 unit tests (edge cases: extreme params, convergence to BS)
- 3 integration tests (cross-validation with market data)
- Coverage: 87% (up from prev)

## Limitations
- Single curve (no multi-curve effects)
- No smile dynamics (surface assumed static)

Fixes #42
```

### 7. Code Review

Maintainer will review your PR:
- **Request changes**: You'll need to iterate
- **Approve**: PR ready to merge

**Typical review points**:
- Does it follow coding standards?
- Are tests sufficient?
- Does documentation match code?
- Any performance issues?
- Will it break existing users?

### 8. Merge

Once approved:
```bash
# Maintainer merges to main
# Your feature branch is deleted
```

You're done! 🎉

---

## Documentation Contributions

### Adding/Updating Docs

1. **Fork & clone** (same as code contributions)

2. **Edit markdown files** in `docs/`:
   - `README.md` — Main overview
   - `docs/ARCHITECTURE.md` — System design
   - `docs/NUMERICAL_METHODS.md` — Math & theory
   - `docs/DATA_PIPELINE.md` — Data flows
   - `docs/RISK.md` — Risk framework
   - `docs/OPERATIONS.md` — Deployment
   - `docs/TESTING.md` — Testing strategy
   - `docs/ROADMAP.md` — Future plans
   - `docs/CONTRIBUTING.md` — This file

3. **Render locally** (recommended):
   ```bash
   # If using Sphinx (future)
   cd docs && make html
   open _build/html/index.html
   ```

4. **Submit PR** with improvements.

### Documentation Standards

- **Clarity**: Write for audience (new users, advanced users, researchers)
- **Accuracy**: Match actual code behavior
- **Examples**: Include runnable code snippets
- **Links**: Cross-reference other docs via markdown links
- **Screenshots**: For UI/dashboard changes

---

## Reporting Issues

### Bug Report Template

```markdown
## Description
Brief summary of the bug.

## Steps to Reproduce
1. Clone repo
2. Run `...`
3. Observe error

## Expected Behavior
What should happen?

## Actual Behavior
What actually happens? Include error traceback.

## Environment
- Python version: 3.11
- OS: macOS/Linux/Windows
- Installation method: pip / editable

## Minimal Reproduction
```python
# Minimal code to trigger bug
...
```

## Workaround (if any)
Temporary fix until patch released.
```

### Feature Request Template

```markdown
## Motivation
Why is this feature useful? What problem does it solve?

## Proposed Solution
How would it work from user perspective?

## Acceptance Criteria
How would we know this is done?

## Alternatives Considered
Any other approaches?
```

---

## Release Process

Maintained will handle releases, but contributors should understand the process:

1. **Bump version** in `pyproject.toml`
   ```toml
   version = "0.2.0"
   ```

2. **Update CHANGELOG** (not tracked yet, planned for v0.2)
   ```markdown
   ## [0.2.0] - 2024-06-15
   ### Added
   - American option support via boundary method
   - Heston stochastic vol model
   
   ### Fixed
   - Vol surface extrapolation crash (issue #42)
   ```

3. **Tag release**
   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0: American options + Heston"
   git push origin v0.2.0
   ```

4. **Publish to PyPI** (future: when project is ready for package distribution)
   ```bash
   python -m build
   twine upload dist/*
   ```

---

## Code Review Checklist (for Maintainers)

Before approving PR:

- [ ] Code follows project standards (types, docstrings, style)
- [ ] Tests pass and coverage ≥80%
- [ ] No breaking changes to public API
- [ ] Relevant docs updated
- [ ] Performance acceptable (no unexpected slowdown)
- [ ] Follows roadmap priorities
- [ ] Commit messages are clean
- [ ] Author has signed CLA (if required in future)

---

## Getting Help

- **Questions**: Open GitHub discussion
- **Ideas**: Open GitHub issue with `[DISCUSSION]` tag
- **Setup problems**: Include full error, Python version, OS

---

## Acknowledgments

Contributors will be:
- Added to CONTRIBUTORS.md file
- Thank you in release notes
- Credited in docs (if substantial contribution)

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT).

---

**Thank you for contributing to Quant Alpha! 🙏**

---
