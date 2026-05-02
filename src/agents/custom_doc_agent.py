from __future__ import annotations

from pathlib import Path

from src.agents.base_agent import BaseAgent, provider_evidence
from src.strategy_docs.document_parser import DocumentParser
from src.strategy_docs.rule_extractor import RuleExtractor
from src.strategy_docs.yyang_eum_yyang_parser import detect_yyang_eum_yyang


class CustomDocumentAgent(BaseAgent):
    name = "custom_doc_agent"

    def __init__(self, config_dir=None, configs=None, document_path: str | Path | None = None) -> None:
        super().__init__(config_dir=config_dir, configs=configs)
        if document_path is None and self.config_dir:
            document_path = self.config_dir.parent / "data" / "custom_docs" / "yyang_eum_yyang.pdf"
        self.document_path = Path(document_path) if document_path else None
        self.document_parser = DocumentParser()
        self.rule_extractor = RuleExtractor()
        self._structured_rules = None

    def structured_rules(self) -> dict:
        if self._structured_rules is None:
            parsed = self.document_parser.parse(self.document_path) if self.document_path else {"text": "", "ok": False}
            self._structured_rules = self.rule_extractor.extract_yyang_eum_yyang_rules(
                parsed.get("text", ""),
                self.configs.get("yyang_eum_yyang_rules", {}),
            )
            self._structured_rules["document_ok"] = parsed.get("ok", False)
            self._structured_rules["document_error"] = parsed.get("error", "")
        return self._structured_rules

    def evaluate(self, context: dict) -> dict:
        structured = self.structured_rules()
        detection = detect_yyang_eum_yyang(context["ohlcv"], self.configs.get("yyang_eum_yyang_rules", {}))
        matched_pattern = detection["matched_pattern"]
        if matched_pattern == "none":
            score = 42
            reason = "양음양 문서 규칙에 명확히 부합하지 않습니다."
            risk = "문서 기반 전략 가점 없음"
        else:
            score = {"pattern_1": 88, "pattern_2": 76, "pattern_3": 84}.get(matched_pattern, 70)
            reason = f"문서 기반 양음양 {matched_pattern} 규칙과 가격/거래량 구조가 부합합니다."
            risk = "거래량 재증가 음봉 또는 단기 이평선 이탈 시 제외"
        if structured.get("uncertain_rules"):
            score -= 8
        return self.result(
            context,
            score=score,
            confidence=min(0.86, detection.get("confidence", 0.6)) if structured.get("document_ok") else 0.48,
            strategy_doc="yyang_eum_yyang",
            matched_pattern=matched_pattern,
            matched_rules=detection["matched_rules"],
            violated_rules=detection["violated_rules"],
            entry_zone_from_doc=detection["entry_zone"],
            invalid_level_from_doc=detection["invalid_level"],
            conflicts=structured.get("uncertain_rules", []),
            reason=reason,
            risk=risk,
            evidence=provider_evidence(context, ["ohlcv"]) + [{"type": "strategy_doc", "path": str(self.document_path)}],
        )
