from __future__ import annotations

from src.utils.normalization import won_to_eok


class ReportGenerator:
    def generate(
        self,
        *,
        metadata: dict,
        rs_results: list[dict],
        recommendations: list[dict],
        excluded: list[dict],
        agent_results: dict[str, dict[str, dict]],
        top_n: int,
    ) -> str:
        lines: list[str] = []
        lines.append("# Multi-Agent Stock Picker Report")
        lines.append("")
        lines.extend(self._data_basis(metadata))
        lines.extend(self._market_summary(metadata, recommendations, excluded))
        lines.extend(self._rs_candidates(rs_results[: min(15, len(rs_results))], agent_results))
        lines.extend(self._recommendations(recommendations[:top_n]))
        lines.extend(self._agent_vote_table(recommendations[:top_n], agent_results))
        lines.extend(self._yyang_candidates(recommendations, agent_results))
        lines.extend(self._excluded(excluded))
        lines.extend(self._next_session_checklist(recommendations, excluded))
        return "\n".join(lines)

    def _data_basis(self, metadata: dict) -> list[str]:
        mode = "장중" if metadata.get("market_open") else "장마감 후"
        return [
            "## 1. 데이터 기준",
            f"- 요청 시각: {metadata.get('requested_at_kst')}",
            f"- 데이터 최신화 시각: {metadata.get('data_fetched_at_kst')}",
            f"- 장중/장마감 여부: {mode}",
            f"- 사용한 벤치마크: {metadata.get('benchmark')}",
            f"- 시총 필터: {won_to_eok(metadata.get('market_cap_min_krw'))} 이상",
            "",
        ]

    def _market_summary(self, metadata: dict, recommendations: list[dict], excluded: list[dict]) -> list[str]:
        strong_themes: dict[str, int] = {}
        for item in recommendations:
            for theme in item.get("themes", []):
                strong_themes[theme] = strong_themes.get(theme, 0) + 1
        theme_text = ", ".join(sorted(strong_themes, key=strong_themes.get, reverse=True)[:5]) or "확인 필요"
        risk_text = f"Health veto/시총 제외 {len(excluded)}건" if excluded else "중대 veto 없음"
        return [
            "## 2. 시장 요약",
            "- KOSPI/KOSDAQ 방향: 선택한 benchmark 기준 RS 강한 종목 우선 선별",
            f"- 강한 섹터: {theme_text}",
            "- 약한 섹터: RS 하위 bucket 후보",
            f"- 오늘의 주도 테마: {theme_text}",
            f"- 리스크 이벤트: {risk_text}",
            "",
        ]

    def _rs_candidates(self, rs_results: list[dict], agent_results: dict[str, dict[str, dict]]) -> list[str]:
        lines = [
            "## 3. RS 상위 후보",
            "| 순위 | 종목 | 시총 | RS 5D | RS 10D | RS 20D | RS 추세 | 테마 | 상태 |",
            "|---:|---|---:|---:|---:|---:|---|---|---|",
        ]
        for result in rs_results:
            ticker = result["ticker"]
            theme = agent_results.get(ticker, {}).get("theme_agent", {}).get("primary_theme", "")
            status = agent_results.get(ticker, {}).get("health_agent", {}).get("financial_health", "")
            lines.append(
                f"| {result.get('rs_rank')} | {result.get('name')}({ticker}) | {won_to_eok(result.get('market_cap_krw'))} | "
                f"{result.get('rs_5d')} | {result.get('rs_10d')} | {result.get('rs_20d')} | "
                f"{result.get('rs_line_trend')} | {theme} | {status} |"
            )
        lines.append("")
        return lines

    def _recommendations(self, recommendations: list[dict]) -> list[str]:
        lines = ["## 4. 최종 추천 종목 Top N"]
        if not recommendations:
            return lines + ["- 추천 후보 없음", ""]
        for idx, item in enumerate(recommendations, start=1):
            plan = item.get("trade_plan", {})
            lines.extend(
                [
                    f"### {idx}. {item.get('name')}({item.get('ticker')})",
                    f"- 최종 등급: {item.get('final_grade')}",
                    f"- RS 순위: {item.get('rs_rank')} / Voting 점수: {item.get('raw_vote_score')}",
                    f"- 핵심 테마 3개: {', '.join(item.get('themes', [])[:3])}",
                    f"- 양음양 패턴: {item.get('yyang_eum_yyang_pattern')}",
                    f"- 구분: {item.get('trade_type')} / 돌파 {item.get('breakout_setup')} / 눌림 {item.get('pullback_type')}",
                    f"- 1차 매수: {plan.get('first_buy')}",
                    f"- 2차 매수: {plan.get('second_buy')}",
                    f"- 3차 매수: {plan.get('third_buy')}",
                    f"- 분할매도: {plan.get('partial_sell_1')} / {plan.get('partial_sell_2')}",
                    f"- 손절선: {plan.get('stop_loss')}",
                    f"- 무효화 조건: {plan.get('invalidation')}",
                    f"- 핵심 리스크: {', '.join(item.get('risks', [])) or '특이사항 없음'}",
                    "",
                ]
            )
        return lines

    def _agent_vote_table(self, recommendations: list[dict], agent_results: dict[str, dict[str, dict]]) -> list[str]:
        lines = [
            "## 5. Agent별 투표 결과",
            "| 종목 | RS | Theme | Health | Trader | Breakout | Pullback | Scalping | Volume | Custom | Vote | 최종등급 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
        fields = [
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
        for item in recommendations:
            ticker = item["ticker"]
            scores = [agent_results[ticker].get(field, {}).get("score", "") for field in fields]
            lines.append(
                f"| {item.get('name')} | "
                + " | ".join(str(score) for score in scores)
                + f" | {item.get('raw_vote_score')} | {item.get('final_grade')} |"
            )
        lines.append("")
        return lines

    def _yyang_candidates(self, recommendations: list[dict], agent_results: dict[str, dict[str, dict]]) -> list[str]:
        lines = ["## 6. 양음양 후보"]
        found = False
        for pattern in ["pattern_1", "pattern_2", "pattern_3"]:
            names = [
                f"{item.get('name')}({item.get('ticker')})"
                for item in recommendations
                if item.get("yyang_eum_yyang_pattern") == pattern
            ]
            lines.append(f"- {pattern} 후보: {', '.join(names) if names else '없음'}")
            found = found or bool(names)
        if found:
            lines.append("- 매수 구간: 전일 저점, 5일선, 10일선 부근에서 다분할 기준")
            lines.append("- 거래량 위험: 음봉일 평균 이상 거래량 또는 단기 이평선 이탈 시 제외")
        else:
            lines.append("- 현재 추천군에는 강한 양음양 확정 후보가 제한적입니다.")
        lines.append("")
        return lines

    def _excluded(self, excluded: list[dict]) -> list[str]:
        lines = ["## 7. 제외 종목"]
        if not excluded:
            return lines + ["- 제외 종목 없음", ""]
        for item in excluded:
            lines.append(f"- {item.get('name')}({item.get('ticker')}): {item.get('reason')} / 재검토 조건: veto 해소와 RS 재상승")
        lines.append("")
        return lines

    def _next_session_checklist(self, recommendations: list[dict], excluded: list[dict]) -> list[str]:
        breakout = [item["name"] for item in recommendations if item.get("breakout_setup") in {"ready", "forming"}]
        pullback = [item["name"] for item in recommendations if item.get("pullback_type") != "none"]
        scalping = [item["name"] for item in recommendations if item.get("trade_type") == "day_trade"]
        risky = [item.get("name") for item in excluded]
        return [
            "## 8. 다음 세션 체크리스트",
            f"- 돌파 확인 종목: {', '.join(breakout[:5]) if breakout else '없음'}",
            f"- 눌림 대기 종목: {', '.join(pullback[:5]) if pullback else '없음'}",
            f"- 단타 후보: {', '.join(scalping[:5]) if scalping else '없음'}",
            f"- 뉴스/공시 확인 필요 종목: {', '.join(risky[:5]) if risky else '없음'}",
            "- 위험 이벤트: 장중 대량 음봉, 투자경고/공시, 시장 급락 시 RS 재계산",
            "",
        ]
