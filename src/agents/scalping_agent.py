from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.indicators import candle_range_pct, turnover
from src.utils.normalization import clamp


class ScalpingAgent(BaseAgent):
    name = "scalping_agent"

    def evaluate(self, context: dict) -> dict:
        intraday = context.get("intraday", {})
        latest = float(intraday.get("latest_price", context["ohlcv"][-1]["close"]))
        vwap = float(intraday.get("vwap", latest))
        day_turnover = turnover(context["ohlcv"][-1])
        intraday_volume = float(intraday.get("intraday_volume", 0))
        volatility = candle_range_pct(context["ohlcv"][-1])
        score = 45
        if day_turnover >= 100_000_000_000:
            score += 24
        elif day_turnover >= 20_000_000_000:
            score += 16
        if latest >= vwap:
            score += 8
        if 2.0 <= volatility <= 9.0:
            score += 12
        if context.get("news"):
            score += 5
        score = clamp(score)
        grade = "A" if score >= 82 else "B" if score >= 70 else "C" if score >= 55 else "avoid"
        return self.result(
            context,
            score=score,
            confidence=0.7 if context.get("is_realtime") else 0.58,
            daytrade_grade=grade,
            entry_trigger=f"VWAP {round(vwap, 0):,}원 회복 후 직전 분봉 고점 돌파",
            exit_trigger="VWAP 재이탈 또는 3분봉 장대음봉",
            max_holding_time="당일 종가 전 청산",
            reason=f"거래대금 {round(day_turnover / 100_000_000, 1):,}억, 장중 거래량 {round(intraday_volume):,}주 기준입니다.",
            risk="실시간 호가/체결 강도 Provider 연결 전에는 단타 confidence 제한",
            evidence=provider_evidence(context, ["intraday", "news"]),
        )
