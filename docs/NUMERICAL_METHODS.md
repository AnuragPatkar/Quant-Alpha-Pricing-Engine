# Numerical Methods

This document details the mathematical foundations, numerical techniques, and model assumptions underlying all pricing, Greeks, and risk calculations.

---

## Black-Scholes Analytic Pricing

### Formula

For a European vanilla option:

$$C_t = S_t \Phi(d_1) - K e^{-r(T-t)} \Phi(d_2)$$

$$P_t = K e^{-r(T-t)} \Phi(-d_2) - S_t \Phi(-d_1)$$

Where:

$$d_1 = \frac{\ln(S/K) + (r + \frac{\sigma^2}{2})T}{\sigma\sqrt{T}}$$

$$d_2 = d_1 - \sigma\sqrt{T}$$

- $S$: Current spot price
- $K$: Strike price
- $T$: Time to maturity (years)
- $r$: Risk-free rate (continuous)
- $\sigma$: Volatility (annualized)
- $\Phi(\cdot)$: Standard normal CDF

### Implementation (`analytic.py`)

```python
d1 = (np.log(S/K) + (r + 0.5*sigma^2)*T) / (sigma*sqrt(T))
d2 = d1 - sigma*sqrt(T)

call_price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
put_price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
```

### Assumptions

1. **Log-normality**: Stock price follows geometric Brownian motion
   $$dS = \mu S dt + \sigma S dW_t$$

2. **Constant volatility**: $\sigma$ is fixed over $[t, T]$ (violated in reality; see vol smile)

3. **No arbitrage**: Risk-neutral pricing with drift $\mu = r$

4. **No dividends**: Extended via dividend adjustment (PV subtraction)

5. **European exercise**: Only at maturity $T$ (American requires lattice/MC)

6. **Continuous trading**: Can hedge continuously with no friction

### Edge Case Handling

**Case T → 0** (at expiry):
- Intrinsic value: $\max(S - K, 0)$ for call; $\max(K - S, 0)$ for put
- Guard: Check `if T < 1e-6: return intrinsic`

**Case σ → 0** (zero volatility):
- Forward pricing: $\max(e^{-rT}(Se^{rT} - K), 0)$ for call
- Guard: Check `if sigma < 1e-8: use forward pricing`

**Extreme moneyness** (S >> K or S << K):
- Numerical precision: Use $\log$ for ratio, avoid cancellation

---

## Greeks

### Delta (Δ)

Sensitivity to spot price changes: $\Delta = \frac{\partial C}{\partial S}$

**Formula**:

$$\Delta_{\text{call}} = \Phi(d_1)$$

$$\Delta_{\text{put}} = \Phi(d_1) - 1 = \Phi(-d_2)$$  (alternative form)

**Interpretation**: Change in option price per $1 move in spot. Range: [0, 1] for OTM/ITM calls.

**Implementation**: Vectorized in numpy for portfolio aggregation.

### Gamma (Γ)

Convexity of delta: $\Gamma = \frac{\partial^2 C}{\partial S^2} = \frac{\partial \Delta}{\partial S}$

**Formula**:

$$\Gamma = \frac{\phi(d_1)}{S\sigma\sqrt{T}}$$

Where $\phi(x) = \frac{1}{\sqrt{2\pi}}e^{-x^2/2}$ is the standard normal PDF.

**Interpretation**: Rate of delta change per $1 spot move. Always non-negative; highest ATM (short gamma = negative convexity).

**Edge case**: When $\sigma \to 0$, use `np.where()` to avoid division by zero.

### Vega (ν)

Sensitivity to volatility changes: $\nu = \frac{\partial C}{\partial \sigma}$

**Formula**:

$$\nu = S\phi(d_1)\sqrt{T}$$

**Interpretation**: Change in option price per 1% (100 basis points) volatility move.

**Note**: Same for calls and puts; positive (long gamma & vega together).

### Higher-Order Greeks

**Theta (Θ)** — Time decay:
$$\Theta_{\text{call}} = -\frac{S\phi(d_1)\sigma}{2\sqrt{T}} - rK e^{-rT}\Phi(d_2)$$

**Rho (ρ)** — Interest rate sensitivity:
$$\rho_{\text{call}} = KT e^{-rT}\Phi(d_2)$$

---

## Binomial Lattice (CRR)

### Cox-Ross-Rubinstein Model

**Tree construction**:

$$u = e^{\sigma\sqrt{\Delta t}}, \quad d = \frac{1}{u}, \quad p = \frac{e^{r\Delta t} - d}{u - d}$$

Where:
- $n$ = number of steps
- $\Delta t = T/n$ = step size
- $u, d$ = up/down multipliers (symmetric around GM)
- $p$ = risk-neutral probability of up move

**Terminal values**:

$$S_{i,n} = S_0 \cdot u^i \cdot d^{n-i}, \quad i = 0, \ldots, n$$

**Option values** (backward induction):

$$V_{i,j} = e^{-r\Delta t}[p \cdot V_{i+1,j+1} + (1-p) \cdot V_{i,j}]$$

For American options, compare with exercise value at each node:

$$V_{i,j} = \max(V_{\text{discounted}}, V_{\text{intrinsic}})$$

### Convergence to Black-Scholes

As $n \to \infty$, CRR price converges to BS price with error $O(1/n)$.

$$P_{\text{CRR}, n} = P_{\text{BS}} + \frac{c_1}{n} + \frac{c_2}{n^2} + \ldots$$

### Richardson Extrapolation (`lattice.py`)

Improves convergence by combining two lattice prices:

$$P_{\text{Richardson}} = 2 \cdot P_{2n} - P_n$$

**Effect**: Reduces error to $O(1/n^2)$, achieving BS accuracy with 40% fewer steps.

**Implementation**:
```python
pn = _price_n(inst, self.steps)
p2n = _price_n(inst, 2*self.steps)
return 2.0 * p2n - pn  # Richardson formula
```

### Assumptions & Limitations

1. **Discrete moves**: Lattice is recombining (binomial, not trinomial)
2. **Stationary volatility**: σ same on each step
3. **American support**: Only for lattice (CRR), not MC (European only currently)
4. **Computational cost**: O(n²) in memory and time; scales poorly for deep trees

---

## Monte Carlo Simulation

### Geometric Brownian Motion (GBM)

$$S_T = S_0 \exp\left[\left(r - \frac{\sigma^2}{2}\right)T + \sigma\sqrt{T}Z\right]$$

Where $Z \sim N(0,1)$ is a standard normal draw.

**Implementation** (`simulation.py`):

```python
def _gbm_terminal(S0, r, sigma, T, z):
    return S0 * np.exp((r - 0.5*sigma^2)*T + sigma*np.sqrt(T)*z)
```

### Variance Reduction Techniques

#### 1. **Sobol Sequences** (quasi-random)

Standard pseudo-random (MRG32k3a): Each sample is independent uniform noise.

**Sobol**: Deterministic low-discrepancy sequence — covers space more uniformly than i.i.d. sampling.

**Advantage**: ~10× faster convergence to true value vs. pseudo-random.

**Implementation**: `scipy.stats.qmc.Sobol(d=1)`

```python
sampler = qmc.Sobol(d=1, seed=0)
z_sobol = sampler.random_scrambled(n_paths)  # Shape (n_paths,)
```

#### 2. **Antithetic Variates**

Generate pairs $(Z_i, -Z_i)$ simultaneously to cancel noise:

- Path 1: $S_T^{(1)} = S_0 e^{...+\sigma\sqrt{T}Z}$
- Path 2: $S_T^{(2)} = S_0 e^{...-\sigma\sqrt{T}Z}$
- Mean: $\frac{S_T^{(1)} + S_T^{(2)}}{2}$ has lower variance than single sample

**Effectiveness**: Variance reduction factor ~2.

#### 3. **Control Variates**

Use known analytical price (BS) as control:

$$C^{CV} = C^{\text{MC}} + \alpha(BS_{\text{analyzed}} - BS_{\text{MC}})$$

Where:
- $C^{\text{MC}}$ = Raw MC estimate from simulated paths
- $BS_{\text{analyzed}}$ = Analytical BS price (ground truth)
- $BS_{\text{MC}}$ = BS price computed from same simulated paths (correlation measure)
- $\alpha$ = Optimal weight (typically 1.0)

**Effectiveness**: Variance reduction factor ~10–50 depending on correlation.

#### 4. **Numba JIT Compilation**

Vectorized terminal price computation compiled to native code:

```python
@njit(cache=True)
def _gbm_terminal_vectorized(S0, r, sigma, T, z):
    n = z.shape[0]
    st = np.empty(n)
    for i in range(n):
        st[i] = S0 * np.exp((r - 0.5*sigma*sigma)*T + sigma*np.sqrt(T)*z[i])
    return st
```

**Speed**: 100–1000× faster than pure Python loops.

### Convergence & Accuracy

**Standard error** (without variance reduction):

$$\text{SE} = \frac{\sigma_{\text{est}}}{\sqrt{N}}$$

**With multiple variance reduction techniques**:

$$\text{SE}^{\text{CV,Antithetic,Sobol}} \approx \frac{\sigma_{\text{est}}}{\sqrt{100 \cdot N}}$$

**Practical accuracy**: 131k paths achieves ±0.05 vs. BS for OTM/ATM options.

---

## Implied Volatility

### Problem Statement

Given an observed market price $C_{\text{mkt}}$, solve for $\sigma^*$:

$$BS(\sigma^*) = C_{\text{mkt}}$$

### Newton-Raphson Method

Iterative root-finding using derivative (vega):

$$\sigma_{n+1} = \sigma_n - \frac{BS(\sigma_n) - C_{\text{mkt}}}{\nu(\sigma_n)}$$

**Convergence**: Quadratic (typically 3–5 iterations).

**Convergence guard**: 
- Early stop if `|BS(σ) - C_mkt| < tolerance`
- Clip σ to [1e-8, 10.0] to prevent step explosion
- Fall back to Brent if vega becomes too small

**Implementation** (`implied_vol.py`):

```python
for iteration in range(max_iter):
    test = VanillaOption(..., vol=sigma)
    diff = eng.price(test) - price_mkt
    if abs(diff) < tol:
        return sigma
    v = _vega(S, K, T, r, sigma)
    if v < 1e-8:
        break  # Fallback to Brent
    sigma_new = sigma - diff / v
    sigma = np.clip(sigma_new, 1e-8, 10.0)
```

### Brent Method (Fallback)

Bracketing root-finding via bisection + interpolation.

**Advantages**: Guaranteed convergence (linear), no derivative needed.

**Use case**: When Newton-Raphson stalls (very OTM, near zero vega).

---

## Volatility Surface

### 2D Cubic Spline Interpolation

**Data**: Grid of implied vols $\sigma(K_i, T_j)$ at discrete strike/maturity pairs.

**Method**: 
1. Fit natural cubic splines in strike direction for each maturity
2. Interpolate via spline evaluation at arbitrary strike

**Bounds enforcement**: Clamp all σ ∈ [1e-6, 2.0] to prevent:
- Numerical underflow (σ → 0)
- Numerical overflow (σ >> 1)
- Unphysical prices (σ > 200%)

**Natural boundary conditions**: 2nd derivative = 0 at edges (no artificial curvature).

### Limitations & Extensions

**Current limitations**:
- Simple cubic spline (no smile/skew dynamics)
- Static surface (no time evolution)
- Extrapolation is flat (dangerous for far OTM)

**Future extensions**:
- SABR parameterization (smile/skew modeling)
- Stochastic vol surface evolution
- Local vol (Dupire) model

---

## Delta-Gamma-Vega Value-at-Risk

### Linear Approximation (Greeks Order-1)

**P&L under market move**:

$$\Delta \text{PnL} = \Delta \cdot dS + \text{Vega} \cdot dV$$

**Limitations**: Breaks for large moves (2%+) due to gamma.

### Quadratic Approximation (Greeks Order-2)

**P&L with gamma**:

$$\Delta \text{PnL} = \Delta \cdot dS + \frac{1}{2}\Gamma \cdot (dS)^2 + \text{Vega} \cdot dV$$

**Accuracy**: Good for ≤5% moves; reasonable for ≤10% crash.

### VaR Calculation

**Distribution of market moves**:

- Spot move: $dS \sim N(0, \sigma_S^2 \cdot h)$
- Vol move: $dV \sim N(0, \sigma_V^2 \cdot h)$
- Correlation: $\text{corr}(dS, dV) = \rho = -0.75$ (typical; embedded)

**Bivariate normal sampling**:

$$Z_1 \sim N(0, 1), \quad Z_2 \sim N(0, 1) \quad (independent)$$

$$dS = \sigma_S \cdot \sqrt{h} \cdot Z_1$$

$$dV = \sigma_V \cdot \sqrt{h} \cdot (\rho Z_1 + \sqrt{1-\rho^2} Z_2)$$

**Monte Carlo loop**:

```python
n = 500_000  # Samples for 99% tail accuracy
z1 = np.random.randn(n)
z2 = np.random.randn(n)

dS = sigma_s * np.sqrt(h) * z1
dV = sigma_v * np.sqrt(h) * (rho*z1 + np.sqrt(1-rho^2)*z2)

pnl = delta*dS + 0.5*gamma*(dS**2) + vega*dV
loss_percentile = np.percentile(pnl, 1.0)  # 1st percentile (99% VaR)
var = -loss_percentile  # flip sign for loss magnitude
```

### Spot-Vol Correlation

**Why -0.75?**
- Equity indices: vol rises when spot falls (flight-to-safety)
- Typical empirical range: -0.85 to -0.65
- Our choice: -0.75 (middle ground)

**Caution**: Fixed correlation violates tail regimes (crashes show ρ → -1.0).

### Time Horizon

**Parametrized by `horizon_days`**:
- Default: 1 day
- Scaling: Variances scale by $\sqrt{h}$ where $h$ = days/year

---

## Interest Rates & Discounting

### Continuous Compounding

Used throughout: $e^{-rT}$ for discount factor.

### Dividend Adjustment

**Discrete dividends**: Subtract PV from spot price (American-style).

$$S_{\text{adj}} = S - \sum_{i: t < d_i \leq T} D_i e^{-r d_i}$$

Where $D_i$ = dividend amount at time $d_i$.

**Continuous yield** (future): Use adjusted spot $S' = S e^{-q \cdot T}$ where $q$ = yield.

---

## Numerical Stability & Edge Cases

### Safe Guards in All Engines

| Case | Guard | Rationale |
|------|-------|-----------|
| T → 0 | Return intrinsic value | Option becomes payoff | 
| σ → 0 | Return forward-discounted payoff | No randomness |
| S → 0 | Min floor at 1e-12 | Prevent log(0) |
| K → 0 | Reject (via validate) | Nonsensical |
| σ > 10 | Clip to 10 or reject | Numerical overflow risk |
| p ∉ [0,1] | Raise ValueError | CRR model breakdown |

### Cancellation Avoidance

**Formula**: $d_1 = \frac{\ln(S/K) + (r + \frac{\sigma^2}{2})T}{\sigma\sqrt{T}}$

**Bad**: Compute $\log(S) - \log(K)$ separately (loses precision if S ≈ K).

**Good**: Use `np.log(S/K)` directly (numpy broadcasts ratio first).

### Underflow Protection

- Min vol: 1e-6 (0.01% floor)
- Min time: 1e-6 years (~0.03 seconds)
- Min spot: 1e-12 (computational limit)

---

## Validation & Testing

### Unit Tests

- **Analytic`: Compare known examples (e.g., ATM 1Y call ≈ 10.45%)
- **Lattice**: Converges to Analytic within 0.1% for European options
- **MC**: Converges to Analytic within 5 bps with variance reduction
- **Greeks**: Finite difference check `(f(σ+ε) - f(σ-ε))/(2ε)` approx. ∂f/∂σ

### Sanity Checks

- Call ≥ Put spread (call - put = forward - K*e^{-rT}) 
- Deep ITM call ≈ intrinsic
- Deep OTM call ≈ 0
- Increases in S, σ, T, r increase call value
- Gamma always ≥ 0
- Vega always ≥ 0

---

## References & Further Reading

1. **Black-Scholes originals**: Black & Scholes (1973), "The Pricing of Options"
2. **Binomial trees**: Cox, Ross, Rubinstein (1979)
3. **Monte Carlo methods**: Glasserman (2004), *Monte Carlo Methods in Financial Engineering*
4. **Greeks & sensitivities**: Hull (2018), *Options, Futures & Other Derivatives*
5. **Numerical recipes**: Numerical Recipes in C++ (ch. 4, 9)
6. **Implied vol**: Gatheral (2006), *The Volatility Surface*

---
