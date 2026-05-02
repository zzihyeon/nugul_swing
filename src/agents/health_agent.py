from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.indicators import turnover
from src.utils.normalization import clamp


class HealthAgent(BaseAgent):
    name = "health_agent"

    def evaluate(self, context: dict) -> dict:
        risk_config = self.configs.get("risk_rules", {})
        market_cap_min = int(self.configs.get("market_cap_filter", {}).get("market_cap_min_krw", 300_000_000_000))
        market_cap = context.get("market_cap_krw")
        flags = set(context.get("status_flags", []))
        disclosures = context.get("disclosures", [])
        financials = context.get("financials", {})
        last_turnover = turnover(context["ohlcv"][-1])
        veto_reasons = []

        if market_cap is None:
            veto_reasons.append("market_cap_unknown")
        elif risk_config.get("veto_market_cap_below_min", True) and market_cap < market_cap_min:
            veto_reasons.append("market_cap_below_min")
        flag_map = {
            "trading_halt": "거래정지",
            "administrative_issue": "관리종목",
            "delisting_risk": "상장폐지 위험",
            "audit_opinion_issue": "감사의견 문제",
            "investment_warning": "투자경고",
        }
        for flag, label in flag_map.items():
            if flag in flags:
                veto_reasons.append(label)
        if financials.get("audit_opinion") in {"adverse", "disclaimer", "qualified"}:
            veto_reasons.append("감사의견 문제")
        if any(item.get("severity") == "high" for item in disclosures):
            veto_reasons.append("최근 심각한 악재 공시")
        if last_turnover < float(risk_config.get("extreme_low_turnover_krw", 100_000_000)):
            veto_reasons.append("거래대금 극단적 부족")

        score = 82
        debt_ratio = float(financials.get("debt_ratio", 100))
        operating_margin = float(financials.get("operating_margin", 0))
        if debt_ratio > 150:
            score -= 20
        if operating_margin < 0:
            score -= 18
        if last_turnover < float(risk_config.get("low_turnover_krw", 500_000_000)):
            score -= 12
        if disclosures:
            score -= 14
        if flags:
            score -= 25
        score = clamp(score)

        financial_health = "strong" if score >= 82 else "normal" if score >= 62 else "weak" if score >= 40 else "danger"
        liquidity_status = "good" if last_turnover >= 5_000_000_000 else "normal" if last_turnover >= 500_000_000 else "poor"
        disclosure_risk = "high" if any(item.get("severity") == "high" for item in disclosures) else "medium" if disclosures else "low"
        veto = bool(veto_reasons)
        return self.result(
            context,
            score=score,
            confidence=0.9,
            financial_health=financial_health,
            liquidity_status=liquidity_status,
            market_cap_krw=market_cap,
            disclosure_risk=disclosure_risk,
            veto=veto,
            veto_reason=", ".join(veto_reasons),
            reason="건전성 veto 사유가 없습니다." if not veto else " / ".join(veto_reasons),
            risk=", ".join(veto_reasons),
            evidence=provider_evidence(context, ["market_cap", "financials", "disclosures"]),
        )
