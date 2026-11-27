"""查詢參數的共用處理。"""
import re

MAX_LIMIT = 100


def limit_param(value, default: int, maximum: int = MAX_LIMIT) -> int:
    """列表的 limit：不是整數就用預設值，限制在 1 到 maximum 之間。
    原本沒有上限，limit=100000 會一次查出整個集合，推薦快取也會被不同的 limit 值塞爆（資安低-9）。"""
    m = re.match(r"^\s*-?\d+", str(value)) if value is not None else None
    return min(max(int(m.group()) if m else default, 1), maximum)
