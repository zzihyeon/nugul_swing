from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


AGENT_NAMES = [
    "rs_agent",
    "theme_agent",
    "health_agent",
    "trader_agent",
    "breakout_agent",
    "pullback_agent",
    "scalping_agent",
    "volume_flow_agent",
    "custom_doc_agent",
]


@dataclass
class ProviderEnvelope:
    source: str
    fetched_at_kst: str
    is_realtime: bool
    is_stale: bool
    data: dict[str, Any]
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    agent: str
    ticker: str
    score: float
    confidence: float
    reason: str
    risk: str = ""
    evidence: list[dict[str, Any] | str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base = {
            "agent": self.agent,
            "ticker": self.ticker,
            "score": round(float(self.score), 2),
            "confidence": round(float(self.confidence), 3),
            "reason": self.reason,
            "risk": self.risk,
            "evidence": self.evidence,
        }
        base.update(self.payload)
        return base


@dataclass
class PipelineResult:
    date: str
    requested_at_kst: str
    data_fetched_at_kst: str
    realtime_refresh: bool
    market_context: str
    filters: dict[str, Any]
    recommendations: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    report: str = ""
    agent_results: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)

    def to_dict(self, include_report: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_report:
            data.pop("report", None)
        return data
