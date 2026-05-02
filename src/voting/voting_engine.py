from __future__ import annotations

from typing import Any

from src.models.schemas import AGENT_NAMES
from src.utils.normalization import confidence_adjustment
from src.voting.ranking import final_grade
from src.voting.rs_priority_ranker import rs_bucket_label, sort_rs_priority
from src.voting.veto_rules import collect_veto_reasons


class VotingEngine:
    def __init__(self, weights: dict[str, float], *, market_cap_min_krw: int) -> None:
        self.weights = weights
        self.market_cap_min_krw = market_cap_min_krw

    def score_ticker(self, ticker: str, agent_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
        raw_score = 0.0
        weighted_agents = []
        for agent_name in AGENT_NAMES:
            result = agent_results.get(agent_name)
            if not result:
                continue
            weight = float(self.weights.get(agent_name, 0.0))
            adjusted = confidence_adjustment(float(result.get("confidence", 0.0)))
            contribution = float(result.get("score", 0.0)) * weight * adjusted
            raw_score += contribution
            weighted_agents.append((agent_name, contribution, result))

        rs_result = agent_results.get("rs_agent", {})
        health_result = agent_results.get("health_agent", {})
        theme_result = agent_results.get("theme_agent", {})
        trader_result = agent_results.get("trader_agent", {})
        custom_doc = agent_results.get("custom_doc_agent", {})
        veto_reasons = collect_veto_reasons(agent_results, self.market_cap_min_krw)
        veto = bool(veto_reasons)
        grade = final_grade(float(rs_result.get("rs_percentile", 0)), raw_score, veto=veto)

        top_agents = [
            name
            for name, _, result in sorted(weighted_agents, key=lambda item: item[1], reverse=True)[:3]
            if float(result.get("score", 0)) >= 70
        ]
        weak_agents = [name for name, _, result in weighted_agents if float(result.get("score", 0)) < 55]
        trade_plan = self._trade_plan(trader_result)
        risks = [risk for risk in [health_result.get("risk"), trader_result.get("risk"), custom_doc.get("risk")] if risk]
        recommendation = {
            "ticker": ticker,
            "name": rs_result.get("name") or health_result.get("name") or ticker,
            "market_cap_krw": rs_result.get("market_cap_krw") or health_result.get("market_cap_krw"),
            "rs_rank": rs_result.get("rs_rank"),
            "rs_percentile": rs_result.get("rs_percentile"),
            "rs_bucket": rs_bucket_label(float(rs_result.get("rs_percentile", 0))),
            "raw_vote_score": round(raw_score, 2),
            "final_grade": grade,
            "primary_reason": self._primary_reason(rs_result, theme_result, custom_doc),
            "top_agents": top_agents,
            "weak_agents": weak_agents,
            "themes": [theme.get("name") for theme in theme_result.get("themes", [])],
            "yyang_eum_yyang_pattern": custom_doc.get("matched_pattern", "none"),
            "trade_plan": trade_plan,
            "risks": risks,
            "evidence": self._merge_evidence(agent_results),
            "agent_scores": {name: result.get("score") for name, result in agent_results.items()},
            "veto_reasons": veto_reasons,
            "trade_type": trader_result.get("trade_type", "watch_only"),
            "pullback_type": agent_results.get("pullback_agent", {}).get("pullback_type", "none"),
            "breakout_setup": agent_results.get("breakout_agent", {}).get("setup", "forming"),
        }
        return recommendation

    def rank(self, all_agent_results: dict[str, dict[str, dict[str, Any]]]) -> tuple[list[dict], list[dict]]:
        candidates = []
        excluded = []
        for ticker, agent_results in all_agent_results.items():
            scored = self.score_ticker(ticker, agent_results)
            if scored["final_grade"] == "Excluded":
                excluded.append({"ticker": ticker, "name": scored.get("name"), "reason": "; ".join(scored.get("veto_reasons", []))})
            else:
                candidates.append(scored)
        return sort_rs_priority(candidates), excluded

    def _trade_plan(self, trader_result: dict[str, Any]) -> dict[str, Any]:
        buy_plan = trader_result.get("buy_plan", {})
        sell_plan = trader_result.get("sell_plan", {})
        return {
            "first_buy": buy_plan.get("first_buy", ""),
            "second_buy": buy_plan.get("second_buy", ""),
            "third_buy": buy_plan.get("third_buy", ""),
            "partial_sell_1": sell_plan.get("partial_sell_1", ""),
            "partial_sell_2": sell_plan.get("partial_sell_2", ""),
            "stop_loss": trader_result.get("stop_loss", ""),
            "invalidation": trader_result.get("invalidation", ""),
        }

    def _primary_reason(self, rs_result: dict[str, Any], theme_result: dict[str, Any], custom_doc: dict[str, Any]) -> str:
        pieces = [rs_result.get("reason", "")]
        if theme_result.get("primary_theme"):
            pieces.append(f"주요 테마: {theme_result['primary_theme']}")
        if custom_doc.get("matched_pattern") and custom_doc.get("matched_pattern") != "none":
            pieces.append(f"양음양 {custom_doc['matched_pattern']} 부합")
        return " / ".join(piece for piece in pieces if piece)

    def _merge_evidence(self, agent_results: dict[str, dict[str, Any]]) -> list[Any]:
        evidence = []
        for result in agent_results.values():
            for item in result.get("evidence", [])[:2]:
                evidence.append(item)
        return evidence[:12]
