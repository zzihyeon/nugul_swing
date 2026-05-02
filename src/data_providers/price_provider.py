from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class PriceProvider(BaseProvider):
    source = "mock_price_provider"

    def fetch_ohlcv(self, ticker: str, start: str | None = None, end: str | None = None):
        return self.envelope({"ticker": ticker, "ohlcv": MOCK_DATA_STORE.ohlcv(ticker)}, is_realtime=False)

    def fetch_intraday(self, ticker: str):
        return self.envelope(MOCK_DATA_STORE.intraday(ticker), is_realtime=True)

    def fetch_latest_price(self, ticker: str):
        return self.envelope(MOCK_DATA_STORE.latest_price(ticker), is_realtime=True)
