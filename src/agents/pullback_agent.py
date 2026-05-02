from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.strategy_docs.yyang_eum_yyang_parser import detect_yyang_eum_yyang
from src.utils.indicators import closes, moving_average
from src.utils.normalization import clamp


class PullbackAgent(BaseAgent):
    name = "pullback_agent"

    def evaluate(self, context: dict) -> dict:
        close_values = closes(context["ohlcv"])
        current = close_values[-1]
        ma5 = moving_average(close_values, 5)
        ma10 = moving_average(close_values, 10)
        ma20 = moving_average(close_values, 20)
        last_volume = float(context["ohlcv"][-1]["volume"])
        prev_volume = float(context["ohlcv"][-2]["volume"])
        volume_dry_up = last_volume <= prev_volume * 0.65
        yyang = detect_yyang_eum_yyang(context["ohlcv"], self.configs.get("yyang_eum_yyang_rules", {}))
        distances = {"ma5": abs(current / ma5 - 1.0), "ma10": abs(current / ma10 - 1.0), "ma20": abs(current / ma20 - 1.0)}
        nearest_ma = min(distances, key=distances.get)
        support_levels = [round(ma5, 2), round(ma10, 2), round(ma20, 2)]

        if yyang["matched_pattern"] != "none":
            pullback_type = "yyang_eum_yyang"
            score = 84 if volume_dry_up else 76
            reason = f"양음양 {yyang['matched_pattern']} 조건과 단기 지지 후보가 겹칩니다."
        elif distances[nearest_ma] <= 0.025 and volume_dry_up:
            pullback_type = nearest_ma
            score = 76
            reason = f"{nearest_ma} 부근 눌림과 거래량 감소가 확인됩니다."
        elif current >= ma20:
            pullback_type = "box_support"
            score = 62
            reason = "20일선 위에서 버티지만 거래량 감소 신호는 제한적입니다."
        else:
            pullback_type = "none"
            score = 42
            reason = "주요 단기 지지선 이탈 또는 눌림 구조가 약합니다."
        invalid_level = yyang["invalid_level"] or round(min(ma10, ma20) * 0.985, 2)
        return self.result(
            context,
            score=clamp(score),
            confidence=max(0.62, yyang.get("confidence", 0.62)),
            pullback_type=pullback_type,
            support_levels=support_levels,
            invalid_level=invalid_level,
            volume_dry_up=volume_dry_up,
            yyang_eum_yyang_candidate=yyang["matched_pattern"] != "none",
            reason=reason,
            risk="음봉 거래량 재증가 시 눌림 실패 가능",
            evidence=provider_evidence(context, ["ohlcv"]),
        )
