from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class ThemeProvider(BaseProvider):
    source = "mock_theme_provider"

    def fetch_themes(self, ticker: str):
        return self.envelope({"ticker": ticker, "themes": MOCK_DATA_STORE.themes(ticker)}, is_realtime=True)
