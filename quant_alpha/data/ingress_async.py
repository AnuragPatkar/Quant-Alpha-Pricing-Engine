import asyncio
import random
import time
import logging
from typing import Optional, Callable, Any
import httpx
from pydantic import BaseModel, Field, field_validator
from quant_alpha.market_data import MarketDataStore

logger = logging.getLogger(__name__)

class RetryConfig(BaseModel):
    """Exponential backoff retry configuration with jitter.
    
    Attributes:
        max_retries: Maximum number of retry attempts before giving up
        base_delay_sec: Initial delay between retries (exponential base)
        max_delay_sec: Maximum delay cap to prevent excessive waits
        jitter_sec: Random jitter added to delay (always clipped to max_delay_sec)
    """
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

class CircuitBreaker:
    """Circuit breaker for fault-tolerant async operations.
    
    Tracks consecutive failures and opens circuit (blocks requests) after
    fail_threshold is exceeded. Circuit auto-resets after reset_timeout_sec.
    
    Attributes:
        fail_threshold: Consecutive failures before opening circuit
        reset_timeout_sec: Time to wait before attempting half-open recovery
    """
    def __init__(self, fail_threshold: int = 5, reset_timeout_sec: float = 15.0):
        if fail_threshold <= 0:
            raise ValueError("fail_threshold must be > 0")
        if reset_timeout_sec <= 0:
            raise ValueError("reset_timeout_sec must be > 0")
        
        self.fail_threshold = fail_threshold
        self.reset_timeout_sec = reset_timeout_sec
        self.fail_count = 0
        self.opened_at: Optional[float] = None

    def allow(self) -> bool:
        """Check if operation is allowed.
        
        Returns False immediately if circuit is open AND timeout not elapsed.
        Returns True if closed or timeout has elapsed (half-open state).
        """
        if self.opened_at is None:
            return True
        return (time.time() - self.opened_at) >= self.reset_timeout_sec

    def on_success(self) -> None:
        """Record a successful operation. Resets fail counter and closes circuit."""
        self.fail_count = 0
        self.opened_at = None

    def on_failure(self) -> None:
        """Record a failed operation. Opens circuit if threshold exceeded."""
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            if self.opened_at is None:  # First time opening
                logger.info(f"Circuit breaker OPEN: {self.fail_count} consecutive failures")
            self.opened_at = time.time()

class NSEOptionIngress:
    """Async ingestion of NSE option data with circuit breaker resilience.
    
    Fetches option chain data from NSE API at regular intervals, applies row mapper
    to extract symbol and tick, and updates MarketDataStore subscribers.
    
    Circuit breaker prevents cascading failures when API is unavailable.
    Exponential backoff with jitter for transient failures.
    
    Args:
        url: NSE API endpoint URL for option chain data
        md_store: MarketDataStore instance for pub-sub updates
        interval_sec: Interval between fetch cycles (seconds)
        retry: RetryConfig with backoff parameters (default: exponential backoff)
        breaker: CircuitBreaker instance (default: fail_threshold=5, reset_timeout=15s)
        row_mapper: Function to extract (symbol, tick) from row dict.
                   Expected input dict format:
                   {
                       "identifier": str (option symbol, e.g., "NIFTY21APR25C18000"),
                       "ltp": float,
                       "bid": float,
                       "ask": float,
                       "oi": int,
                       "iv": float,
                       ... (other fields)
                   }
                   Default: lambda row: (row.get("identifier"), row)
    """
    
    def __init__(
        self, 
        url: str, 
        md_store: MarketDataStore, 
        interval_sec: float = 1.0,
        retry: RetryConfig | None = None, 
        breaker: CircuitBreaker | None = None,
        row_mapper: Callable[[dict], tuple[str, Any]] | None = None,
    ):
        self.url = url
        self.md_store = md_store
        self.interval_sec = interval_sec
        self.retry = retry or RetryConfig()
        self.breaker = breaker or CircuitBreaker()
        self.row_mapper = row_mapper or (lambda row: (row.get("identifier", "UNKNOWN"), row))
        self._running = False
        self.stats = {"records_processed": 0, "errors": 0, "breaker_trips": 0}

    async def _fetch_with_retry(self, client: httpx.AsyncClient) -> dict:
        for attempt in range(self.retry.max_retries + 1):
            try:
                r = await client.get(self.url)
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected JSON object payload")
                return data
            except Exception:
                if attempt >= self.retry.max_retries:
                    raise
                delay = min(
                    self.retry.max_delay_sec,
                    self.retry.base_delay_sec * (2**attempt) + random.uniform(0, self.retry.jitter_sec),
                )
                await asyncio.sleep(delay)

        raise RuntimeError("Unreachable: retry loop exited without return")
    
    def get_stats(self) -> dict:
        """Return current ingress statistics and breaker state."""
        return {
            "records_processed": self.stats["records_processed"],
            "errors": self.stats["errors"],
            "breaker_trips": self.stats["breaker_trips"],
            "breaker_is_open": self.breaker.opened_at is not None,
            "breaker_fail_count": self.breaker.fail_count,
        }

    async def run(self):
        self._running = True
        logger.info(f"NSEOptionIngress starting: url={self.url}, interval={self.interval_sec}s")
        async with httpx.AsyncClient(timeout=5.0) as client:
            while self._running:
                try:
                    if not self.breaker.allow():
                        logger.warning(f"Circuit breaker OPEN (fail_count={self.breaker.fail_count}/{self.breaker.fail_threshold}), waiting")
                        await asyncio.sleep(self.interval_sec)
                        continue
                    
                    logger.debug("Fetching option data from NSE API...")
                    payload = await self._fetch_with_retry(client)
                    records = payload.get("records", {}).get("data", [])
                    logger.debug(f"Fetched {len(records)} records")
                    
                    for row in records:
                        try:
                            sym, tick = self.row_mapper(row)
                            self.md_store.update_tick(sym, tick)
                            self.stats["records_processed"] += 1
                        except Exception as e:
                            logger.warning(f"Row mapper failed on symbol {row.get('identifier', '?')}: {e}")
                            self.stats["errors"] += 1
                    
                    self.breaker.on_success()
                    logger.debug(f"Cycle complete: {self.stats['records_processed']} total processed")
                except Exception as e:
                    self.breaker.on_failure()
                    self.stats["breaker_trips"] += 1
                    logger.error(f"Fetch cycle failed (fail_count now {self.breaker.fail_count}): {e}")
                
                await asyncio.sleep(self.interval_sec)
