import math

def _safe(x, default=0.0):
    return default if x is None else x

def is_liquid(row: dict, min_qty: int = 1) -> bool:
    return int(_safe(row.get("bidQty"), 0)) >= min_qty or int(_safe(row.get("askQty"), 0)) >= min_qty

def has_valid_spread(row: dict) -> bool:
    bid = float(_safe(row.get("bidprice", row.get("bidPrice")), 0.0))
    ask = float(_safe(row.get("askPrice"), math.inf))
    return bid >= 0 and ask >= 0 and bid <= ask

def clean_option_chain(rows: list[dict]) -> list[dict]:
    return [r for r in rows if is_liquid(r) and has_valid_spread(r)]
