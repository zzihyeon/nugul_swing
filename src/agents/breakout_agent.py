from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.indicators import closes, volume_ratio_to_average
from src.utils.normalization import clamp


class BreakoutAgent(BaseAgent):
    name = "breakout_agent"

    def evaluate(self, context: dict) -> dict:
        close_values = closes(context["ohlcv"])
        current = close_values[-1]
        previous_high = max(close_values[-21:-1]) if len(close_values) >= 21 else max(close_values[:-1])
        nearest_resistance = round(previous_high, 2)
        vol_ratio = volume_ratio_to_average(context["ohlcv"], 20)
        distance = (current / previous_high - 1.0) * 100.0 if previous_high else 0.0
        if current > previous_high and vol_ratio >= 1.4:
            setup = "ready"
            score = 86
            reason = "전고점 상단을 거래량과 함께 돌파했습니다."
        elif -2.0 <= distance <= 1.5:
            setup = "forming"
            score = 72 + min(vol_ratio, 2.0) * 5
            reason = "박스권 상단 또는 전고점에 근접해 돌파 확인 구간입니다."
        elif distance > 8:
            setup = "overextended"
            score = 48
            reason = "돌파 이후 이격이 커져 신규 추격 위험이 큽니다."
        else:
            setup = "failed"
            score = 45
            reason = "저항까지 거리가 있거나 돌파 거래량이 부족합니다."
        return self.result(
            context,
            score=clamp(score),
            confidence=0.74,
            breakout_level=nearest_resistance,
            nearest_resistance=nearest_resistance,
            volume_confirmation_needed=vol_ratio < 1.4,
            setup=setup,
            reason=reason,
            risk="저항 돌파 실패 시 윗꼬리 매물 출회 가능",
            evidence=provider_evidence(context, ["ohlcv"]),
        )
