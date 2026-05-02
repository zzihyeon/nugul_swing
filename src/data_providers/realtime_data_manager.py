from __future__ import annotations

from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

from src.data_providers.disclosure_provider import DisclosureProvider
from src.data_providers.financial_provider import FinancialProvider
from src.data_providers.market_cap_provider import MarketCapProvider
from src.data_providers.market_provider import MarketProvider
from src.data_providers.naver_provider import NaverFinanceProvider
from src.data_providers.news_provider import NewsProvider
from src.data_providers.price_provider import PriceProvider
from src.data_providers.sqlite_cache import SQLiteCache
from src.data_providers.theme_provider import ThemeProvider
from src.data_providers.volume_provider import VolumeProvider
from src.models.schemas import ProviderEnvelope
from src.utils.config import load_config_dir
from src.utils.market_time import is_market_open_kst, now_kst, parse_kst, stale_cutoff_delta


class RealtimeDataManager:
    def __init__(
        self,
        config_dir: str | Path,
        provider: str = "mock",
        *,
        cache_db: str | Path | None = None,
        cache_only: bool = False,
        refresh_cache: bool = False,
        cache_ttl_minutes: int | None = None,
        incremental_cache: bool = False,
    ) -> None:
        self.config_dir = Path(config_dir)
        self.configs = load_config_dir(self.config_dir)
        self.provider_name = provider
        self.cache = SQLiteCache(cache_db) if cache_db else None
        self.cache_only = cache_only
        self.refresh_cache = refresh_cache
        self.cache_ttl_seconds = cache_ttl_minutes * 60 if cache_ttl_minutes is not None else None
        self.incremental_cache = incremental_cache
        self._target_market_dates: dict[str, date] = {}
        if provider == "naver":
            historical_days = int(self.configs.get("realtime_config", {}).get("historical_ohlcv_days", 1095))
            naver_provider = NaverFinanceProvider(historical_days=historical_days)
            self.price_provider = naver_provider
            self.market_provider = naver_provider
            self.news_provider = naver_provider
            self.theme_provider = naver_provider
            self.financial_provider = naver_provider
            self.volume_provider = naver_provider
            self.disclosure_provider = naver_provider
            self.market_cap_provider = naver_provider
        else:
            self.price_provider = PriceProvider()
            self.market_provider = MarketProvider()
            self.news_provider = NewsProvider()
            self.theme_provider = ThemeProvider()
            self.financial_provider = FinancialProvider()
            self.volume_provider = VolumeProvider()
            self.disclosure_provider = DisclosureProvider()
            self.market_cap_provider = MarketCapProvider()

    def refresh_universe(
        self,
        *,
        universe: str = "kospi_kosdaq",
        tickers: list[str] | None = None,
        realtime: bool = False,
        refresh: bool = False,
        market_cap_min: int | None = None,
        rs_top_n: int | None = None,
        benchmark: str | None = None,
        allow_unknown_market_cap: bool | None = None,
        universe_limit: int | None = None,
        universe_offset: int = 0,
    ) -> dict[str, Any]:
        requested_at = now_kst()
        market_cap_config = self.configs.get("market_cap_filter", {})
        min_cap = int(market_cap_min or market_cap_config.get("market_cap_min_krw", 300_000_000_000))
        allow_unknown = bool(
            allow_unknown_market_cap
            if allow_unknown_market_cap is not None
            else market_cap_config.get("allow_unknown_market_cap", False)
        )
        rs_config = self.configs.get("rs_config", {})
        selected_rs_top_n = int(rs_top_n or rs_config.get("rs_top_n", 100))
        selected_tickers = tickers or self._fetch_or_load_universe(universe)
        if tickers is None:
            if universe_offset:
                selected_tickers = selected_tickers[universe_offset:]
            if universe_limit:
                selected_tickers = selected_tickers[:universe_limit]

        records: list[dict[str, Any]] = []
        excluded_by_market_cap: list[dict[str, Any]] = []
        for ticker in selected_tickers:
            record = self._fetch_or_load_ticker_context(ticker, realtime=realtime or refresh, benchmark=benchmark)
            market_cap = record.get("market_cap_krw")
            if market_cap is None:
                record["passed_market_cap_filter"] = False
                record["market_cap_unknown"] = True
                record["watch_only"] = allow_unknown
                record["exclusion_reason"] = "market_cap_unknown"
                if not allow_unknown:
                    excluded_by_market_cap.append({"ticker": ticker, "name": record.get("name"), "reason": "market_cap_unknown"})
                    continue
            elif market_cap < min_cap:
                record["passed_market_cap_filter"] = False
                record["watch_only"] = False
                record["exclusion_reason"] = "market_cap_below_300bn"
                excluded_by_market_cap.append(
                    {
                        "ticker": ticker,
                        "name": record.get("name"),
                        "market_cap_krw": market_cap,
                        "reason": "market_cap_below_300bn",
                    }
                )
                continue
            else:
                record["passed_market_cap_filter"] = True
                record["watch_only"] = False
            records.append(record)

        fetched_times = [
            envelope["fetched_at_kst"]
            for record in records
            for envelope in record.get("provider_envelopes", {}).values()
            if envelope.get("fetched_at_kst")
        ]
        data_fetched_at = max(fetched_times) if fetched_times else requested_at.isoformat(timespec="seconds")
        market_open = is_market_open_kst(requested_at)

        return {
            "requested_at_kst": requested_at.isoformat(timespec="seconds"),
            "data_fetched_at_kst": data_fetched_at,
            "realtime_refresh": bool(realtime or refresh),
            "market_open": market_open,
            "benchmark": benchmark or rs_config.get("benchmark_default", "KOSPI_KOSDAQ_BY_LISTING"),
            "market_cap_min_krw": min_cap,
            "rs_top_n": selected_rs_top_n,
            "records": records,
            "excluded_by_market_cap": excluded_by_market_cap,
        }

    def _fetch_or_load_universe(self, universe: str) -> list[str]:
        if self.cache and not self.refresh_cache:
            cached_universe = self.cache.get_universe(
                self.provider_name,
                universe,
                max_age_seconds=None if self.incremental_cache else self.cache_ttl_seconds,
                allow_stale=self.cache_only or self.incremental_cache,
            )
            if cached_universe:
                return cached_universe
        if self.cache_only:
            raise RuntimeError(f"cache_only requested but universe cache is missing: {self.provider_name}/{universe}")
        tickers = self.market_provider.fetch_universe(universe)
        if self.cache:
            self.cache.set_universe(self.provider_name, universe, tickers)
        return tickers

    def _fetch_or_load_ticker_context(self, ticker: str, *, realtime: bool, benchmark: str | None) -> dict[str, Any]:
        if self.cache and not self.refresh_cache:
            if self.incremental_cache:
                cached_context = self.cache.get_context(self.provider_name, ticker, allow_stale=True)
            else:
                cached_context = self.cache.get_context(
                    self.provider_name,
                    ticker,
                    max_age_seconds=self.cache_ttl_seconds,
                    allow_stale=self.cache_only,
                )
            if cached_context is not None:
                if self.cache_only:
                    return cached_context
                if self.incremental_cache:
                    needs_update, target_date, last_ohlcv_date = self._context_update_status(cached_context)
                    needs_realtime_update = realtime and is_market_open_kst() and self._has_stale_realtime_envelope(cached_context)
                    if not needs_update and not needs_realtime_update:
                        cached_context["incremental_cache_hit"] = True
                        cached_context["incremental_cache_target_date"] = target_date.isoformat()
                        cached_context["incremental_cache_last_ohlcv_date"] = (
                            last_ohlcv_date.isoformat() if last_ohlcv_date else None
                        )
                        return cached_context
                else:
                    return cached_context
        if self.cache_only:
            raise RuntimeError(f"cache_only requested but ticker context cache is missing: {self.provider_name}/{ticker}")
        context = self._fetch_ticker_context(ticker, realtime=realtime, benchmark=benchmark)
        context["loaded_from_cache"] = False
        if self.incremental_cache:
            _, target_date, last_ohlcv_date = self._context_update_status(context)
            context["incremental_cache_refreshed"] = True
            context["incremental_cache_target_date"] = target_date.isoformat()
            context["incremental_cache_last_ohlcv_date"] = last_ohlcv_date.isoformat() if last_ohlcv_date else None
        if self.cache:
            self.cache.set_context(self.provider_name, ticker, context)
        return context

    def _fetch_ticker_context(self, ticker: str, *, realtime: bool, benchmark: str | None) -> dict[str, Any]:
        market_cap = self.market_cap_provider.fetch_market_cap(ticker)
        latest_price = self.price_provider.fetch_latest_price(ticker)
        ohlcv = self.price_provider.fetch_ohlcv(ticker)
        intraday = self.price_provider.fetch_intraday(ticker)
        news = self.news_provider.fetch_news(ticker)
        themes = self.theme_provider.fetch_themes(ticker)
        financials = self.financial_provider.fetch_financials(ticker)
        supply = self.volume_provider.fetch_supply_demand(ticker)
        disclosures = self.disclosure_provider.fetch_disclosures(ticker)

        market_cap_data = market_cap.data
        listing_market = market_cap_data.get("listing_market", "KOSPI")
        benchmark_name = self._resolve_benchmark(listing_market, benchmark)
        benchmark_envelope = self.market_provider.fetch_market_index(benchmark_name)

        provider_envelopes = {
            "market_cap": market_cap.to_dict(),
            "latest_price": latest_price.to_dict(),
            "ohlcv": ohlcv.to_dict(),
            "intraday": intraday.to_dict(),
            "news": news.to_dict(),
            "themes": themes.to_dict(),
            "financials": financials.to_dict(),
            "supply_demand": supply.to_dict(),
            "disclosures": disclosures.to_dict(),
            "benchmark": benchmark_envelope.to_dict(),
        }

        stale_data = any(envelope["is_stale"] for envelope in provider_envelopes.values())
        return {
            "ticker": ticker,
            "name": market_cap_data.get("name"),
            "listing_market": listing_market,
            "market_cap_krw": market_cap_data.get("market_cap_krw"),
            "status_flags": market_cap_data.get("status_flags", []),
            "latest_price": latest_price.data,
            "ohlcv": ohlcv.data["ohlcv"],
            "intraday": intraday.data,
            "news": news.data.get("news", []),
            "themes": themes.data.get("themes", []),
            "financials": financials.data.get("financials", {}),
            "supply_demand": supply.data.get("supply_demand", {}),
            "disclosures": disclosures.data.get("disclosures", []),
            "benchmark_name": benchmark_name,
            "benchmark_ohlcv": benchmark_envelope.data["ohlcv"],
            "provider_envelopes": provider_envelopes,
            "stale_data": stale_data,
            "data_confidence": 0.72 if stale_data else 1.0,
            "is_realtime": realtime,
        }

    def _resolve_benchmark(self, listing_market: str, benchmark: str | None) -> str:
        if benchmark and benchmark != "KOSPI_KOSDAQ_BY_LISTING":
            return benchmark
        return "KOSDAQ" if listing_market.upper() == "KOSDAQ" else "KOSPI"

    def _context_needs_incremental_update(self, context: dict[str, Any], *, target_date: date | None = None) -> bool:
        needs_update, _, _ = self._context_update_status(context, target_date=target_date)
        return needs_update

    def _context_update_status(
        self,
        context: dict[str, Any],
        *,
        target_date: date | None = None,
    ) -> tuple[bool, date, date | None]:
        last_ohlcv_date = self._latest_ohlcv_date(context.get("ohlcv", []))
        benchmark_name = context.get("benchmark_name")
        selected_target_date = target_date or self._target_market_date(
            benchmark_name,
            fallback_rows=context.get("benchmark_ohlcv", []),
        )
        if last_ohlcv_date is None:
            return True, selected_target_date, None
        return last_ohlcv_date < selected_target_date, selected_target_date, last_ohlcv_date

    def _target_market_date(
        self,
        benchmark_name: str | None = None,
        *,
        fallback_rows: list[dict[str, Any]] | None = None,
    ) -> date:
        benchmark_key = self._benchmark_cache_key(benchmark_name)
        if benchmark_key in self._target_market_dates:
            return self._target_market_dates[benchmark_key]
        if self.provider_name == "naver" and not self.cache_only:
            try:
                benchmark_envelope = self.market_provider.fetch_market_index(benchmark_key)
                latest_market_date = self._latest_ohlcv_date(benchmark_envelope.data.get("ohlcv", []))
                if latest_market_date is not None:
                    self._target_market_dates[benchmark_key] = latest_market_date
                    return latest_market_date
            except Exception:
                pass
        fallback_market_date = self._latest_ohlcv_date(fallback_rows or [])
        if fallback_market_date is not None:
            return fallback_market_date
        calendar_date = self._calendar_market_date()
        self._target_market_dates[benchmark_key] = calendar_date
        return calendar_date

    def _benchmark_cache_key(self, benchmark_name: str | None) -> str:
        if not benchmark_name or benchmark_name == "KOSPI_KOSDAQ_BY_LISTING":
            return "KOSPI"
        benchmark = benchmark_name.upper()
        return "KOSDAQ" if benchmark == "KOSDAQ" else "KOSPI"

    def _calendar_market_date(self) -> date:
        current = now_kst()
        candidate = current.date()
        if current.weekday() >= 5:
            return self._previous_weekday(candidate)
        if current.time() < time(9, 0):
            return self._previous_weekday(candidate)
        return candidate

    def _previous_weekday(self, candidate: date) -> date:
        previous = candidate - timedelta(days=1)
        while previous.weekday() >= 5:
            previous -= timedelta(days=1)
        return previous

    def _latest_ohlcv_date(self, rows: list[dict[str, Any]]) -> date | None:
        for row in reversed(rows or []):
            value = row.get("date")
            if not value:
                continue
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                continue
        return None

    def _has_stale_realtime_envelope(self, context: dict[str, Any]) -> bool:
        envelopes = context.get("provider_envelopes", {})
        for key in ("latest_price", "intraday", "news", "supply_demand"):
            envelope = envelopes.get(key)
            if envelope and self.is_stale(envelope):
                return True
        return False

    def is_stale(self, envelope: ProviderEnvelope | dict[str, Any], *, current_time=None) -> bool:
        realtime_config = self.configs.get("realtime_config", {})
        current_time = current_time or now_kst()
        fetched_at = envelope.fetched_at_kst if isinstance(envelope, ProviderEnvelope) else envelope.get("fetched_at_kst")
        if not fetched_at:
            return bool(realtime_config.get("require_fetched_at_kst", True))
        fetched_dt = parse_kst(fetched_at)
        allowed_delta = stale_cutoff_delta(realtime_config, is_market_open_kst(current_time))
        return current_time - fetched_dt > allowed_delta
