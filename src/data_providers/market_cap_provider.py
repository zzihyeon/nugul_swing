from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class MarketCapProvider(BaseProvider):
    source = "mock_market_cap_provider"

    def fetch_market_cap(self, ticker: str):
        return self.envelope(MOCK_DATA_STORE.market_cap(ticker), is_realtime=True)
