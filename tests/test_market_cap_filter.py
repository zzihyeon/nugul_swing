import unittest

from src.main import parse_args, run_pipeline


class MarketCapFilterTest(unittest.TestCase):
    def test_excludes_market_cap_below_300bn(self):
        args = parse_args(["--tickers", "999999,005930", "--include-report", "false"])
        result = run_pipeline(args)
        self.assertEqual(result.filters["passed_count"], 1)
        self.assertEqual(result.filters["excluded_by_market_cap_count"], 1)
        self.assertEqual(result.excluded[0]["ticker"], "999999")
        self.assertIn("market_cap_below_300bn", result.excluded[0]["reason"])


if __name__ == "__main__":
    unittest.main()
