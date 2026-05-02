from __future__ import annotations

from src.data_providers.base_provider import BaseProvider, MOCK_DATA_STORE


class FinancialProvider(BaseProvider):
    source = "mock_financial_provider"

    def fetch_financials(self, ticker: str):
        return self.envelope({"ticker": ticker, "financials": MOCK_DATA_STORE.financials(ticker)}, is_realtime=False)
