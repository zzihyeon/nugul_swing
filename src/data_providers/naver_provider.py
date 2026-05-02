from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import timedelta
from typing import Any

from src.data_providers.base_provider import BaseProvider
from src.utils.market_time import now_kst


class NaverFinanceProvider(BaseProvider):
    source = "naver_finance_public"

    def __init__(self, historical_days: int = 1095) -> None:
        self.headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://m.stock.naver.com/",
            "Accept": "application/json,text/plain,*/*",
        }
        self.historical_days = historical_days
        self._basic_cache: dict[str, dict[str, Any]] = {}
        self._integration_cache: dict[str, dict[str, Any]] = {}
        self._ohlcv_cache: dict[str, list[dict[str, Any]]] = {}

    def fetch_universe(self, universe: str) -> list[str]:
        if universe == "kosdaq150":
            return self._fetch_market_sum_universe(["1"], min_market_cap_eok=3_000)
        if universe == "kospi200":
            return self._fetch_market_sum_universe(["0"], min_market_cap_eok=3_000)
        return self._fetch_market_sum_universe(["0", "1"], min_market_cap_eok=3_000)

    def fetch_ohlcv(self, ticker: str, start: str | None = None, end: str | None = None):
        if ticker not in self._ohlcv_cache:
            self._ohlcv_cache[ticker] = self._fetch_daily_ohlcv(ticker)
        return self.envelope({"ticker": ticker, "ohlcv": self._ohlcv_cache[ticker]}, is_realtime=False)

    def fetch_intraday(self, ticker: str):
        integration = self._integration(ticker)
        infos = self._total_infos(integration)
        latest = self._num(self._basic(ticker).get("closePrice") or infos.get("closePrice") or infos.get("lastClosePrice"))
        volume = self._num(infos.get("accumulatedTradingVolume"))
        turnover = self._parse_value_million_krw(infos.get("accumulatedTradingValue", "0"))
        vwap = turnover / volume if volume else latest
        return self.envelope(
            {
                "ticker": ticker,
                "latest_price": latest,
                "intraday_volume": volume,
                "intraday_turnover": turnover,
                "vwap": round(vwap, 2) if vwap else latest,
                "bars": [],
            },
            is_realtime=True,
        )

    def fetch_latest_price(self, ticker: str):
        basic = self._basic(ticker)
        integration = self._integration(ticker)
        infos = self._total_infos(integration)
        latest = self._num(basic.get("closePrice"))
        previous = latest - self._num(basic.get("compareToPreviousClosePrice"))
        volume = self._num(infos.get("accumulatedTradingVolume"))
        turnover = self._parse_value_million_krw(infos.get("accumulatedTradingValue", "0"))
        return self.envelope(
            {
                "ticker": ticker,
                "name": basic.get("stockName") or integration.get("stockName") or ticker,
                "latest_price": latest,
                "close": latest,
                "daily_volume": volume,
                "daily_turnover": turnover,
                "change_pct": self._float(basic.get("fluctuationsRatio")),
                "previous_close": previous,
                "local_traded_at": basic.get("localTradedAt"),
            },
            is_realtime=True,
        )

    def fetch_market_cap(self, ticker: str):
        basic = self._basic(ticker)
        integration = self._integration(ticker)
        infos = self._total_infos(integration)
        listing_market = "KOSDAQ" if basic.get("stockExchangeType", {}).get("nameEng") == "KOSDAQ" else "KOSPI"
        market_cap_krw = self._parse_korean_market_value(infos.get("marketValue", ""))
        return self.envelope(
            {
                "ticker": ticker,
                "name": basic.get("stockName") or integration.get("stockName") or ticker,
                "market_cap_krw": market_cap_krw,
                "listing_market": listing_market,
                "status_flags": [],
            },
            is_realtime=True,
            confidence=0.86 if market_cap_krw else 0.45,
        )

    def fetch_market_index(self, index_name: str):
        symbol = "KOSDAQ" if index_name.upper() == "KOSDAQ" else "KOSPI"
        if symbol not in self._ohlcv_cache:
            self._ohlcv_cache[symbol] = self._fetch_daily_ohlcv(symbol)
        return self.envelope({"index_name": symbol, "ohlcv": self._ohlcv_cache[symbol]}, is_realtime=False)

    def fetch_news(self, ticker: str, since: str | None = None):
        url = f"https://m.stock.naver.com/api/news/stock/{ticker}?pageSize=10&page=1"
        try:
            payload = self._json(url)
            groups = payload if isinstance(payload, list) else [payload]
            news = []
            for group in groups:
                for item in group.get("items", []):
                    news.append(
                        {
                            "headline": item.get("titleFull") or item.get("title", ""),
                            "published_at_kst": self._format_news_time(item.get("datetime", "")),
                            "source": item.get("officeName", "naver_news"),
                            "url": f"https://n.news.naver.com/mnews/article/{item.get('officeId')}/{item.get('articleId')}"
                            if item.get("officeId") and item.get("articleId")
                            else "",
                        }
                    )
            return self.envelope({"ticker": ticker, "news": news[:10]}, is_realtime=True)
        except Exception as exc:
            return self.envelope({"ticker": ticker, "news": [], "error": str(exc)}, is_realtime=True, is_stale=True, confidence=0.35)

    def fetch_financials(self, ticker: str):
        integration = self._integration(ticker)
        infos = self._total_infos(integration)
        return self.envelope(
            {
                "ticker": ticker,
                "financials": {
                    "per": self._float_text(infos.get("per", "")),
                    "pbr": self._float_text(infos.get("pbr", "")),
                    "eps": self._num(infos.get("eps", "")),
                    "foreign_rate": infos.get("foreignRate", ""),
                    "audit_opinion": "unknown",
                    "debt_ratio": 100,
                    "operating_margin": 0,
                    "cashflow": "unknown",
                }
            },
            is_realtime=False,
            confidence=0.62,
        )

    def fetch_supply_demand(self, ticker: str):
        trend = self._integration(ticker).get("dealTrendInfos", [])[:5]
        foreign_sum = sum(self._signed_num(row.get("foreignerPureBuyQuant", "0")) for row in trend)
        institution_sum = sum(self._signed_num(row.get("organPureBuyQuant", "0")) for row in trend)
        retail_sum = sum(self._signed_num(row.get("individualPureBuyQuant", "0")) for row in trend)
        return self.envelope(
            {
                "ticker": ticker,
                "supply_demand": {
                    "foreign": self._flow_label(foreign_sum),
                    "institution": self._flow_label(institution_sum),
                    "retail": self._flow_label(retail_sum),
                    "program": "unknown",
                    "foreign_5d_shares": foreign_sum,
                    "institution_5d_shares": institution_sum,
                    "retail_5d_shares": retail_sum,
                },
            },
            is_realtime=True,
            confidence=0.76,
        )

    def fetch_disclosures(self, ticker: str, since: str | None = None):
        return self.envelope(
            {
                "ticker": ticker,
                "disclosures": [],
                "note": "Naver public provider does not include DART disclosure feed.",
            },
            is_realtime=False,
            confidence=0.45,
        )

    def fetch_themes(self, ticker: str):
        integration = self._integration(ticker)
        peers = integration.get("industryCompareInfo", [])[:5]
        stock_name = integration.get("stockName", ticker)
        industry_code = integration.get("industryCode", "")
        themes = [
            {"name": self._infer_theme(stock_name, industry_code), "strength": 70, "stage": "expanding", "catalyst": "Naver industry/stock context"},
            {"name": "수급/시세", "strength": 62, "stage": "forming", "catalyst": "최근 가격·거래량"},
            {"name": "동종업종", "strength": 58, "stage": "forming", "catalyst": ", ".join(peer.get("stockName", "") for peer in peers[:3])},
        ]
        return self.envelope({"ticker": ticker, "themes": themes}, is_realtime=True, confidence=0.58)

    def _basic(self, ticker: str) -> dict[str, Any]:
        if ticker not in self._basic_cache:
            self._basic_cache[ticker] = self._json(f"https://m.stock.naver.com/api/stock/{ticker}/basic")
        return self._basic_cache[ticker]

    def _integration(self, ticker: str) -> dict[str, Any]:
        if ticker not in self._integration_cache:
            self._integration_cache[ticker] = self._json(f"https://m.stock.naver.com/api/stock/{ticker}/integration")
        return self._integration_cache[ticker]

    def _json(self, url: str) -> Any:
        request = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def _text(self, url: str) -> str:
        request = urllib.request.Request(url, headers={**self.headers, "Referer": "https://finance.naver.com/"})
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
        return raw.decode("euc-kr", errors="ignore")

    def _fetch_daily_ohlcv(self, symbol: str) -> list[dict[str, Any]]:
        today = now_kst().date()
        start = (today - timedelta(days=self.historical_days)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")
        url = (
            "https://api.finance.naver.com/siseJson.naver?"
            + urllib.parse.urlencode({"symbol": symbol, "requestType": 1, "startTime": start, "endTime": end, "timeframe": "day"})
        )
        text = self._text(url)
        rows = []
        pattern = re.compile(
            r'\["(?P<date>\d{8})",\s*(?P<open>[-0-9.]+),\s*(?P<high>[-0-9.]+),\s*(?P<low>[-0-9.]+),\s*(?P<close>[-0-9.]+),\s*(?P<volume>[-0-9.]+),'
        )
        for match in pattern.finditer(text):
            close = float(match.group("close"))
            volume = float(match.group("volume"))
            rows.append(
                {
                    "date": f"{match.group('date')[:4]}-{match.group('date')[4:6]}-{match.group('date')[6:]}",
                    "open": float(match.group("open")),
                    "high": float(match.group("high")),
                    "low": float(match.group("low")),
                    "close": close,
                    "volume": volume,
                    "turnover": close * volume,
                }
            )
        return rows

    def _fetch_market_sum_universe(self, sosoks: list[str], *, min_market_cap_eok: int) -> list[str]:
        tickers: list[str] = []
        seen: set[str] = set()
        for sosok in sosoks:
            for page in range(1, 80):
                rows = self._fetch_market_sum_page(sosok, page)
                if not rows:
                    break
                page_has_above_min = False
                for row in rows:
                    if row["market_cap_eok"] >= min_market_cap_eok:
                        page_has_above_min = True
                        if row["ticker"] not in seen and not self._is_non_common_stock(row["name"]):
                            tickers.append(row["ticker"])
                            seen.add(row["ticker"])
                if not page_has_above_min:
                    break
        return tickers

    def _fetch_market_sum_page(self, sosok: str, page: int) -> list[dict[str, Any]]:
        url = f"https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}"
        text = self._text(url)
        rows: list[dict[str, Any]] = []
        for match in re.finditer(r"<tr[^>]*>\s*<td class=\"no\">.*?</tr>", text, flags=re.S):
            row_html = match.group(0)
            item = re.search(r'/item/main\.naver\?code=(\d{6})" class="tltle">([^<]+)</a>', row_html)
            if not item:
                continue
            numbers = re.findall(r'<td class="number">([\d,.\-]+)</td>', row_html)
            if len(numbers) < 3:
                continue
            market_cap_eok = int(self._num(numbers[2]))
            rows.append({"ticker": item.group(1), "name": item.group(2), "market_cap_eok": market_cap_eok})
        return rows

    def _is_non_common_stock(self, name: str) -> bool:
        upper = name.upper()
        blocked_keywords = [
            "ETF",
            "ETN",
            "KODEX",
            "TIGER",
            "ACE ",
            "SOL ",
            "RISE ",
            "PLUS ",
            "KOSEF",
            "HANARO",
            "ARIRANG",
            "KBSTAR",
            "SMART",
            "TREX",
            "TIMEFOLIO",
            "스팩",
            "리츠",
        ]
        if any(keyword in upper for keyword in blocked_keywords):
            return True
        return name.endswith("우") or name.endswith("우B") or name.endswith("우C")

    def _total_infos(self, integration: dict[str, Any]) -> dict[str, str]:
        return {item.get("code"): item.get("value", "") for item in integration.get("totalInfos", [])}

    def _num(self, value: Any) -> float:
        if value is None:
            return 0.0
        text = str(value).replace(",", "").replace("+", "").strip()
        text = re.sub(r"[^0-9.\-]", "", text)
        return float(text) if text not in {"", "-", "."} else 0.0

    def _signed_num(self, value: Any) -> float:
        if value is None:
            return 0.0
        text = str(value).replace(",", "").strip()
        sign = -1 if text.startswith("-") else 1
        text = text.replace("+", "").replace("-", "")
        return sign * self._num(text)

    def _float(self, value: Any) -> float:
        return self._num(value)

    def _float_text(self, value: str) -> float:
        return self._num(value)

    def _parse_value_million_krw(self, value: str) -> float:
        if "백만" in value:
            return self._num(value) * 1_000_000
        return self._num(value)

    def _parse_korean_market_value(self, value: str) -> int | None:
        if not value:
            return None
        value = value.replace(",", "")
        total = 0
        jo = re.search(r"([0-9]+(?:\.[0-9]+)?)조", value)
        eok = re.search(r"([0-9]+(?:\.[0-9]+)?)억", value)
        if jo:
            total += int(float(jo.group(1)) * 1_000_000_000_000)
        if eok:
            total += int(float(eok.group(1)) * 100_000_000)
        if total:
            return total
        plain = self._num(value)
        return int(plain * 1_000_000) if plain else None

    def _flow_label(self, value: float) -> str:
        if value > 500_000:
            return "net_buy_strong"
        if value > 0:
            return "net_buy"
        if value < -500_000:
            return "net_sell_strong"
        if value < 0:
            return "net_sell"
        return "neutral"

    def _format_news_time(self, value: str) -> str:
        if len(value) >= 12:
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}T{value[8:10]}:{value[10:12]}:00+09:00"
        return now_kst().isoformat(timespec="seconds")

    def _infer_theme(self, stock_name: str, industry_code: str) -> str:
        name = stock_name.upper()
        if "하이닉스" in stock_name or "삼성전자" in stock_name or "반도체" in stock_name:
            return "반도체"
        if "LS" in name or "ELECTRIC" in name:
            return "전력기기"
        if "NAVER" in name:
            return "플랫폼/AI"
        if "에코프로" in stock_name:
            return "2차전지"
        if "LG전자" in stock_name:
            return "전장/가전"
        return industry_code or "업종 모멘텀"
