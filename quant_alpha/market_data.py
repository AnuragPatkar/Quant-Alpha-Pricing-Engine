import threading
import logging
from collections import defaultdict
from typing import Callable, Dict, Any, List

logger = logging.getLogger(__name__)

class MarketDataStore:
    """Thread-safe market data store with pub-sub callback pattern.
    
    Attributes:
        _data: Dict mapping symbol → latest tick
        _subs: Dict mapping symbol → list of callbacks
        _lock: RLock for thread-safe access
        stats: Dict tracking callback_errors
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._data: Dict[str, Any] = {}
        self._subs: Dict[str, List[Callable[[str, Any], None]]] = defaultdict(list)
        self.stats: Dict[str, int] = {"callback_errors": 0}

    def subscribe(self, symbol: str, callback: Callable[[str, Any], None]) -> None:
        with self._lock:
            self._subs[symbol].append(callback)

    def update_tick(self, symbol: str, tick: Any) -> None:
        with self._lock:
            self._data[symbol] = tick
            callbacks = list(self._subs.get(symbol, []))
        for cb in callbacks:
            try:
                cb(symbol, tick)
            except Exception as e:
                logger.error(f"Callback failed for symbol={symbol}: {e}", exc_info=True)
                if not hasattr(self, 'stats'):
                    self.stats = {}
                self.stats['callback_errors'] = self.stats.get('callback_errors', 0) + 1

    def get(self, symbol: str) -> Any:
        with self._lock:
            return self._data.get(symbol)
