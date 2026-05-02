from __future__ import annotations


def collect_veto_reasons(agent_results: dict[str, dict], market_cap_min_krw: int) -> list[str]:
    reasons: list[str] = []
    rs_result = agent_results.get("rs_agent", {})
    health_result = agent_results.get("health_agent", {})
    volume_result = agent_results.get("volume_flow_agent", {})
    market_cap = health_result.get("market_cap_krw") or rs_result.get("market_cap_krw")
    if market_cap is None:
        reasons.append("market_cap_unknown")
    elif market_cap < market_cap_min_krw:
        reasons.append("market_cap_below_min")
    if health_result.get("veto"):
        reasons.append(health_result.get("veto_reason") or "health_agent_veto")
    if float(rs_result.get("score", 0)) < 40 and float(volume_result.get("score", 0)) < 40:
        reasons.append("rs_and_volume_both_below_40")
    trader_result = agent_results.get("trader_agent", {})
    if not trader_result.get("stop_loss"):
        reasons.append("missing_stop_loss")
    return [reason for reason in reasons if reason]
