from __future__ import annotations

from typing import Any


class RuleExtractor:
    def extract_yyang_eum_yyang_rules(self, document_text: str, config_rules: dict[str, Any]) -> dict[str, Any]:
        rules = {
            "strategy_doc": "yyang_eum_yyang",
            "patterns": {
                "pattern_1": dict(config_rules.get("pattern_1", {})),
                "pattern_2": dict(config_rules.get("pattern_2", {})),
                "pattern_3": dict(config_rules.get("pattern_3", {})),
            },
            "risk_rules": dict(config_rules.get("risk_rules", {})),
            "uncertain_rules": [],
        }
        normalized = document_text.lower()
        required_terms = ["pattern 1", "pattern 2", "pattern 3"]
        if not all(term in normalized for term in required_terms):
            rules["uncertain_rules"].append("document_text_incomplete_or_not_pdf_extractable")
        if "60%" in document_text:
            rules["patterns"]["pattern_1"]["bearish_volume_max_ratio_to_prev_bullish"] = 0.60
        return rules
