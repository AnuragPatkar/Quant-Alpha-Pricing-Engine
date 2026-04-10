# Data Pipeline

Complete guide to market data ingestion, processing, and storage in Quant Alpha Pricing Engine.

---

## Overview

The data pipeline handles **async HTTP ingestion**, **circuit breaker fault tolerance**, **thread-safe updates**, and **observer notifications**.

```
API Source (HTTP)
    ↓
AsyncIngress (retry + circuit breaker)
    ↓
MarketDataStore (pub-sub)
    ↓
Subscribers (Observers)
    ├─→ Risk calculator
    ├─→ Vol surface updater
    └─→ Pricing engine
```

---

## Architecture

### 1. **Market Data Store** (`market_data.py`)

Thread-safe pub-sub pattern for real-time data distribution.

#### Core Operations

```python
class MarketDataStore:
    def __init__(self):
        self._lock = threading.RLock()      # Recursive lock for thread safety
        self._data: Dict[str, Any] = {}      # Symbol → latest tick
        self._subs: Dict[str, List[Callable]] = defaultdict(list)  # Symbol → observers
        self.stats: Dict[str, int] = {}      # Error tracking
    
    def subscribe(self, symbol: str, callback: Callable[[str, Any], None]) -> None:
        """Register observer callback for symbol updates."""
        with self._lock:
            self._subs[symbol].append(callback)
    
    def update_tick(self, symbol: str, tick: Any) -> None:
        """Atomically update tick and notify all subscribers."""
        with self._lock:
            self._data[symbol] = tick
            callbacks = list(self._subs.get(symbol, []))  # Snapshot to avoid lock during callback
        
        # Execute callbacks outside lock to prevent deadlocks
        for cb in callbacks:
            try:
                cb(symbol, tick)
            except Exception as e:
                logger.error(f"Callback failed for {symbol}: {e}")
                self.stats['callback_errors'] = self.stats.get('callback_errors', 0) + 1
    
    def get(self, symbol: str) -> Any:
        """Fetch latest tick."""
        with self._lock:
            return self._data.get(symbol)
```

#### Usage Example

```python
store = MarketDataStore()

def on_aapl_update(symbol, tick):
    print(f"AAPL: Price={tick['price']}, Vol={tick['iv']}")

store.subscribe("AAPL", on_aapl_update)

# Simulate market update
store.update_tick("AAPL", {"price": 150.25, "iv": 0.18, "bid": 150.20, "ask": 150.30})
# Prints: "AAPL: Price=150.25, Vol=0.18"
```

#### Full Example: Risk Monitoring

```python
from quant_alpha.risk.limits import evaluate_limits

store = MarketDataStore()
portfolio = Portfolio(name="LIVE_BOOK")

def on_market_update(symbol, tick):
    """Recalculate risk on every tick."""
    price = tick['price']
    vol = tick['iv']
    
    # Update portfolio spot & vol
    for pos in portfolio.positions:
        if pos.instrument.spot != price:
            pos.instrument.spot = price
        if pos.instrument.vol != vol:
            pos.instrument.vol = vol
    
    # Evaluate risk
    report = evaluate_limits(
        portfolio=portfolio,
        limits=RiskLimits(...),
        spot=price,
        spot_daily_vol=0.012,
        iv_daily_vol_abs=0.01,
        stress_scenarios=[...]
    )
    
    if report['breaches']:
        alert(f"RISK BREACH: {report['breaches']}")
    
    print(f"Delta: {report['greeks']['delta']:.0f}")

store.subscribe("SPY", on_market_update)
```

#### Thread Safety Guarantees

- **Atomicity**: `update_tick()` locks while copying subscriber list; callbacks execute unlocked (no deadlock)
- **Ordering**: Updates to same symbol serialize (RLock prevents concurrent writers)
- **Stats**: `self.stats['callback_errors']` is incremented safely (int assignment is atomic in CPython GIL)

---

### 2. **Async Ingestion with Retry** (`ingress_async.py`)

Fault-tolerant HTTP data fetching with exponential backoff and circuit breaker.

#### RetryConfig

```python
class RetryConfig(BaseModel):
    """Exponential backoff configuration."""
    max_retries: int = Field(default=5, ge=0, le=50)
    base_delay_sec: float = Field(default=0.25, gt=0, le=10)
    max_delay_sec: float = Field(default=3.0, gt=0, le=60)
    jitter_sec: float = Field(default=0.1, ge=0, le=5)
    
    @field_validator('max_delay_sec')
    @classmethod
    def max_ge_base(cls, v: float, info) -> float:
        if info.data.get('base_delay_sec') and v < info.data['base_delay_sec']:
            raise ValueError("max_delay_sec must be >= base_delay_sec")
        return v
```

**Example**:
```yaml
# config/app_config.yaml
retry:
  max_retries: 5           # 5 attempts before giving up
  base_delay_sec: 0.25     # Start with 250ms wait
  max_delay_sec: 3.0       # Cap at 3 seconds
  jitter_sec: 0.1          # Randomize by ±100ms
```

#### Exponential Backoff Calculation

```
Attempt 1: delay = 0.25s
Attempt 2: delay = 0.25s × 2 = 0.5s
Attempt 3: delay = 0.25s × 4 = 1.0s
Attempt 4: delay = min(0.25s × 8, 3.0s) = 2.0s
Attempt 5: delay = min(0.25s × 16, 3.0s) = 3.0s + jitter
```

Each attempt adds random ±jitter to prevent synchronized retries (thundering herd).

#### Circuit Breaker

```python
class CircuitBreaker:
    """Fault-tolerance pattern: fail-fast when service is unavailable."""
    
    def __init__(self, fail_threshold: int = 5, reset_timeout_sec: float = 15.0):
        self.fail_threshold = fail_threshold          # Fails before opening
        self.reset_timeout_sec = reset_timeout_sec    # Time before retry
        self._fail_count = 0
        self._open_time = None
        self._state = "CLOSED"  # CLOSED → OPEN → HALF_OPEN → CLOSED
    
    def acquire(self) -> bool:
        """Check if circuit allows request."""
        now = time.time()
        
        if self._state == "OPEN":
            # In open state; check if timeout elapsed
            if now - self._open_time > self.reset_timeout_sec:
                self._state = "HALF_OPEN"
                logger.info("Circuit: OPEN → HALF_OPEN (recovery attempt)")
                return True  # Allow one test request
            else:
                return False  # Still open; block request
        
        return True  # CLOSED or HALF_OPEN: allow request
    
    def record_success(self):
        """Mark successful request; reset circuit if in HALF_OPEN."""
        if self._state == "HALF_OPEN":
            self._fail_count = 0
            self._state = "CLOSED"
            logger.info("Circuit: HALF_OPEN → CLOSED (recovered)")
        elif self._state == "CLOSED":
            self._fail_count = 0
    
    def record_failure(self):
        """Mark failed request; may open circuit."""
        self._fail_count += 1
        if self._fail_count >= self.fail_threshold and self._state != "OPEN":
            self._state = "OPEN"
            self._open_time = time.time()
            logger.warning(f"Circuit OPEN: {self._fail_count} consecutive failures")
```

**State transitions**:

```
CLOSED (happy path)
  ↓ (fail_threshold failures)
OPEN (reject requests)
  ↓ (reset_timeout elapses)
HALF_OPEN (test one request)
  ├─→ success → CLOSED
  └─→ failure → OPEN
```

#### Async Fetch Implementation

```python
async def fetch_with_retry(
    url: str,
    retry_config: RetryConfig,
    breaker: CircuitBreaker,
    timeout_sec: float = 5.0
) -> dict:
    """Fetch with automatic retry and circuit breaker."""
    
    if not breaker.acquire():
        raise RuntimeError(f"Circuit OPEN: {url} unavailable")
    
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        for attempt in range(1, retry_config.max_retries + 1):
            try:
                response = await client.get(url)
                response.raise_for_status()
                
                breaker.record_success()
                return response.json()
            
            except httpx.HTTPError as e:
                logger.warning(f"Attempt {attempt}/{retry_config.max_retries} failed: {e}")
                breaker.record_failure()
                
                if attempt == retry_config.max_retries:
                    raise
                
                # Exponential backoff with jitter
                delay = min(
                    retry_config.base_delay_sec * (2 ** (attempt - 1)),
                    retry_config.max_delay_sec
                )
                jitter = random.uniform(-retry_config.jitter_sec, retry_config.jitter_sec)
                total_delay = delay + jitter
                
                logger.info(f"Retrying in {total_delay:.2f}s...")
                await asyncio.sleep(total_delay)
```

---

### 3. **Option Chain Data Cleaning** (`nse_cleaning.py`)

Standardizes NSE/Indian market option chain data for downstream processing.

#### Input Format (NSE JSON)

```json
{
  "records": {
    "data": [
      {
        "strikePrice": 100.0,
        "expiryDate": "31MAR2024",
        "CE": {
          "bidPrice": 5.50,
          "askPrice": 5.75,
          "lastPrice": 5.60,
          "bidQty": 100,
          "askQty": 200,
          "openInterest": 2500
        },
        "PE": {
          "bidPrice": 4.80,
          "askPrice": 5.10,
          "lastPrice": 4.90,
          ...
        }
      }
    ]
  }
}
```

#### Cleaning Steps

```python
def clean_option_chain(raw_data: dict, symbol: str) -> pd.DataFrame:
    """
    Clean NSE option chain JSON → standardized DataFrame.
    
    Cleaning steps:
    1. Extract data array
    2. Parse expiry date → days to expiry
    3. Validate bid-ask spreads (flag illiquid)
    4. Remove stale quotes (zero OI)
    5. Standardize column names
    6. Type conversion
    """
    rows = []
    for record in raw_data['records']['data']:
        strike = record['strikePrice']
        expiry_str = record['expiryDate']  # e.g., "31MAR2024"
        
        # Parse expiry
        expiry_date = pd.to_datetime(expiry_str, format='%d%b%Y')
        dte = (expiry_date - pd.Timestamp.now()).days
        
        for option_type, key in [('CALL', 'CE'), ('PUT', 'PE')]:
            opt = record.get(key, {})
            
            bid = opt.get('bidPrice', np.nan)
            ask = opt.get('askPrice', np.nan)
            mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else np.nan
            
            # Quality checks
            spread = ask - bid if (bid > 0 and ask > 0) else np.nan
            is_illiquid = spread > mid * 0.10 if spread > 0 else True  # >10% spread
            
            oi = opt.get('openInterest', 0)
            is_stale = oi == 0
            
            if is_stale or is_illiquid:
                continue  # Skip
            
            rows.append({
                'symbol': symbol,
                'strike': strike,
                'option_type': option_type,
                'expiry_date': expiry_date,
                'dte': dte,
                'bid': bid,
                'ask': ask,
                'mid': mid,
                'spread': spread,
                'oi': oi,
                'volume': opt.get('totalTradedVolume', 0),
                'iv': np.nan  # Caller should populate via implied_vol()
            })
    
    return pd.DataFrame(rows)
```

#### Output Format

```
   symbol  strike option_type expiry_date  dte   bid   ask   mid  spread   oi volume
0   NIFTY    19000        CALL  2024-03-31   45  150.5 151.2 150.85 0.7    150000 25000
1   NIFTY    19000        PUT   2024-03-31   45  100.2 101.0 100.6  0.8    200000 30000
...
```

---

### 4. **Data Change Observers** (`observers.py`)

Interface for pluggable reactions to market data updates.

```python
from abc import ABC, abstractmethod
from quant_alpha.market_data import MarketDataStore

class Observer(ABC):
    """Base class for market data update handlers."""
    
    @abstractmethod
    def on_market_update(self, symbol: str, tick: dict) -> None:
        """React to symbol update."""
        pass

class RiskMonitor(Observer):
    """Recalculates portfolio risk on every market update."""
    
    def __init__(self, portfolio, limits):
        self.portfolio = portfolio
        self.limits = limits
    
    def on_market_update(self, symbol, tick):
        # Update spot/vol in portfolio instruments
        # Recalculate risk
        # Alert if breaches
        pass

class VolSurfaceUpdater(Observer):
    """Updates vol surface on every tick."""
    
    def __init__(self, store):
        self.store = store
    
    def on_market_update(self, symbol, tick):
        # Add tick to vol surface grid
        # Re-interpolate
        pass

# Usage
store = MarketDataStore()
monitor = RiskMonitor(portfolio, limits)
updater = VolSurfaceUpdater(store)

store.subscribe("NIFTY", monitor.on_market_update)
store.subscribe("NIFTY", updater.on_market_update)
```

---

## Data Flow Examples

### Example 1: Live Option Pricing

```python
import asyncio
from quant_alpha.data.ingress_async import fetch_with_retry, RetryConfig, CircuitBreaker
from quant_alpha.data.nse_cleaning import clean_option_chain
from quant_alpha.pricing.implied_vol import implied_vol
from quant_alpha.pricing.vol_surface import VolSurface

async def live_pricing_loop():
    store = MarketDataStore()
    config = RetryConfig()
    breaker = CircuitBreaker()
    
    while True:
        # Fetch option chain every 5 seconds
        try:
            raw_data = await fetch_with_retry(
                "https://api.example.com/nifty/option_chain",
                config, breaker
            )
            
            # Clean data
            df = clean_option_chain(raw_data, symbol="NIFTY")
            
            # Extract IVs
            for _, row in df.iterrows():
                opt = VanillaOption(
                    spot=row['spot'],
                    strike=row['strike'],
                    maturity=row['dte'] / 365.0,
                    rate=0.06,
                    vol=0.20,  # Initial guess
                    option_type=OptionType[row['option_type']]
                )
                iv = implied_vol(row['mid'], opt)
                
                # Update store (triggers observers)
                store.update_tick(f"NIFTY_{row['strike']}_{row['option_type']}", {
                    'price': row['mid'],
                    'iv': iv,
                    'bid': row['bid'],
                    'ask': row['ask'],
                    'oi': row['oi']
                })
        
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        
        await asyncio.sleep(5.0)

# Run
asyncio.run(live_pricing_loop())
```

### Example 2: Vol Surface Construction

```python
import pandas as pd
import numpy as np
from quant_alpha.pricing.vol_surface import VolSurface
from quant_alpha.data.nse_cleaning import clean_option_chain

def build_vol_surface(df: pd.DataFrame) -> VolSurface:
    """Build 2D vol surface from cleaned option chain."""
    
    # Pivot to (DTE, Strike) grid
    surface_data = df.pivot_table(
        index='dte',
        columns='strike',
        values='iv',
        aggfunc='first'
    ).fillna(method='bfill').fillna(method='ffill')
    
    # Create VolSurface
    return VolSurface(
        strikes=np.array(surface_data.columns),
        maturities=np.array(surface_data.index) / 365.0,
        vols=surface_data.values
    )

# Usage
df = clean_option_chain(raw_data, "NIFTY")
surface = build_vol_surface(df)

# Interpolate vol at arbitrary (strike, maturity)
iv_105_0p5y = surface.iv(105, 0.5)
```

---

## Deployment & Monitoring

### Typical Production Setup

```
┌─────────────────────────────────────────────┐
│   NSE API (market data source)              │
└────────────────┬────────────────────────────┘
                 │ fetch_with_retry()
                 │ (circuit breaker + backoff)
                 ↓
         ┌───────────────────┐
         │ Data Cleaning     │
         │ (NSE → canonical) │
         └────────┬──────────┘
                  │
         ┌────────▼──────────────────┐
         │ MarketDataStore pub-sub    │
         └────────┬──────────────────┘
                  │
         ┌────────┴─────────────┬─────────────┐
         ↓                      ↓             ↓
    Risk Monitor      Vol Surface Updater   Pricing Engine
    (recalc Greeks)   (build surface)       (repricing)
```

### Health Checks

```python
def health_check(store: MarketDataStore) -> dict:
    """Monitor data pipeline health."""
    return {
        "data_age_sec": time.time() - store._last_update,
        "symbols_active": len(store._data),
        "callback_errors": store.stats.get('callback_errors', 0),
        "status": "HEALTHY" if data_age_sec < 300 else "STALE"
    }
```

### Logging Configuration

Structured logging to track data pipeline issues:

```python
import logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Sample logs
logger.info(f"Fetching {url}")
logger.warning(f"Retry attempt {n}: {error}")
logger.error(f"Circuit OPEN: {url}")
logger.debug(f"Callback executed: {symbol}")
```

---

## Limitations & Future Work

### Current Limitations

1. **In-memory only**: No persistent storage; data lost on restart
2. **Single API source**: No fallback/redundancy
3. **No rate limiting**: Could hammer API if not careful
4. **NSE-specific cleaning**: Would need adaptations for other exchanges
5. **Static vol surface**: No dynamic smile/skew evolution

### Future Enhancements

- [ ] Persistent cache (Redis, SQLite)
- [ ] Multi-source data aggregation (fallback APIs)
- [ ] Rate limiting & quotas
- [ ] Multiple exchange support (US equity, futures)
- [ ] Stochastic vol surface evolution
- [ ] Real-time data quality monitoring dashboard

---
