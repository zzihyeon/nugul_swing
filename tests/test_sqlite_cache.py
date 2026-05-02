import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.data_providers.realtime_data_manager import RealtimeDataManager
from src.data_providers.sqlite_cache import SQLiteCache
from src.main import parse_args, run_pipeline


class SQLiteCacheTest(unittest.TestCase):
    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "cache.sqlite3"
            cache = SQLiteCache(db_path)
            cache.set_universe("mock", "kospi_kosdaq", ["005930", "000660"])
            cache.set_context("mock", "005930", {"ticker": "005930", "value": 1})

            self.assertEqual(cache.get_universe("mock", "kospi_kosdaq"), ["005930", "000660"])
            self.assertEqual(cache.get_context("mock", "005930")["value"], 1)
            self.assertEqual(cache.count("ticker_context"), 1)

    def test_pipeline_can_read_cache_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "cache.sqlite3")
            warm_args = parse_args(
                [
                    "--provider",
                    "mock",
                    "--tickers",
                    "000660,005930",
                    "--top-n",
                    "2",
                    "--cache-db",
                    db_path,
                    "--warm-cache",
                    "--include-report",
                    "false",
                ]
            )
            run_pipeline(warm_args)

            cached_args = parse_args(
                [
                    "--provider",
                    "mock",
                    "--tickers",
                    "000660,005930",
                    "--top-n",
                    "2",
                    "--cache-db",
                    db_path,
                    "--cache-only",
                    "--include-report",
                    "false",
                ]
            )
            result = run_pipeline(cached_args)
            self.assertEqual(result.filters["passed_count"], 2)
            self.assertTrue(result.agent_results["000660"]["rs_agent"]["score"] >= 0)

    def test_incremental_cache_detects_missing_market_dates(self):
        manager = RealtimeDataManager("config", provider="mock")
        current_context = {"ohlcv": [{"date": "2026-05-01", "close": 100}]}
        stale_context = {"ohlcv": [{"date": "2026-04-30", "close": 100}]}

        self.assertFalse(
            manager._context_needs_incremental_update(current_context, target_date=date(2026, 5, 1))
        )
        self.assertTrue(
            manager._context_needs_incremental_update(stale_context, target_date=date(2026, 5, 1))
        )


if __name__ == "__main__":
    unittest.main()
