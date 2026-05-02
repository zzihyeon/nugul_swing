from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent, provider_evidence
from src.utils.indicators import closes, return_pct
from src.utils.normalization import clamp


class RSAgent(BaseAgent):
    name = "rs_agent"

    def evaluate_many(self, contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        results = [self._evaluate_without_rank(context) for context in contexts]
        results.sort(
            key=lambda item: (
                int(item.get("rs_sort_bucket", 9)),
                -float(item.get("rs_composite_raw", -999)),
            )
        )
        total = len(results)
        for idx, result in enumerate(results, start=1):
            percentile = 100.0 if total == 1 else 100.0 - ((idx - 1) / (total - 1) * 100.0)
            percentile = round(percentile, 2)
            result["rs_rank"] = idx
            result["rs_percentile"] = percentile
            result["score"] = percentile
            result["reason"] = self._reason(result)
            result["risk"] = (
                "KOSPI/KOSDAQ benchmark 대비 5/10/20일 RS가 모두 우위입니다."
                if result.get("market_outperformance")
                else "benchmark 대비 5/10/20일 RS 중 일부가 열위라 RS 우선 후보로는 감점입니다."
            )
        return results

    def evaluate(self, context: dict[str, Any]) -> dict[str, Any]:
        return self._evaluate_without_rank(context)

    def _evaluate_without_rank(self, context: dict[str, Any]) -> dict[str, Any]:
        stock_close = closes(context["ohlcv"])
        benchmark_close = closes(context["benchmark_ohlcv"])
        windows = self.configs.get("rs_config", {}).get("rs_windows", [5, 10, 20, 60])
        stock_returns = {f"stock_return_{window}d": round(return_pct(stock_close, int(window)), 2) for window in windows}
        benchmark_returns = {f"benchmark_return_{window}d": round(return_pct(benchmark_close, int(window)), 2) for window in windows}
        rs_values = {}
        for window in windows:
            rs_values[f"rs_{window}d"] = round(
                stock_returns[f"stock_return_{window}d"] - benchmark_returns[f"benchmark_return_{window}d"],
                2,
            )
        rs5 = rs_values.get("rs_5d", 0.0)
        rs10 = rs_values.get("rs_10d", 0.0)
        rs20 = rs_values.get("rs_20d", 0.0)
        rs60 = rs_values.get("rs_60d", 0.0)
        weighted_rs = rs5 * 0.35 + rs10 * 0.25 + rs20 * 0.25 + rs60 * 0.15

        rs_line = [stock / benchmark for stock, benchmark in zip(stock_close[-20:], benchmark_close[-20:]) if benchmark]
        trend = "flat"
        if len(rs_line) >= 5:
            if rs_line[-1] > max(rs_line[:-1]) * 0.995 and rs_line[-1] > rs_line[-5]:
                trend = "rising"
            elif rs_line[-1] < rs_line[-5] * 0.995:
                trend = "falling"

        market_outperformance = rs5 > 0 and rs10 > 0 and rs20 > 0
        primary_positive_count = sum(1 for value in [rs5, rs10, rs20] if value > 0)
        if market_outperformance:
            rs_sort_bucket = 1
        elif primary_positive_count >= 2 and trend in {"rising", "flat"}:
            rs_sort_bucket = 2
        else:
            rs_sort_bucket = 3
        squeeze_candidate = trend == "rising" and abs(return_pct(stock_close, 10)) < 4 and rs10 > 1.5
        return self.result(
            context,
            score=0,
            confidence=0.9 if not context.get("stale_data") else 0.65,
            benchmark_name=context.get("benchmark_name"),
            market_cap_krw=context.get("market_cap_krw"),
            passed_market_cap_filter=context.get("passed_market_cap_filter", False),
            rs_rank=0,
            rs_percentile=0,
            rs_composite_raw=round(weighted_rs, 4),
            rs_sort_bucket=rs_sort_bucket,
            rs_5d=rs5,
            rs_10d=rs10,
            rs_20d=rs20,
            rs_60d=rs60,
            **stock_returns,
            **benchmark_returns,
            rs_line_trend=trend,
            market_outperformance=market_outperformance,
            sector_outperformance=market_outperformance,
            squeeze_candidate_by_rs=squeeze_candidate,
            reason="RS percentile is assigned after universe ranking.",
            risk="",
            evidence=provider_evidence(context, ["ohlcv", "benchmark", "market_cap"]),
            name=context.get("name"),
        )

    def _reason(self, result: dict[str, Any]) -> str:
        benchmark = result.get("benchmark_name", "benchmark")
        return (
            f"{benchmark} 대비 초과수익률 RS 5/10/20/60일 = "
            f"{result.get('rs_5d'):.2f}/{result.get('rs_10d'):.2f}/"
            f"{result.get('rs_20d'):.2f}/{result.get('rs_60d'):.2f}%p, "
            f"100분위 RS score = {result.get('rs_percentile')}입니다."
        )
