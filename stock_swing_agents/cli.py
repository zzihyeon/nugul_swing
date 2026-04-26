"""Command-line interface for the swing agent voting engine."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Sequence

from .agents import SwingVotingEngine
from .models import (
    AnalysisInput,
    DataSource,
    ExecutionSnapshot,
    MarketDataSnapshot,
    NewsDisclosureSnapshot,
    PostTradeSnapshot,
    RiskSnapshot,
    SupplyDemandSnapshot,
    TechnicalSnapshot,
    ThemeFollowSnapshot,
    ThemeSectorSnapshot,
    YangEumYangSnapshot,
    to_plain,
)
from .theme_parser import (
    build_theme_follow_snapshot_from_file,
    build_theme_snapshot_from_file,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="한국 주식 스윙 매매 보조 Agent voting CLI"
    )
    parser.add_argument("--input", type=Path, help="분석 입력 JSON 파일")
    parser.add_argument("--stock", help="종목명. 입력 JSON이 없을 때 샘플에 사용합니다.")
    parser.add_argument("--ticker", help="종목 코드")
    parser.add_argument("--theme", help="테마 추종 Agent가 우선 추적할 테마명")
    parser.add_argument("--theme-file", type=Path, help="테마 주간 메모 파일")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    args = parser.parse_args(argv)

    context = _load_context(args.input, args.stock, args.ticker)
    if args.theme_file:
        context.theme_sector = build_theme_snapshot_from_file(
            args.theme_file,
            stock_name=context.stock_name,
        )
        context.theme_follow = build_theme_follow_snapshot_from_file(
            args.theme_file,
            stock_name=context.stock_name,
            target_theme=args.theme,
        )

    decision = SwingVotingEngine().evaluate(context)
    if args.json:
        print(json.dumps(to_plain(decision), ensure_ascii=False, indent=2))
    else:
        print(_format_human(context, decision))
    return 0


def _load_context(
    input_path: Path | None,
    stock_name: str | None,
    ticker: str | None,
) -> AnalysisInput:
    if input_path:
        data = json.loads(input_path.read_text(encoding="utf-8-sig"))
        return AnalysisInput.from_dict(data)
    return _sample_context(stock_name or "샘플종목", ticker)


def _sample_context(stock_name: str, ticker: str | None) -> AnalysisInput:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    investing = DataSource(
        name="Investing.com Economic Calendar",
        url="https://www.investing.com/economic-calendar/",
        retrieved_at=now,
        delay="real-time when queried",
    )
    krx = DataSource(
        name="KRX 정보데이터시스템",
        url="https://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd?vsView=Y",
        retrieved_at=now,
        delay="일부 20분 지연 가능",
    )
    dart = DataSource(
        name="OpenDART",
        url="https://opendart.fss.or.kr/intro/main.do",
        retrieved_at=now,
        delay="공시 반영 시점 기준",
    )
    return AnalysisInput(
        stock_name=stock_name,
        ticker=ticker,
        market_data=MarketDataSnapshot(
            price=10000,
            change_pct=2.4,
            volume_ratio=1.8,
            trading_value_rank=25,
            kospi_change_pct=0.3,
            kosdaq_change_pct=0.7,
            usdkrw_change_pct=-0.1,
            sources=[krx, investing],
        ),
        technical=TechnicalSnapshot(
            trend="up",
            close_above_ma20=True,
            close_above_ma60=True,
            rsi=61,
            macd_histogram=0.4,
            support=9400,
            resistance=11200,
            stop_loss=9300,
        ),
        supply_demand=SupplyDemandSnapshot(
            foreign_net_buy_krw=1_200_000_000,
            institution_net_buy_krw=700_000_000,
            program_net_buy_krw=300_000_000,
            consecutive_foreign_buy_days=3,
            sources=[krx],
        ),
        news_disclosure=NewsDisclosureSnapshot(
            positive_events=["최근 긍정 뉴스가 확인되었습니다."],
            high_impact_events=["주요 경제 이벤트 일정 확인 필요"],
            sources=[investing, dart],
        ),
        theme_sector=ThemeSectorSnapshot(
            themes=["샘플 테마"],
            leading_stock=True,
            sector_breadth=4,
            theme_persistence_days=3,
        ),
        theme_follow=ThemeFollowSnapshot(
            target_theme="샘플 테마",
            latest_event_date="2026-04-26",
            freshness_days=0,
            recent_event_count=3,
            positive_event_count=3,
            negative_event_count=0,
            latest_event="샘플 테마 상승 이벤트",
            latest_leaders=[stock_name],
            recurring_leaders=[stock_name],
            follow_candidates=[stock_name],
        ),
        yang_eum_yang=YangEumYangSnapshot(
            pattern="pattern1",
            first_candle_gain_pct=11.4,
            first_candle_has_upper_shadow=False,
            first_candle_volume_ratio=2.8,
            pullback_is_bearish=True,
            pullback_holds_ma5=True,
            pullback_volume_pct_of_first=45,
            short_ma_distance_pct=3.2,
            current_above_short_ma=True,
            entry_near_previous_low=True,
            entry_near_short_ma=True,
            has_theme_or_momentum=True,
            opening_volume_spike=False,
            pullback_low_broken=False,
            short_ma_broken=False,
            sources=[DataSource(name="핀업 스탁 양음양 법칙 PDF", delay="rule reference")],
        ),
        risk=RiskSnapshot(
            volatility_pct=4.8,
            gap_risk=False,
            trade_halt_risk=False,
            investment_warning=False,
            bad_disclosure_risk=False,
            max_position_pct=15,
            stop_loss=9300,
        ),
        execution=ExecutionSnapshot(
            price_vs_support_pct=4.5,
            price_vs_resistance_pct=9.0,
            pullback_ready=True,
            breakout_confirmed=False,
            entry_mode="분할 진입",
        ),
        post_trade=PostTradeSnapshot(
            journal=["진입 근거와 손절 기준 기록"],
            last_rule_breach=False,
        ),
    )


def _format_human(context: AnalysisInput, decision) -> str:
    lines = [
        f"종목: {context.stock_name}" + (f" ({context.ticker})" if context.ticker else ""),
        f"최종 판단: {decision.decision.value}",
        f"총점: {decision.score_total}",
        f"손절 기준: {decision.stop_loss}",
        f"시간축: {decision.time_horizon}",
        "",
        "[최종 근거]",
    ]
    lines.extend(f"- {item}" for item in decision.reason)
    lines.append("")
    lines.append("[반대 근거]")
    lines.extend(f"- {item}" for item in decision.counter_reason)
    lines.append("")
    lines.append("[Agent Voting]")
    for vote in decision.votes:
        lines.append(
            f"- {vote.agent}: {vote.signal.value}, score {vote.score:+d}, "
            f"confidence {vote.confidence}"
        )
        lines.append("  근거: " + " / ".join(vote.evidence))
        lines.append("  리스크: " + " / ".join(vote.risk))
    if decision.sources:
        lines.append("")
        lines.append("[Data Sources]")
        for source in decision.sources:
            delay = f", delay={source.delay}" if source.delay else ""
            when = f", retrieved_at={source.retrieved_at}" if source.retrieved_at else ""
            url = f", url={source.url}" if source.url else ""
            lines.append(f"- {source.name}{delay}{when}{url}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
