from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class DisclosureProvider(BaseProvider):
    source = "mock_disclosure_provider"

    def fetch_disclosures(self, ticker: str, since: str | None = None):
        return self.envelope({"ticker": ticker, "disclosures": MOCK_DATA_STORE.disclosures(ticker)}, is_realtime=True)
