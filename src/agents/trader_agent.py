from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.indicators import closes, moving_average, volume_ratio_to_average
from src.utils.normalization import clamp


class TraderAgent(BaseAgent):
    name = "trader_agent"

    def evaluate(self, context: dict) -> dict:
        close_values = closes(context["ohlcv"])
        last = close_values[-1]
        ma5 = moving_average(close_values, 5)
        ma10 = moving_average(close_values, 10)
        ma20 = moving_average(close_values, 20)
        vol_ratio = volume_ratio_to_average(context["ohlcv"], 20)
        distance_ma5 = (last / ma5 - 1.0) * 100.0 if ma5 else 0.0
        distance_ma20 = (last / ma20 - 1.0) * 100.0 if ma20 else 0.0
        high20 = max(close_values[-20:])
        stop = round(min(ma10, ma20) * 0.985, 2)
        upside = max(high20 * 1.08 - last, last * 0.04)
        downside = max(last - stop, last * 0.01)
        risk_reward = round(upside / downside, 2) if downside else 0.0

        if distance_ma5 > 8:
            trade_type = "watch_only"
            score = 58
            reason = "5일선 이격이 커서 추격보다 눌림 확인이 유리합니다."
        elif -2.5 <= distance_ma5 <= 3.5 and vol_ratio <= 1.4:
            trade_type = "swing"
            score = 80
            reason = "단기 이평선 부근에서 과열이 크지 않아 분할 접근이 가능합니다."
        elif last >= high20 * 0.985 and vol_ratio >= 1.2:
            trade_type = "day_trade"
            score = 76
            reason = "전고점 돌파 구간에 가까워 거래량 확인형 접근이 필요합니다."
        else:
            trade_type = "watch_only"
            score = 64
            reason = "자리는 나쁘지 않지만 명확한 진입 트리거가 더 필요합니다."

        if risk_reward < 1.4:
            score -= 8
        score = clamp(score)
        buy_plan = {
            "first_buy": f"{round(min(last, ma5), 0):,}원 부근 1차",
            "second_buy": f"{round(ma10, 0):,}원 부근 2차",
            "third_buy": f"{round(ma20, 0):,}원 부근 3차 또는 지지 확인 후",
        }
        sell_plan = {
            "partial_sell_1": f"{round(last * 1.05, 0):,}원 1차 분할매도",
            "partial_sell_2": f"{round(last * 1.09, 0):,}원 2차 분할매도",
            "final_target": f"{round(last * 1.14, 0):,}원 또는 거래량 climax",
        }
        return self.result(
            context,
            score=score,
            confidence=0.78,
            trade_type=trade_type,
            buy_plan=buy_plan,
            sell_plan=sell_plan,
            stop_loss=f"{stop:,}원 이탈",
            invalidation=f"종가 기준 20일선 {round(ma20, 0):,}원 이탈 또는 대량 음봉",
            risk_reward=risk_reward,
            reason=reason,
            risk="손절선까지 거리가 커지면 비중 축소" if risk_reward < 1.8 else "",
            evidence=provider_evidence(context, ["ohlcv", "intraday"]),
        )
