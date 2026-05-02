from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.indicators import closes, volume_ratio_to_average
from src.utils.normalization import clamp


class VolumeFlowAgent(BaseAgent):
    name = "volume_flow_agent"

    def evaluate(self, context: dict) -> dict:
        volume_ratio = volume_ratio_to_average(context["ohlcv"], 20)
        close_values = closes(context["ohlcv"])
        price_up = close_values[-1] >= close_values[-2]
        supply = context.get("supply_demand", {})
        institutional_support = supply.get("foreign") in {"net_buy", "net_buy_strong"} or supply.get("institution") in {"net_buy", "net_buy_strong"}
        if price_up and volume_ratio >= 1.4 and institutional_support:
            status = "accumulation"
            score = 84
        elif not price_up and volume_ratio >= 1.4:
            status = "distribution"
            score = 42
        elif volume_ratio <= 0.7:
            status = "dry_up"
            score = 72 if institutional_support else 60
        elif volume_ratio >= 2.8:
            status = "climax"
            score = 55
        else:
            status = "neutral"
            score = 62
        if institutional_support:
            score += 8
        key_levels = [
            {"level": context["ohlcv"][-1]["close"], "description": "latest close"},
            {"level": max(row["close"] for row in context["ohlcv"][-20:]), "description": "20d high"},
        ]
        return self.result(
            context,
            score=clamp(score),
            confidence=0.76,
            volume_status=status,
            supply_demand=supply,
            key_volume_levels=key_levels,
            reason=f"20일 평균 대비 거래량 배율은 {volume_ratio:.2f}배입니다.",
            risk="분배 신호에서는 돌파보다 매물 소화 확인 필요" if status == "distribution" else "",
            evidence=provider_evidence(context, ["ohlcv", "supply_demand"]),
        )
