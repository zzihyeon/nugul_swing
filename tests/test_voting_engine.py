from datetime import date
import unittest

from stock_swing_agents.agents import SwingVotingEngine
from stock_swing_agents.models import (
    AnalysisInput,
    Decision,
    ExecutionSnapshot,
    MarketDataSnapshot,
    NewsDisclosureSnapshot,
    PostTradeSnapshot,
    RiskSnapshot,
    SupplyDemandSnapshot,
    TechnicalSnapshot,
    ThemeFollowSnapshot,
    ThemeSectorSnapshot,
    YangEumYangSnapshot,
)
from stock_swing_agents.theme_parser import (
    build_theme_follow_snapshot,
    build_theme_snapshot,
    parse_theme_text,
)


def bullish_context() -> AnalysisInput:
    return AnalysisInput(
        stock_name="세림B&G",
        market_data=MarketDataSnapshot(
            change_pct=2.1,
            volume_ratio=2.0,
            trading_value_rank=12,
            kosdaq_change_pct=0.8,
        ),
        technical=TechnicalSnapshot(
            trend="up",
            close_above_ma20=True,
            close_above_ma60=True,
            rsi=58,
            macd_histogram=0.2,
            support=9400,
            stop_loss=9300,
        ),
        supply_demand=SupplyDemandSnapshot(
            foreign_net_buy_krw=1_000_000,
            institution_net_buy_krw=2_000_000,
            program_net_buy_krw=500_000,
        ),
        news_disclosure=NewsDisclosureSnapshot(
            positive_events=["긍정 뉴스"],
            negative_events=[],
            dart_warnings=[],
        ),
        theme_sector=ThemeSectorSnapshot(
            themes=["탈 플라스틱"],
            leading_stock=True,
            sector_breadth=4,
            theme_persistence_days=3,
        ),
        theme_follow=ThemeFollowSnapshot(
            target_theme="탈 플라스틱",
            latest_event_date="2026-04-20",
            freshness_days=6,
            recent_event_count=3,
            positive_event_count=3,
            negative_event_count=0,
            latest_event="관련주 상승",
            latest_leaders=["세림B&G", "진영"],
            recurring_leaders=["세림B&G"],
            follow_candidates=["세림B&G", "진영"],
        ),
        yang_eum_yang=YangEumYangSnapshot(
            pattern="pattern1",
            first_candle_gain_pct=11.4,
            first_candle_has_upper_shadow=False,
            first_candle_volume_ratio=2.8,
            pullback_is_bearish=True,
            pullback_holds_ma5=True,
            pullback_volume_pct_of_first=45,
            short_ma_distance_pct=3.2,
            current_above_short_ma=True,
            entry_near_previous_low=True,
            entry_near_short_ma=True,
            has_theme_or_momentum=True,
            opening_volume_spike=False,
            pullback_low_broken=False,
            short_ma_broken=False,
        ),
        risk=RiskSnapshot(
            volatility_pct=4.0,
            gap_risk=False,
            trade_halt_risk=False,
            investment_warning=False,
            bad_disclosure_risk=False,
            max_position_pct=15,
            stop_loss=9300,
        ),
        execution=ExecutionSnapshot(
            price_vs_support_pct=3.0,
            price_vs_resistance_pct=9.0,
            pullback_ready=True,
            entry_mode="분할 진입",
        ),
        post_trade=PostTradeSnapshot(
            journal=["복기"],
            last_rule_breach=False,
        ),
    )


class VotingEngineTest(unittest.TestCase):
    def test_bullish_context_allows_entry(self):
        decision = SwingVotingEngine().evaluate(bullish_context())

        self.assertEqual(decision.decision, Decision.ENTRY)
        self.assertFalse(decision.risk_veto)
        self.assertEqual(decision.time_horizon, "스윙")
        self.assertIn("9300", decision.stop_loss)

    def test_risk_guard_blocks_even_when_other_agents_are_bullish(self):
        context = bullish_context()
        context.risk.trade_halt_risk = True

        decision = SwingVotingEngine().evaluate(context)

        self.assertEqual(decision.decision, Decision.FORBIDDEN)
        self.assertTrue(decision.risk_veto)
        risk_vote = next(vote for vote in decision.votes if vote.agent == "Risk Guard Agent")
        self.assertEqual(risk_vote.signal.value, "block")

    def test_theme_parser_builds_theme_snapshot_for_leader(self):
        text = """
NEW!탈 플라스틱 - 한두번 들썩일 수 있음
2026. 04. 20  중동 지정학적 리스크 재부각 등에 일부 관련주 상승(주도주 : 세림B&G, 진영)
2026. 04. 14  정책 기대감 등에 상승(주도주 : 세림B&G, 에코플라스틱)
"""
        themes = parse_theme_text(text)
        snapshot = build_theme_snapshot(themes, "세림B&G", as_of=date(2026, 4, 26))

        self.assertEqual(snapshot.themes, ["탈 플라스틱"])
        self.assertTrue(snapshot.leading_stock)
        self.assertEqual(snapshot.sector_breadth, 2)
        self.assertEqual(snapshot.theme_persistence_days, 2)

    def test_theme_follow_snapshot_tracks_recent_recurring_leaders(self):
        text = """
NEW!탈 플라스틱 - 한두번 들썩일 수 있음
2026. 04. 20  중동 지정학적 리스크 재부각 등에 일부 관련주 상승(주도주 : 세림B&G, 진영)
2026. 04. 14  정책 기대감 등에 상승(주도주 : 세림B&G, 에코플라스틱)
2026. 04. 08  이슈 소강 등에 하락
"""
        themes = parse_theme_text(text)
        snapshot = build_theme_follow_snapshot(
            themes,
            stock_name="세림B&G",
            as_of=date(2026, 4, 26),
        )

        self.assertEqual(snapshot.target_theme, "탈 플라스틱")
        self.assertEqual(snapshot.freshness_days, 6)
        self.assertEqual(snapshot.recent_event_count, 3)
        self.assertIn("세림B&G", snapshot.recurring_leaders)

    def test_theme_following_agent_votes_bullish_for_fresh_recurring_theme(self):
        decision = SwingVotingEngine().evaluate(bullish_context())
        vote = next(vote for vote in decision.votes if vote.agent == "Theme Following Agent")

        self.assertEqual(vote.signal.value, "bullish")
        self.assertGreaterEqual(vote.score, 1)

    def test_yang_eum_yang_agent_votes_bullish_for_pattern_one(self):
        decision = SwingVotingEngine().evaluate(bullish_context())
        vote = next(vote for vote in decision.votes if vote.agent == "Yang-Eum-Yang Agent")

        self.assertEqual(vote.signal.value, "bullish")
        self.assertEqual(vote.score, 2)

    def test_yang_eum_yang_agent_turns_bearish_when_pullback_breaks_ma(self):
        context = bullish_context()
        context.yang_eum_yang.pullback_volume_pct_of_first = 140
        context.yang_eum_yang.pullback_low_broken = True
        context.yang_eum_yang.short_ma_broken = True

        decision = SwingVotingEngine().evaluate(context)
        vote = next(vote for vote in decision.votes if vote.agent == "Yang-Eum-Yang Agent")

        self.assertEqual(vote.signal.value, "bearish")
        self.assertEqual(vote.score, -2)

    def test_observe_timing_downgrades_otherwise_bullish_entry(self):
        context = bullish_context()
        context.execution.entry_mode = "관망"
        context.execution.pullback_ready = False
        context.execution.price_vs_support_pct = 18
        context.execution.price_vs_resistance_pct = 10

        decision = SwingVotingEngine().evaluate(context)
        vote = next(vote for vote in decision.votes if vote.agent == "Execution Timing Agent")

        self.assertEqual(vote.signal.value, "bearish")
        self.assertEqual(decision.decision, Decision.WAIT)


if __name__ == "__main__":
    unittest.main()
