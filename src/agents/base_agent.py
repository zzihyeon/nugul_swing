from __future__ import annotations

from pathlib import Path
from typing import Any

from src.models.schemas import AgentResult
from src.utils.config import load_config_dir
from src.utils.normalization import clamp


class BaseAgent:
    name = "base_agent"

    def __init__(self, config_dir: str | Path | None = None, configs: dict[str, dict[str, Any]] | None = None) -> None:
        self.config_dir = Path(config_dir) if config_dir else None
        self.configs = configs or (load_config_dir(self.config_dir) if self.config_dir else {})

    def evaluate(self, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def result(
        self,
        context: dict[str, Any],
        *,
        score: float,
        confidence: float,
        reason: str,
        risk: str = "",
        evidence: list[Any] | None = None,
        **payload: Any,
    ) -> dict[str, Any]:
        adjusted_confidence = min(float(confidence), float(context.get("data_confidence", 1.0)))
        return AgentResult(
            agent=self.name,
            ticker=context["ticker"],
            score=clamp(float(score)),
            confidence=max(0.0, min(1.0, adjusted_confidence)),
            reason=reason,
            risk=risk,
            evidence=evidence or [],
            payload=payload,
        ).to_dict()


def provider_evidence(context: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    evidence = []
    envelopes = context.get("provider_envelopes", {})
    for key in keys:
        envelope = envelopes.get(key)
        if envelope:
            evidence.append(
                {
                    "type": key,
                    "source": envelope.get("source"),
                    "fetched_at_kst": envelope.get("fetched_at_kst"),
                    "is_stale": envelope.get("is_stale"),
                }
            )
    return evidence
