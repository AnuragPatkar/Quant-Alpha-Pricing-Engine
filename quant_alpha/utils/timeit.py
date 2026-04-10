import time
import numpy as np
from collections import deque
from typing import Deque, Any, Callable


class TailLatencyMonitor:
    def __init__(self, maxlen: int = 50_000):
        self.samples_ms: Deque[float] = deque(maxlen=maxlen)

    def record_ms(self, value_ms: float) -> None:
        self.samples_ms.append(float(value_ms))

    def wrap(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        t0 = time.perf_counter_ns()
        out = fn(*args, **kwargs)
        t1 = time.perf_counter_ns()
        self.record_ms((t1 - t0) / 1e6)
        return out

    def summary(self) -> dict:
        if not self.samples_ms:
            return {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None, "max_ms": None}
        x = np.array(self.samples_ms, dtype=float)
        return {
            "count": int(x.size),
            "p50_ms": float(np.percentile(x, 50)),
            "p95_ms": float(np.percentile(x, 95)),
            "p99_ms": float(np.percentile(x, 99)),
            "max_ms": float(np.max(x)),
        }
