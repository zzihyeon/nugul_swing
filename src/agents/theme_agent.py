from __future__ import annotations

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.normalization import clamp


class ThemeAgent(BaseAgent):
    name = "theme_agent"

    def evaluate(self, context: dict) -> dict:
        raw_themes = context.get("themes", [])
        themes = []
        stage_bonus = {"early": 4, "expanding": 8, "crowded": -2, "exhausted": -10, "forming": 2}
        for theme in raw_themes[:3]:
            stage = theme.get("stage", "unknown")
            normalized_stage = stage if stage in {"early", "expanding", "crowded", "exhausted"} else "early"
            strength = float(theme.get("strength", 0))
            themes.append(
                {
                    "name": theme.get("name", "unknown"),
                    "strength": strength,
                    "stage": normalized_stage,
                    "catalyst": theme.get("catalyst", ""),
                    "evidence": [news["headline"] for news in context.get("news", [])[:2]],
                }
            )
        if not themes:
            return self.result(
                context,
                score=35,
                confidence=0.45,
                themes=[],
                primary_theme="unknown",
                theme_leadership="unknown",
                reason="확인된 테마 연결이 부족합니다.",
                risk="테마 근거 부족",
                evidence=provider_evidence(context, ["themes", "news"]),
            )
        average_strength = sum(theme["strength"] for theme in themes) / len(themes)
        bonus = sum(stage_bonus.get(theme["stage"], 0) for theme in themes) / len(themes)
        score = clamp(average_strength + bonus)
        top_strength = max(theme["strength"] for theme in themes)
        leadership = "leader" if top_strength >= 90 else "fast_follower" if top_strength >= 75 else "laggard"
        return self.result(
            context,
            score=score,
            confidence=0.82,
            themes=themes,
            primary_theme=themes[0]["name"],
            theme_leadership=leadership,
            reason=f"{themes[0]['name']} 중심으로 {len(themes)}개 테마가 연결됩니다.",
            risk="crowded 단계 테마는 장중 변동성 확대 가능" if any(t["stage"] == "crowded" for t in themes) else "",
            evidence=provider_evidence(context, ["themes", "news"]),
        )
