from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class VolumeProvider(BaseProvider):
    source = "mock_volume_provider"

    def fetch_supply_demand(self, ticker: str):
        return self.envelope({"ticker": ticker, "supply_demand": MOCK_DATA_STORE.supply_demand(ticker)}, is_realtime=True)
