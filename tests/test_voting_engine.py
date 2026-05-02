import unittest

from src.voting.voting_engine import VotingEngine


WEIGHTS = {
    "rs_agent": 0.20,
    "theme_agent": 0.12,
    "health_agent": 0.15,
    "trader_agent": 0.13,
    "breakout_agent": 0.08,
    "pullback_agent": 0.10,
    "scalping_agent": 0.05,
    "volume_flow_agent": 0.12,
    "custom_doc_agent": 0.05,
}


def agent_result(agent, ticker, score, confidence=0.9, **extra):
    result = {
        "agent": agent,
        "ticker": ticker,
        "score": score,
        "confidence": confidence,
        "reason": "",
        "risk": "",
        "evidence": [],
    }
    result.update(extra)
    return result


def full_results(ticker, rs_percentile, vote_score, *, veto=False):
    return {
        "rs_agent": agent_result(
            "rs_agent",
            ticker,
            vote_score,
            rs_rank={"A": 1, "B": 2, "C": 3}.get(ticker, 9),
            rs_percentile=rs_percentile,
            market_cap_krw=1_000_000_000_000,
            name=ticker,
        ),
        "theme_agent": agent_result("theme_agent", ticker, vote_score, themes=[]),
        "health_agent": agent_result(
            "health_agent",
            ticker,
            80 if not veto else 10,
            market_cap_krw=1_000_000_000_000,
            veto=veto,
            veto_reason="test_veto" if veto else "",
        ),
        "trader_agent": agent_result("trader_agent", ticker, vote_score, stop_loss="100 이탈", buy_plan={}, sell_plan={}),
        "breakout_agent": agent_result("breakout_agent", ticker, vote_score),
        "pullback_agent": agent_result("pullback_agent", ticker, vote_score),
        "scalping_agent": agent_result("scalping_agent", ticker, vote_score),
        "volume_flow_agent": agent_result("volume_flow_agent", ticker, vote_score),
        "custom_doc_agent": agent_result("custom_doc_agent", ticker, vote_score, matched_pattern="none"),
    }


class VotingEngineTest(unittest.TestCase):
    def test_vote_score_reorders_inside_same_rs_bucket(self):
        engine = VotingEngine(WEIGHTS, market_cap_min_krw=300_000_000_000)
        recommendations, _ = engine.rank(
            {
                "A": full_results("A", 95, 65),
                "B": full_results("B", 92, 90),
                "C": full_results("C", 75, 98),
            }
        )
        self.assertEqual([item["ticker"] for item in recommendations], ["B", "A", "C"])

    def test_lower_rs_bucket_cannot_easily_overtake_higher_bucket(self):
        engine = VotingEngine(WEIGHTS, market_cap_min_krw=300_000_000_000)
        recommendations, _ = engine.rank(
            {
                "A": full_results("A", 95, 62),
                "C": full_results("C", 75, 99),
            }
        )
        self.assertEqual(recommendations[0]["ticker"], "A")

    def test_health_veto_removes_final_recommendation(self):
        engine = VotingEngine(WEIGHTS, market_cap_min_krw=300_000_000_000)
        recommendations, excluded = engine.rank({"A": full_results("A", 95, 90, veto=True)})
        self.assertEqual(recommendations, [])
        self.assertEqual(excluded[0]["ticker"], "A")
        self.assertIn("test_veto", excluded[0]["reason"])


if __name__ == "__main__":
    unittest.main()
