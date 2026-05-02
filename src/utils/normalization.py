from __future__ import annotations


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def confidence_adjustment(confidence: float) -> float:
    if confidence >= 0.8:
        return 1.0
    if confidence >= 0.6:
        return 0.85
    if confidence >= 0.4:
        return 0.65
    return 0.4


def pct(part: float, whole: float) -> float:
    if whole == 0:
        return 0.0
    return (part / whole) * 100.0


def won_to_eok(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    return f"{round(value / 100_000_000):,}억"
