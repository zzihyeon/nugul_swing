from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from src.agents.breakout_agent import BreakoutAgent
from src.agents.custom_doc_agent import CustomDocumentAgent
from src.agents.health_agent import HealthAgent
from src.agents.pullback_agent import PullbackAgent
from src.agents.rs_agent import RSAgent
from src.agents.scalping_agent import ScalpingAgent
from src.agents.theme_agent import ThemeAgent
from src.agents.trader_agent import TraderAgent
from src.agents.volume_flow_agent import VolumeFlowAgent
from src.data_providers.realtime_data_manager import RealtimeDataManager
from src.models.schemas import PipelineResult
from src.report.report_generator import ReportGenerator
from src.utils.config import load_config_dir
from src.voting.voting_engine import VotingEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


def str_to_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() not in {"false", "0", "no", "n"}


def normalize_ticker(value: str) -> str:
    ticker = value.strip()
    return ticker.zfill(6) if ticker.isdigit() and len(ticker) < 6 else ticker


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RS-first Korean stock multi-agent picker")
    parser.add_argument("--universe", default="kospi_kosdaq", help="kospi_kosdaq, kospi200, kosdaq150")
    parser.add_argument("--tickers", default="", help="Comma-separated tickers. Overrides universe when set.")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--market-cap-min", type=int, default=None)
    parser.add_argument("--rs-top-n", type=int, default=None)
    parser.add_argument("--benchmark", default=None)
    parser.add_argument("--include-report", type=str_to_bool, default=True)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--allow-unknown-market-cap", action="store_true")
    parser.add_argument("--provider", choices=["mock", "naver"], default="mock", help="Data provider backend.")
    parser.add_argument("--universe-limit", type=int, default=None, help="Limit fetched universe size for external provider runs.")
    parser.add_argument("--universe-offset", type=int, default=0, help="Skip this many market-cap-ranked tickers before fetching.")
    parser.add_argument("--cache-db", default="", help="SQLite cache DB path. Example: data/cache/stock_picker.sqlite3")
    parser.add_argument("--cache-only", action="store_true", help="Read ticker contexts from SQLite cache without API calls.")
    parser.add_argument("--warm-cache", action="store_true", help="Refresh API data and write it into SQLite cache.")
    parser.add_argument("--cache-ttl-minutes", type=int, default=None, help="Use cached contexts if newer than this many minutes.")
    parser.add_argument(
        "--incremental-cache",
        action="store_true",
        help="Use SQLite first, then refresh only tickers whose cached OHLCV is behind the latest market date.",
    )
    parser.add_argument("--collector-loop", action="store_true", help="Continuously warm the cache until interrupted.")
    parser.add_argument("--collector-interval-minutes", type=int, default=15)
    return parser.parse_args(argv)


def run_pipeline(args: argparse.Namespace) -> PipelineResult:
    configs = load_config_dir(CONFIG_DIR)
    manager = RealtimeDataManager(
        CONFIG_DIR,
        provider=args.provider,
        cache_db=args.cache_db or None,
        cache_only=args.cache_only,
        refresh_cache=args.warm_cache or args.refresh,
        cache_ttl_minutes=args.cache_ttl_minutes,
        incremental_cache=args.incremental_cache,
    )
    tickers = [normalize_ticker(ticker) for ticker in args.tickers.split(",") if ticker.strip()] if args.tickers else None
    universe_data = manager.refresh_universe(
        universe=args.universe,
        tickers=tickers,
        realtime=args.realtime,
        refresh=args.refresh,
        market_cap_min=args.market_cap_min,
        rs_top_n=args.rs_top_n,
        benchmark=args.benchmark,
        allow_unknown_market_cap=args.allow_unknown_market_cap,
        universe_limit=args.universe_limit,
        universe_offset=args.universe_offset,
    )
    records = universe_data["records"]
    contexts_by_ticker = {record["ticker"]: record for record in records}
    rs_agent = RSAgent(configs=configs)
    rs_results = rs_agent.evaluate_many(records)
    rs_top_n = int(universe_data["rs_top_n"])
    rs_forwarded = rs_results[:rs_top_n]

    agent_instances = [
        ThemeAgent(configs=configs),
        HealthAgent(configs=configs),
        TraderAgent(configs=configs),
        BreakoutAgent(configs=configs),
        PullbackAgent(configs=configs),
        ScalpingAgent(configs=configs),
        VolumeFlowAgent(configs=configs),
        CustomDocumentAgent(config_dir=CONFIG_DIR, configs=configs),
    ]
    all_agent_results: dict[str, dict[str, dict[str, Any]]] = {}
    for rs_result in rs_forwarded:
        ticker = rs_result["ticker"]
        context = contexts_by_ticker[ticker]
        all_agent_results[ticker] = {"rs_agent": rs_result}
        for agent in agent_instances:
            all_agent_results[ticker][agent.name] = agent.evaluate(context)

    market_cap_min = int(universe_data["market_cap_min_krw"])
    voting_engine = VotingEngine(configs.get("agent_weights", {}), market_cap_min_krw=market_cap_min)
    recommendations, voting_excluded = voting_engine.rank(all_agent_results)
    excluded = universe_data["excluded_by_market_cap"] + voting_excluded
    recommendations = recommendations[: args.top_n]

    metadata = {
        "requested_at_kst": universe_data["requested_at_kst"],
        "data_fetched_at_kst": universe_data["data_fetched_at_kst"],
        "market_open": universe_data["market_open"],
        "benchmark": universe_data["benchmark"],
        "market_cap_min_krw": market_cap_min,
    }
    report = ""
    if args.include_report:
        report = ReportGenerator().generate(
            metadata=metadata,
            rs_results=rs_results,
            recommendations=recommendations,
            excluded=excluded,
            agent_results=all_agent_results,
            top_n=args.top_n,
        )

    return PipelineResult(
        date=universe_data["requested_at_kst"][:10],
        requested_at_kst=universe_data["requested_at_kst"],
        data_fetched_at_kst=universe_data["data_fetched_at_kst"],
        realtime_refresh=universe_data["realtime_refresh"],
        market_context=f"{args.provider} provider / benchmark={universe_data['benchmark']}",
        filters={
            "market_cap_min_krw": market_cap_min,
            "passed_count": len(records),
            "excluded_by_market_cap_count": len(universe_data["excluded_by_market_cap"]),
        },
        recommendations=recommendations,
        excluded=excluded,
        report=report,
        agent_results=all_agent_results,
    )


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    if args.collector_loop:
        run_collector_loop(args)
        return
    result = run_pipeline(args)
    result_dict = result.to_dict(include_report=args.include_report)
    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.include_report:
        print(result.report)
        print("\n--- JSON ---")
    print(json.dumps(result_dict, ensure_ascii=False, indent=2))


def run_collector_loop(args: argparse.Namespace) -> None:
    if not args.cache_db:
        raise SystemExit("--collector-loop requires --cache-db")
    interval_seconds = max(60, int(args.collector_interval_minutes) * 60)
    args.warm_cache = True
    args.include_report = False
    while True:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        result = run_pipeline(args)
        print(
            json.dumps(
                {
                    "collector_started_at": started,
                    "requested_at_kst": result.requested_at_kst,
                    "passed_count": result.filters["passed_count"],
                    "recommendation_count": len(result.recommendations),
                    "excluded_count": len(result.excluded),
                    "cache_db": args.cache_db,
                },
                ensure_ascii=False,
            )
        )
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
