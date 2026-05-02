from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class NewsProvider(BaseProvider):
    source = "mock_news_provider"

    def fetch_news(self, ticker: str, since: str | None = None):
        return self.envelope({"ticker": ticker, "news": MOCK_DATA_STORE.news(ticker)}, is_realtime=True)
