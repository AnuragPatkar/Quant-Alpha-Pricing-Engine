from typing import TypedDict, Any, Dict

class Tick(TypedDict, total=False):
    symbol: str
    ltp: float
    bid: float
    ask: float
    ts: str

JSON = Dict[str, Any]
