from __future__ import annotations

from src.utils.indicators import candle_change_pct, candle_range_pct, closes, moving_average, upper_shadow_ratio


def detect_yyang_eum_yyang(ohlcv: list[dict], rules: dict) -> dict:
    matches = [
        _detect_pattern_1(ohlcv, rules.get("pattern_1", {})),
        _detect_pattern_2(ohlcv, rules.get("pattern_2", {})),
        _detect_pattern_3(ohlcv, rules.get("pattern_3", {})),
    ]
    matched = [match for match in matches if match["matched"]]
    if not matched:
        return {
            "matched_pattern": "none",
            "matched_rules": [],
            "violated_rules": [rule for match in matches for rule in match["violated_rules"]],
            "entry_zone": "",
            "invalid_level": None,
            "confidence": 0.55,
        }
    best = max(matched, key=lambda item: item["score"])
    return {
        "matched_pattern": best["pattern"],
        "matched_rules": best["matched_rules"],
        "violated_rules": best["violated_rules"],
        "entry_zone": best["entry_zone"],
        "invalid_level": best["invalid_level"],
        "confidence": best["confidence"],
    }


def _detect_pattern_1(ohlcv: list[dict], rule: dict) -> dict:
    if len(ohlcv) < 6:
        return _miss("pattern_1", ["not_enough_ohlcv"])
    prev = ohlcv[-2]
    current = ohlcv[-1]
    min_pct = float(rule.get("bullish_candle_min_pct", 5))
    max_pct = float(rule.get("bullish_candle_max_pct", 20))
    bullish_pct = candle_change_pct(prev)
    ma5 = moving_average(closes(ohlcv), 5)
    ma10 = moving_average(closes(ohlcv), 10)
    current_close = float(current["close"])
    short_ma_distance = min(abs(current_close - ma5), abs(current_close - ma10)) / current_close * 100.0
    bearish = float(current["close"]) < float(current["open"])
    volume_ratio = float(current["volume"]) / float(prev["volume"]) if float(prev["volume"]) else 99

    matched_rules = []
    violated_rules = []
    upper_shadow_bullish = bullish_pct > 2 and candle_range_pct(prev) >= min_pct and upper_shadow_ratio(prev) > 0.32
    if min_pct <= bullish_pct <= max_pct or upper_shadow_bullish:
        matched_rules.append("bullish_candle_5_to_20_or_upper_shadow")
    else:
        violated_rules.append("bullish_candle_range")
    if bearish:
        matched_rules.append("next_day_bearish_candle")
    else:
        violated_rules.append("next_day_is_not_bearish")
    if float(current["low"]) >= ma5:
        matched_rules.append("next_day_holds_ma5")
    else:
        violated_rules.append("breaks_ma5")
    if volume_ratio <= float(rule.get("bearish_volume_max_ratio_to_prev_bullish", 0.60)):
        matched_rules.append("bearish_volume_under_60pct")
    else:
        violated_rules.append("bearish_volume_too_high")
    if short_ma_distance <= float(rule.get("short_ma_distance_max_pct", 5)):
        matched_rules.append("short_ma_within_5pct")
    else:
        violated_rules.append("short_ma_too_far")

    matched = len(violated_rules) == 0
    return {
        "pattern": "pattern_1",
        "matched": matched,
        "score": 92 if matched else 45,
        "confidence": 0.88 if matched else 0.55,
        "matched_rules": matched_rules,
        "violated_rules": violated_rules,
        "entry_zone": f"전일 저점 {prev['low']:,}원 또는 5일선 {round(ma5, 0):,}원 부근 분할매수",
        "invalid_level": round(min(float(current["low"]), ma5), 2),
    }


def _detect_pattern_2(ohlcv: list[dict], rule: dict) -> dict:
    if len(ohlcv) < 12:
        return _miss("pattern_2", ["not_enough_ohlcv"])
    prev = ohlcv[-2]
    current = ohlcv[-1]
    ma5 = moving_average(closes(ohlcv), 5)
    ma10 = moving_average(closes(ohlcv), 10)
    avg_volume = moving_average([float(row["volume"]) for row in ohlcv[:-2]], 20)
    high_volume = float(prev["volume"]) >= avg_volume * 1.8
    long_upper_shadow = upper_shadow_ratio(prev) >= 0.42
    next_day_below_prev_close = float(current["open"]) < float(prev["close"])
    holds_short_ma = float(current["low"]) >= min(ma5, ma10) * 0.995

    matched_rules = []
    violated_rules = []
    if long_upper_shadow:
        matched_rules.append("long_upper_shadow")
    else:
        violated_rules.append("upper_shadow_not_long")
    if high_volume:
        matched_rules.append("high_volume_bullish_candle")
    else:
        violated_rules.append("volume_not_high_enough")
    if next_day_below_prev_close:
        matched_rules.append("next_day_below_prev_close")
    else:
        violated_rules.append("next_day_not_below_prev_close")
    if holds_short_ma:
        matched_rules.append("holds_ma5_ma10")
    else:
        violated_rules.append("breaks_ma5_ma10")

    matched = len(violated_rules) == 0
    return {
        "pattern": "pattern_2",
        "matched": matched,
        "score": 96 if matched else 42,
        "confidence": 0.82 if matched else 0.52,
        "matched_rules": matched_rules,
        "violated_rules": violated_rules,
        "entry_zone": f"시초가 아래 또는 5/10일선 {round(min(ma5, ma10), 0):,}원 부근에서 실시간 분할매수",
        "invalid_level": round(min(ma5, ma10), 2),
    }


def _detect_pattern_3(ohlcv: list[dict], rule: dict) -> dict:
    if len(ohlcv) < 15:
        return _miss("pattern_3", ["not_enough_ohlcv"])
    min_pct = float(rule.get("bullish_candle_min_pct", 5))
    max_pct = float(rule.get("bullish_candle_max_pct", 20))
    search = ohlcv[-10:-3]
    bullish_candidates = [
        (idx, row)
        for idx, row in enumerate(search)
        if min_pct <= candle_change_pct(row) <= max_pct
        or (candle_change_pct(row) > 2 and candle_range_pct(row) >= min_pct and upper_shadow_ratio(row) > 0.32)
    ]
    matched_rules = []
    violated_rules = []
    if bullish_candidates:
        matched_rules.append("prior_bullish_candle_5_to_20")
        candidate_idx, _ = bullish_candidates[-1]
        after = search[candidate_idx + 1 :] + ohlcv[-3:]
    else:
        violated_rules.append("no_prior_bullish_candle")
        after = ohlcv[-7:]
    volumes = [float(row["volume"]) for row in after]
    volume_contraction = len(volumes) >= 3 and all(left >= right * 0.92 for left, right in zip(volumes, volumes[1:]))
    closes_after = [float(row["close"]) for row in after]
    sideways = closes_after and (max(closes_after) / min(closes_after) - 1.0) <= 0.08
    ma5 = moving_average(closes(ohlcv), 5)
    ma10 = moving_average(closes(ohlcv), 10)
    above_short_ma = all(float(row["close"]) >= min(ma5, ma10) * 0.985 for row in after[-5:])

    if volume_contraction:
        matched_rules.append("volume_contraction")
    else:
        violated_rules.append("volume_not_contracting")
    if sideways:
        matched_rules.append("sideways_after_bullish_candle")
    else:
        violated_rules.append("not_sideways")
    if above_short_ma:
        matched_rules.append("sideways_above_short_ma")
    else:
        violated_rules.append("breaks_short_ma")

    matched = len(violated_rules) == 0
    return {
        "pattern": "pattern_3",
        "matched": matched,
        "score": 88 if matched else 44,
        "confidence": 0.84 if matched else 0.54,
        "matched_rules": matched_rules,
        "violated_rules": violated_rules,
        "entry_zone": f"5일선 {round(ma5, 0):,}원 / 10일선 {round(ma10, 0):,}원 부근 다분할",
        "invalid_level": round(min(float(row["low"]) for row in after[-3:]), 2) if after else None,
    }


def _miss(pattern: str, violated_rules: list[str]) -> dict:
    return {
        "pattern": pattern,
        "matched": False,
        "score": 0,
        "confidence": 0.3,
        "matched_rules": [],
        "violated_rules": violated_rules,
        "entry_zone": "",
        "invalid_level": None,
    }
