from __future__ import annotations

from statistics import mean
from typing import Iterable


def closes(ohlcv: list[dict]) -> list[float]:
    return [float(row["close"]) for row in ohlcv]


def volumes(ohlcv: list[dict]) -> list[float]:
    return [float(row["volume"]) for row in ohlcv]


def moving_average(values: Iterable[float], window: int) -> float:
    values = list(values)
    if not values:
        return 0.0
    if len(values) < window:
        return mean(values)
    return mean(values[-window:])


def return_pct(values: list[float], window: int) -> float:
    if len(values) <= window:
        return 0.0
    base = values[-window - 1]
    if base == 0:
        return 0.0
    return (values[-1] / base - 1.0) * 100.0


def candle_change_pct(row: dict) -> float:
    open_price = float(row["open"])
    if open_price == 0:
        return 0.0
    return (float(row["close"]) / open_price - 1.0) * 100.0


def candle_range_pct(row: dict) -> float:
    low = float(row["low"])
    if low == 0:
        return 0.0
    return (float(row["high"]) / low - 1.0) * 100.0


def upper_shadow_ratio(row: dict) -> float:
    high = float(row["high"])
    low = float(row["low"])
    if high <= low:
        return 0.0
    body_top = max(float(row["open"]), float(row["close"]))
    return (high - body_top) / (high - low)


def turnover(row: dict) -> float:
    return float(row["close"]) * float(row["volume"])


def average_volume(ohlcv: list[dict], window: int = 20) -> float:
    return moving_average(volumes(ohlcv), window)


def volume_ratio_to_average(ohlcv: list[dict], window: int = 20) -> float:
    if not ohlcv:
        return 0.0
    avg = average_volume(ohlcv[:-1] or ohlcv, window)
    if avg == 0:
        return 0.0
    return float(ohlcv[-1]["volume"]) / avg


def vwap_from_intraday(rows: list[dict]) -> float:
    amount = sum(float(row["price"]) * float(row["volume"]) for row in rows)
    volume = sum(float(row["volume"]) for row in rows)
    if volume == 0:
        return 0.0
    return amount / volume
