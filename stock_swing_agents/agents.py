"""Agent implementations and the final voting engine."""

from __future__ import annotations

from typing import Protocol

from .models import (
    AgentVote,
    AnalysisInput,
    Decision,
    Signal,
    TradeDecision,
    collect_sources,
)


class SwingAgent(Protocol):
    name: str

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        ...


class MarketDataAgent:
    name = "Market Data Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.market_data
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if data.change_pct is not None:
            if data.change_pct > 0:
                raw_score += 1
                evidence.append(f"현재 등락률이 +{data.change_pct:.2f}%입니다.")
            elif data.change_pct <= -3:
                raw_score -= 1
                risks.append(f"현재 등락률이 {data.change_pct:.2f}%로 약합니다.")

        if data.volume_ratio is not None:
            if data.volume_ratio >= 1.5:
                raw_score += 1
                evidence.append(f"거래량이 평균 대비 {data.volume_ratio:.1f}배입니다.")
            elif data.volume_ratio < 0.7:
                raw_score -= 1
                risks.append("거래량이 평균보다 부족합니다.")

        if data.trading_value_rank is not None:
            if data.trading_value_rank <= 30:
                raw_score += 1
                evidence.append(f"거래대금 순위가 {data.trading_value_rank}위권입니다.")
            elif data.trading_value_rank > 150:
                risks.append("거래대금 순위가 낮아 체결 안정성이 떨어질 수 있습니다.")

        market_tailwind = _positive(data.kospi_change_pct) or _positive(
            data.kosdaq_change_pct
        )
        market_headwind = _weak(data.kospi_change_pct) and _weak(data.kosdaq_change_pct)
        if market_tailwind:
            raw_score += 1
            evidence.append("시장 지수가 우호적입니다.")
        if market_headwind:
            raw_score -= 1
            risks.append("KOSPI/KOSDAQ 흐름이 동시에 약합니다.")
        if data.usdkrw_change_pct is not None and data.usdkrw_change_pct >= 0.7:
            raw_score -= 1
            risks.append("원/달러 환율 상승이 수급 부담이 될 수 있습니다.")

        for source in data.sources[:2]:
            label = source.name
            if source.delay:
                label += f"({source.delay})"
            if source.retrieved_at:
                label += f" 조회 {source.retrieved_at}"
            evidence.append(label)

        return _vote(self.name, raw_score, _confidence(data, 9), evidence, risks)


class TechnicalSignalAgent:
    name = "Technical Signal Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.technical
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if data.trend:
            trend = data.trend.lower()
            if trend in {"up", "uptrend", "상승"}:
                raw_score += 1
                evidence.append("추세가 상승 방향입니다.")
            elif trend in {"down", "downtrend", "하락"}:
                raw_score -= 1
                risks.append("추세가 하락 방향입니다.")

        if data.close_above_ma20 is True:
            raw_score += 1
            evidence.append("종가가 20일선 위에 있습니다.")
        elif data.close_above_ma20 is False:
            raw_score -= 1
            risks.append("종가가 20일선 아래에 있습니다.")

        if data.close_above_ma60 is True:
            raw_score += 1
            evidence.append("종가가 60일선 위에 있습니다.")
        elif data.close_above_ma60 is False:
            raw_score -= 1
            risks.append("종가가 60일선 아래에 있습니다.")

        if data.rsi is not None:
            if 45 <= data.rsi <= 70:
                raw_score += 1
                evidence.append(f"RSI {data.rsi:.1f}로 추세 지속 구간입니다.")
            elif data.rsi > 75:
                raw_score -= 1
                risks.append(f"RSI {data.rsi:.1f}로 과열 부담이 있습니다.")
            elif data.rsi < 35:
                raw_score -= 1
                risks.append(f"RSI {data.rsi:.1f}로 모멘텀이 약합니다.")

        if data.macd_histogram is not None:
            if data.macd_histogram > 0:
                raw_score += 1
                evidence.append("MACD 히스토그램이 양수입니다.")
            elif data.macd_histogram < 0:
                raw_score -= 1
                risks.append("MACD 히스토그램이 음수입니다.")

        if data.bollinger_position in {"upper_breakout", "상단돌파"}:
            evidence.append("볼린저밴드 상단 돌파가 확인됩니다.")
        elif data.bollinger_position in {"lower_breakdown", "하단이탈"}:
            raw_score -= 1
            risks.append("볼린저밴드 하단 이탈이 확인됩니다.")

        return _vote(self.name, raw_score, _confidence(data, 8), evidence, risks)


class SupplyDemandAgent:
    name = "Supply/Demand Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.supply_demand
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        smart_money = (data.foreign_net_buy_krw or 0) + (
            data.institution_net_buy_krw or 0
        )
        if smart_money > 0:
            raw_score += 1
            evidence.append("외국인+기관 합산 순매수가 양수입니다.")
        elif smart_money < 0:
            raw_score -= 1
            risks.append("외국인+기관 합산 순매도가 발생했습니다.")

        if data.foreign_net_buy_krw is not None and data.foreign_net_buy_krw > 0:
            raw_score += 1
            evidence.append("외국인 순매수가 유입되었습니다.")
        if data.institution_net_buy_krw is not None and data.institution_net_buy_krw > 0:
            raw_score += 1
            evidence.append("기관 순매수가 유입되었습니다.")
        if data.program_net_buy_krw is not None:
            if data.program_net_buy_krw > 0:
                raw_score += 1
                evidence.append("프로그램 순매수가 유입되었습니다.")
            elif data.program_net_buy_krw < 0:
                raw_score -= 1
                risks.append("프로그램 순매도가 부담입니다.")

        if (
            data.individual_net_buy_krw is not None
            and data.individual_net_buy_krw > 0
            and smart_money < 0
        ):
            risks.append("개인 매수 우위와 외국인/기관 매도 조합입니다.")

        if (data.consecutive_foreign_buy_days or 0) >= 3:
            evidence.append("외국인 연속 순매수 흐름입니다.")
        if (data.consecutive_institution_buy_days or 0) >= 3:
            evidence.append("기관 연속 순매수 흐름입니다.")

        return _vote(self.name, raw_score, _confidence(data, 6), evidence, risks)


class NewsDisclosureAgent:
    name = "News/Disclosure Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.news_disclosure
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if data.positive_events:
            raw_score += min(2, len(data.positive_events))
            evidence.extend(data.positive_events[:2])
        if data.high_impact_events:
            evidence.append(f"확인된 주요 이벤트: {data.high_impact_events[0]}")
        if data.negative_events:
            raw_score -= min(2, len(data.negative_events))
            risks.extend(data.negative_events[:2])
        if data.dart_warnings:
            raw_score -= 2
            risks.extend(data.dart_warnings[:2])

        return _vote(self.name, raw_score, _confidence(data, 4), evidence, risks)


class ThemeSectorAgent:
    name = "Theme/Sector Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.theme_sector
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if data.themes:
            raw_score += 1
            evidence.append("연결 테마: " + ", ".join(data.themes[:3]))
        else:
            risks.append("확인된 주도 테마 연결이 없습니다.")

        if data.leading_stock is True:
            raw_score += 1
            evidence.append("테마 내 주도주로 분류됩니다.")
        elif data.leading_stock is False:
            risks.append("테마 내 후발주 가능성이 있습니다.")

        if data.sector_breadth is not None:
            if data.sector_breadth >= 4:
                raw_score += 1
                evidence.append(f"관련주 확산 폭이 {data.sector_breadth}개 이상입니다.")
            elif data.sector_breadth <= 1:
                risks.append("테마 확산 폭이 좁습니다.")

        if data.theme_persistence_days is not None:
            if data.theme_persistence_days >= 2:
                raw_score += 1
                evidence.append(f"테마가 {data.theme_persistence_days}일 이상 반복됐습니다.")
            elif data.theme_persistence_days == 0:
                raw_score -= 1
                risks.append("최근 반복성이 확인되지 않습니다.")

        return _vote(self.name, raw_score, _confidence(data, 4), evidence, risks)


class ThemeFollowingAgent:
    name = "Theme Following Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.theme_follow
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if not data.target_theme:
            return AgentVote(
                agent=self.name,
                signal=Signal.NEUTRAL,
                score=0,
                confidence=35,
                evidence=("테마 추종 데이터 없음",),
                risk=("테마 파일에서 추종할 테마를 확정하지 못했습니다.",),
            )

        evidence.append(f"추종 대상 테마: {data.target_theme}")

        if data.freshness_days is not None:
            if data.freshness_days <= 7:
                raw_score += 2
                evidence.append(f"최신 이벤트가 {data.freshness_days}일 전입니다.")
            elif data.freshness_days <= 30:
                raw_score += 1
                evidence.append(f"최근 {data.freshness_days}일 내 이벤트가 있습니다.")
            elif data.freshness_days > 60:
                raw_score -= 1
                risks.append("최근성 약화: 최신 이벤트가 60일을 넘었습니다.")

        if data.recent_event_count is not None:
            if data.recent_event_count >= 3:
                raw_score += 1
                evidence.append(f"최근 이벤트가 {data.recent_event_count}회 반복됐습니다.")
            elif data.recent_event_count <= 1:
                risks.append("최근 반복성이 약합니다.")

        positive = data.positive_event_count or 0
        negative = data.negative_event_count or 0
        if positive > negative:
            raw_score += 1
            evidence.append(f"상승성 이벤트가 하락성 이벤트보다 많습니다({positive}:{negative}).")
        elif negative > positive and negative > 0:
            raw_score -= 1
            risks.append(f"하락성 이벤트가 더 많습니다({positive}:{negative}).")

        if data.recurring_leaders:
            raw_score += 1
            evidence.append("반복 주도주: " + ", ".join(data.recurring_leaders[:3]))
        elif data.latest_leaders:
            evidence.append("최신 주도주: " + ", ".join(data.latest_leaders[:3]))

        if _stock_in_names(context.stock_name, data.follow_candidates):
            raw_score += 1
            evidence.append(f"{context.stock_name}이 추종 후보군에 포함됩니다.")
        elif data.follow_candidates:
            risks.append(f"{context.stock_name}은 추종 후보군 선두가 아닙니다.")

        if data.latest_event:
            latest = data.latest_event
            if any(word in latest for word in ("하락", "약세", "급락")):
                raw_score -= 1
                risks.append("최신 테마 이벤트가 부정적 문구를 포함합니다.")
            evidence.append("최신 이벤트: " + latest)

        return _vote(self.name, raw_score, _confidence(data, 10), evidence, risks)


class YangEumYangAgent:
    name = "Yang-Eum-Yang Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.yang_eum_yang
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if not _has_snapshot_data(data):
            return AgentVote(
                agent=self.name,
                signal=Signal.NEUTRAL,
                score=0,
                confidence=35,
                evidence=("양음양 데이터 없음",),
                risk=("장대양봉/음봉 거래량/단기 이평선 조건을 확인할 입력이 없습니다.",),
            )

        pattern = (data.pattern or "pattern1").lower()
        evidence.append(f"양음양 기준: {pattern}")

        if _first_candle_acceptable(data):
            raw_score += 1
            evidence.append("첫 양봉이 5~20% 구간 또는 윗꼬리 장대양봉 조건입니다.")
        elif data.first_candle_gain_pct is not None:
            raw_score -= 1
            risks.append("첫 양봉이 5~20% 기준에서 벗어났습니다.")

        if data.first_candle_volume_ratio is not None:
            if data.first_candle_volume_ratio >= 1.5:
                raw_score += 1
                evidence.append("첫 양봉에 평균 대비 거래량이 동반됐습니다.")
            elif data.first_candle_volume_ratio < 1:
                risks.append("첫 양봉 거래량이 충분히 크지 않습니다.")

        if pattern in {"pattern1", "p1", "1"}:
            raw_score += _score_pattern_one(data, evidence, risks)
        elif pattern in {"pattern2", "p2", "2"}:
            raw_score += _score_pattern_two(data, evidence, risks)
        elif pattern in {"pattern3", "p3", "3"}:
            raw_score += _score_pattern_three(data, evidence, risks)
        else:
            risks.append("알 수 없는 양음양 패턴명입니다.")

        if data.has_theme_or_momentum is True:
            raw_score += 1
            evidence.append("장대양봉에 테마/호재 모멘텀이 동반됐습니다.")
        elif data.has_theme_or_momentum is False:
            risks.append("장대양봉을 설명할 테마/호재 모멘텀이 약합니다.")

        if data.entry_near_previous_low or data.entry_near_short_ma:
            raw_score += 1
            evidence.append("분할 매수 위치가 전일 저점 또는 단기 이평선 부근입니다.")

        if data.opening_volume_spike:
            raw_score -= 1
            risks.append("장대양봉 다음날 시초 거래량이 과다해 접근 보류 조건입니다.")
        if data.pullback_low_broken:
            raw_score -= 2
            risks.append("거래량 감소 음봉의 저가를 이탈했습니다.")
        if data.short_ma_broken:
            raw_score -= 2
            risks.append("5일선/10일선 등 단기 이평선을 이탈했습니다.")
        if data.pullback_low_broken and data.short_ma_broken:
            return AgentVote(
                agent=self.name,
                signal=Signal.BEARISH,
                score=-2,
                confidence=_confidence(data, 17),
                evidence=tuple(evidence or ["양음양 조건 무효화"]),
                risk=tuple(risks),
            )

        return _vote(self.name, raw_score, _confidence(data, 17), evidence, risks)


class RiskGuardAgent:
    name = "Risk Guard Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.risk
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        hard_blocks = []
        if data.trade_halt_risk:
            hard_blocks.append("거래정지 가능성")
        if data.investment_warning:
            hard_blocks.append("투자주의/경고 리스크")
        if data.bad_disclosure_risk:
            hard_blocks.append("악성 공시 리스크")
        if hard_blocks:
            return AgentVote(
                agent=self.name,
                signal=Signal.BLOCK,
                score=-2,
                confidence=95,
                evidence=("거래 금지 조건 발생: " + ", ".join(hard_blocks),),
                risk=("Risk Guard 거부권 발동",),
            )

        if data.volatility_pct is not None:
            if data.volatility_pct <= 5:
                raw_score += 1
                evidence.append(f"변동성 {data.volatility_pct:.1f}%로 관리 가능 범위입니다.")
            elif data.volatility_pct >= 10:
                raw_score -= 1
                risks.append(f"변동성 {data.volatility_pct:.1f}%로 손절 폭 관리가 어렵습니다.")

        if data.gap_risk:
            raw_score -= 1
            risks.append("갭하락 리스크가 있습니다.")
        if data.stop_loss is not None:
            raw_score += 1
            evidence.append(f"손절 기준 {data.stop_loss:g}가 지정되어 있습니다.")
        else:
            risks.append("명시적 손절 기준이 없습니다.")
        if data.max_position_pct is not None and data.max_position_pct <= 20:
            evidence.append(f"포지션 한도 {data.max_position_pct:g}%로 제한됩니다.")

        return _vote(self.name, raw_score, _confidence(data, 7), evidence, risks)


class ExecutionTimingAgent:
    name = "Execution Timing Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.execution
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if data.pullback_ready:
            raw_score += 1
            evidence.append("눌림 후 재상승 대기 조건이 확인됩니다.")
        if data.breakout_confirmed:
            raw_score += 1
            evidence.append("돌파 확인 조건이 있습니다.")
        if data.entry_mode:
            evidence.append(f"실행 모드: {data.entry_mode}")
            if data.entry_mode == "관망":
                raw_score -= 1
                risks.append("실행 타이밍이 관망으로 분류됐습니다.")

        if data.price_vs_support_pct is not None:
            if 0 <= data.price_vs_support_pct <= 5:
                raw_score += 1
                evidence.append("지지선과의 거리가 스윙 진입에 과도하지 않습니다.")
            elif data.price_vs_support_pct > 12:
                raw_score -= 1
                risks.append("지지선과의 거리가 멀어 손절 폭이 커질 수 있습니다.")

        if data.price_vs_resistance_pct is not None:
            if data.price_vs_resistance_pct <= 3:
                raw_score -= 1
                risks.append("저항선까지 남은 여유가 3% 이하입니다.")
            elif data.price_vs_resistance_pct >= 8:
                raw_score += 1
                evidence.append("저항선까지 기대 여유가 남아 있습니다.")

        return _vote(self.name, raw_score, _confidence(data, 5), evidence, risks)


class PostTradeReviewAgent:
    name = "Post-Trade Review Agent"

    def evaluate(self, context: AnalysisInput) -> AgentVote:
        data = context.post_trade
        raw_score = 0
        evidence: list[str] = []
        risks: list[str] = []

        if data.last_rule_breach:
            raw_score -= 1
            risks.append("최근 매매에서 원칙 위반이 기록되었습니다.")
        elif data.last_rule_breach is False:
            raw_score += 1
            evidence.append("최근 매매 원칙 위반 기록이 없습니다.")

        if data.journal:
            evidence.append("매매 복기 기록이 존재합니다.")
        else:
            risks.append("매매 복기 기록이 없습니다.")

        return _vote(self.name, raw_score, _confidence(data, 2), evidence, risks)


class SwingVotingEngine:
    def __init__(self, agents: tuple[SwingAgent, ...] | None = None) -> None:
        self.agents = agents or (
            MarketDataAgent(),
            TechnicalSignalAgent(),
            SupplyDemandAgent(),
            NewsDisclosureAgent(),
            ThemeSectorAgent(),
            ThemeFollowingAgent(),
            YangEumYangAgent(),
            RiskGuardAgent(),
            ExecutionTimingAgent(),
            PostTradeReviewAgent(),
        )
        self.weights = {
            "Market Data Agent": 1.0,
            "Technical Signal Agent": 1.2,
            "Supply/Demand Agent": 1.2,
            "News/Disclosure Agent": 1.1,
            "Theme/Sector Agent": 0.8,
            "Theme Following Agent": 1.0,
            "Yang-Eum-Yang Agent": 1.1,
            "Risk Guard Agent": 1.5,
            "Execution Timing Agent": 1.0,
            "Post-Trade Review Agent": 0.5,
        }

    def evaluate(self, context: AnalysisInput) -> TradeDecision:
        votes = tuple(agent.evaluate(context) for agent in self.agents)
        risk_vote = next(v for v in votes if v.agent == "Risk Guard Agent")
        risk_veto = risk_vote.signal is Signal.BLOCK
        score_total = self._weighted_score(votes)

        if risk_veto:
            decision = Decision.FORBIDDEN
        else:
            decision = self._decision_from_score(score_total, votes)

        return TradeDecision(
            decision=decision,
            reason=_top_reasons(votes),
            counter_reason=_top_counter_reasons(votes),
            stop_loss=_stop_loss_text(context),
            time_horizon=context.time_horizon,
            score_total=round(score_total, 2),
            risk_veto=risk_veto,
            votes=votes,
            sources=collect_sources(context),
        )

    def _weighted_score(self, votes: tuple[AgentVote, ...]) -> float:
        total = 0.0
        for vote in votes:
            confidence_factor = 0.5 + (vote.confidence / 200)
            total += vote.score * self.weights.get(vote.agent, 1.0) * confidence_factor
        return total

    def _decision_from_score(
        self, score_total: float, votes: tuple[AgentVote, ...]
    ) -> Decision:
        risk_vote = next(v for v in votes if v.agent == "Risk Guard Agent")
        execution_vote = next(v for v in votes if v.agent == "Execution Timing Agent")

        if score_total >= 5:
            decision = Decision.ENTRY
        elif score_total >= 1.5:
            decision = Decision.WAIT
        elif score_total >= -1:
            decision = Decision.OBSERVE
        else:
            decision = Decision.FORBIDDEN

        if decision is Decision.ENTRY and risk_vote.score < 0:
            return Decision.WAIT
        if decision is Decision.ENTRY and execution_vote.score < 0:
            return Decision.WAIT
        return decision


def _vote(
    agent: str,
    raw_score: int,
    confidence: int,
    evidence: list[str],
    risks: list[str],
) -> AgentVote:
    score = max(-2, min(2, raw_score))
    if score > 0:
        signal = Signal.BULLISH
    elif score < 0:
        signal = Signal.BEARISH
    else:
        signal = Signal.NEUTRAL
    return AgentVote(agent, signal, score, confidence, tuple(evidence), tuple(risks))


def _confidence(snapshot: object, field_count: int) -> int:
    present = 0
    for value in vars(snapshot).values():
        if value not in (None, [], (), {}):
            present += 1
    return max(35, min(90, round((present / field_count) * 100)))


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _weak(value: float | None) -> bool:
    return value is not None and value <= -1


def _has_snapshot_data(snapshot: object) -> bool:
    return any(value not in (None, [], (), {}) for value in vars(snapshot).values())


def _first_candle_acceptable(data) -> bool:
    gain_ok = (
        data.first_candle_gain_pct is not None
        and 5 <= data.first_candle_gain_pct <= 20
    )
    return gain_ok or data.first_candle_has_upper_shadow is True


def _score_pattern_one(data, evidence: list[str], risks: list[str]) -> int:
    score = 0
    if data.pullback_is_bearish is True:
        score += 1
        evidence.append("다음날 음봉 눌림이 확인됩니다.")
    elif data.pullback_is_bearish is False:
        risks.append("두 번째 캔들이 음봉 눌림이 아닙니다.")

    if data.pullback_holds_ma5 is True:
        score += 1
        evidence.append("음봉이 5일선을 이탈하지 않았습니다.")
    elif data.pullback_holds_ma5 is False:
        score -= 1
        risks.append("음봉이 5일선을 이탈했습니다.")

    if data.pullback_volume_pct_of_first is not None:
        if data.pullback_volume_pct_of_first <= 60:
            score += 2
            evidence.append("음봉 거래량이 첫 양봉의 60% 이하로 감소했습니다.")
        elif data.pullback_volume_pct_of_first <= 100:
            score -= 1
            risks.append("음봉 거래량 감소가 60% 기준보다 약합니다.")
        else:
            score -= 2
            risks.append("음봉 거래량이 첫 양봉보다 많아 진성 매도 가능성이 있습니다.")

    if data.short_ma_distance_pct is not None:
        if 0 <= data.short_ma_distance_pct <= 5:
            score += 1
            evidence.append("단기 이평선이 현재가 기준 -5%권 안에 있습니다.")
        elif data.short_ma_distance_pct > 5:
            risks.append("단기 이평선과의 거리가 멀어 분할 접근 리스크가 큽니다.")

    return score


def _score_pattern_two(data, evidence: list[str], risks: list[str]) -> int:
    score = 0
    if data.first_candle_has_upper_shadow is True:
        score += 1
        evidence.append("윗꼬리가 긴 대량거래 양봉 조건입니다.")
    else:
        risks.append("Pattern 2의 핵심인 긴 윗꼬리 양봉이 약합니다.")

    if data.current_above_short_ma is True:
        score += 1
        evidence.append("양봉 마감 또는 현재가가 단기 이평선 위입니다.")
    elif data.current_above_short_ma is False:
        score -= 1
        risks.append("단기 이평선 위 마감 조건이 약합니다.")

    if data.entry_near_short_ma is True:
        score += 1
        evidence.append("시초가 아래 단기 이평선 부근 분할 접근 조건입니다.")

    return score


def _score_pattern_three(data, evidence: list[str], risks: list[str]) -> int:
    score = 0
    if (data.consecutive_volume_decline_days or 0) >= 2:
        score += 1
        evidence.append("거래량이 연속 감소하는 눌림/횡보 구간입니다.")
    else:
        risks.append("거래량 연속 감소 확인이 부족합니다.")

    if data.sideways_above_short_ma is True:
        score += 1
        evidence.append("단기 이평선 위에서 횡보가 유지됩니다.")
    elif data.sideways_above_short_ma is False:
        score -= 1
        risks.append("단기 이평선 위 횡보 조건이 깨졌습니다.")

    if data.entry_near_short_ma is True:
        score += 1
        evidence.append("5일선/10일선 부근 다분할 접근 조건입니다.")

    return score


def _stock_in_names(stock_name: str, names: list[str]) -> bool:
    stock = "".join(stock_name.split()).lower()
    return any(stock and stock in "".join(name.split()).lower() for name in names)


def _top_reasons(votes: tuple[AgentVote, ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for vote in sorted(votes, key=lambda item: (item.score, item.confidence), reverse=True):
        if vote.score <= 0:
            continue
        for item in vote.evidence:
            if item not in reasons and item != "충분한 데이터 없음":
                reasons.append(item)
            if len(reasons) == 3:
                return tuple(reasons)
    return tuple(reasons or ["명확한 찬성 근거가 부족합니다."])


def _top_counter_reasons(votes: tuple[AgentVote, ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for vote in sorted(votes, key=lambda item: (item.signal == Signal.BLOCK, -item.score), reverse=True):
        if vote.score >= 0 and vote.signal is not Signal.BLOCK:
            continue
        for item in vote.risk:
            if item not in reasons and item != "충분한 데이터 없음":
                reasons.append(item)
            if len(reasons) == 2:
                return tuple(reasons)
    for vote in votes:
        for item in vote.risk:
            if item not in reasons and item != "충분한 데이터 없음":
                reasons.append(item)
            if len(reasons) == 2:
                return tuple(reasons)
    return tuple(reasons or ["주요 반대 근거가 확인되지 않았습니다."])


def _stop_loss_text(context: AnalysisInput) -> str:
    if context.risk.stop_loss is not None:
        return f"{context.risk.stop_loss:g} 이탈 시"
    if context.technical.stop_loss is not None:
        return f"{context.technical.stop_loss:g} 이탈 시"
    if context.technical.support is not None:
        return f"주요 지지선 {context.technical.support:g} 이탈 시"
    return "입력 데이터 부족: 기술적 지지선 또는 손절가 필요"
