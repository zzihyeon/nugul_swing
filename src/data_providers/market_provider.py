from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class MarketProvider(BaseProvider):
    source = "mock_market_provider"

    def fetch_market_index(self, index_name: str):
        return self.envelope({"index_name": index_name, "ohlcv": MOCK_DATA_STORE.index_ohlcv(index_name)}, is_realtime=False)

    def fetch_universe(self, universe: str) -> list[str]:
        return MOCK_DATA_STORE.tickers_for_universe(universe)
