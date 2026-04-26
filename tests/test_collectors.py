from datetime import date, timedelta
import unittest

from stock_swing_agents.collectors import (
    DailyCandle,
    RealtimeQuote,
    build_analysis_input_from_market_data,
    normalize_ticker,
    parse_daily_candles,
    parse_realtime_quote,
)


class CollectorTest(unittest.TestCase):
    def test_normalize_ticker_keeps_six_digits(self):
        self.assertEqual(normalize_ticker("5930"), "005930")
        self.assertEqual(normalize_ticker("A005930"), "005930")

    def test_parse_realtime_quote_from_naver_payload(self):
        payload = """
        {
          "resultCode": "success",
          "result": {
            "areas": [
              {
                "name": "SERVICE_ITEM",
                "datas": [
                  {
                    "cd": "005930",
                    "nm": "Samsung",
                    "nv": 71200,
                    "cr": 1.28,
                    "ov": 70500,
                    "hv": 72000,
                    "lv": 70100,
                    "pcv": 70300,
                    "aq": 12345678,
                    "aa": 876543210000,
                    "ms": "OPEN"
                  }
                ]
              }
            ]
          }
        }
        """

        quote = parse_realtime_quote(payload, ticker="005930", retrieved_at="2026-04-26T10:00:00+09:00")

        self.assertEqual(quote.ticker, "005930")
        self.assertEqual(quote.name, "Samsung")
        self.assertEqual(quote.price, 71200)
        self.assertEqual(quote.volume, 12345678)
        self.assertEqual(quote.market_status, "OPEN")

    def test_parse_daily_candles_from_naver_table_rows(self):
        html = """
        <table>
          <tr onMouseOver="mouseOver(this)">
            <td><span>2026.04.24</span></td>
            <td><span>1,200</span></td>
            <td><span>0</span></td>
            <td><span>1,150</span></td>
            <td><span>1,250</span></td>
            <td><span>1,120</span></td>
            <td><span>3,000,000</span></td>
          </tr>
        </table>
        """

        candles = parse_daily_candles(html)

        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].date, "2026.04.24")
        self.assertEqual(candles[0].open, 1150)
        self.assertEqual(candles[0].high, 1250)
        self.assertEqual(candles[0].low, 1120)
        self.assertEqual(candles[0].close, 1200)
        self.assertEqual(candles[0].volume, 3_000_000)

    def test_build_analysis_input_from_collected_market_data(self):
        candles = _sample_candles()
        quote = RealtimeQuote(
            ticker="340440",
            name="Sample",
            price=175,
            change_pct=2.1,
            open=169,
            high=178,
            low=167,
            previous_close=171,
            volume=2200,
            trading_value=385000,
            market_status="CLOSE",
            retrieved_at="2026-04-26T10:00:00+09:00",
            raw={},
        )

        context = build_analysis_input_from_market_data(
            ticker="340440",
            stock_name="Sample",
            quote_data=quote,
            candles=candles,
        )

        self.assertEqual(context.stock_name, "Sample")
        self.assertEqual(context.market_data.price, 175)
        self.assertEqual(context.technical.trend, "up")
        self.assertTrue(context.technical.close_above_ma20)
        self.assertTrue(context.yang_eum_yang.pullback_is_bearish)
        self.assertFalse(context.risk.trade_halt_risk)
        self.assertIsNotNone(context.execution.entry_mode)


def _sample_candles() -> list[DailyCandle]:
    start = date(2026, 1, 1)
    candles: list[DailyCandle] = []
    for idx in range(62):
        close = 100 + idx
        candles.append(
            DailyCandle(
                date=(start + timedelta(days=idx)).strftime("%Y.%m.%d"),
                open=close - 1,
                high=close + 2,
                low=close - 3,
                close=close,
                volume=1000 + idx,
            )
        )
    candles.extend(
        [
            DailyCandle("2026.03.04", 160, 180, 158, 176, 4000),
            DailyCandle("2026.03.05", 175, 177, 165, 168, 1800),
            DailyCandle("2026.03.06", 169, 178, 167, 175, 2200),
        ]
    )
    return candles


if __name__ == "__main__":
    unittest.main()
