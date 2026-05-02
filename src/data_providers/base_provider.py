from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

from src.models.schemas import ProviderEnvelope
from src.utils.market_time import iso_kst, now_kst


class BaseProvider:
    source = "base"

    def envelope(
        self,
        data: dict[str, Any] | list[Any],
        *,
        is_realtime: bool = False,
        is_stale: bool = False,
        confidence: float = 1.0,
    ) -> ProviderEnvelope:
        return ProviderEnvelope(
            source=self.source,
            fetched_at_kst=iso_kst(),
            is_realtime=is_realtime,
            is_stale=is_stale,
            data={"items": data} if isinstance(data, list) else data,
            confidence=confidence,
        )

    def fetch_ohlcv(self, ticker: str, start: str | None = None, end: str | None = None) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_intraday(self, ticker: str) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_latest_price(self, ticker: str) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_market_cap(self, ticker: str) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_market_index(self, index_name: str) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_news(self, ticker: str, since: str | None = None) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_financials(self, ticker: str) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_supply_demand(self, ticker: str) -> ProviderEnvelope:
        raise NotImplementedError

    def fetch_disclosures(self, ticker: str, since: str | None = None) -> ProviderEnvelope:
        raise NotImplementedError


class MockDataStore:
    """Deterministic in-memory market data for end-to-end local execution."""

    def __init__(self) -> None:
        self._profiles = self._build_profiles()
        self._ohlcv_cache: dict[str, list[dict[str, Any]]] = {}
        self._index_cache: dict[str, list[dict[str, Any]]] = {}

    def tickers_for_universe(self, universe: str) -> list[str]:
        if universe == "kosdaq150":
            return ["247540", "042700", "123456", "999999"]
        if universe == "kospi200":
            return ["005930", "000660", "010120", "035420", "066570"]
        return ["000660", "010120", "042700", "247540", "005930", "035420", "066570", "123456", "999999"]

    def profile(self, ticker: str) -> dict[str, Any]:
        if ticker not in self._profiles:
            return self._unknown_profile(ticker)
        return self._profiles[ticker]

    def ohlcv(self, ticker: str) -> list[dict[str, Any]]:
        if ticker not in self._ohlcv_cache:
            self._ohlcv_cache[ticker] = self._generate_ohlcv(self.profile(ticker))
        return deepcopy(self._ohlcv_cache[ticker])

    def index_ohlcv(self, index_name: str) -> list[dict[str, Any]]:
        index_name = index_name.upper()
        if index_name not in self._index_cache:
            base = 2600 if "KOSPI" in index_name else 900
            drift = 0.0005 if "KOSPI" in index_name else 0.0002
            profile = {
                "ticker": index_name,
                "name": index_name,
                "base_price": base,
                "base_volume": 900_000,
                "drift": drift,
                "cycle": 0.001,
                "pattern": "none",
            }
            self._index_cache[index_name] = self._generate_ohlcv(profile)
        return deepcopy(self._index_cache[index_name])

    def latest_price(self, ticker: str) -> dict[str, Any]:
        rows = self.ohlcv(ticker)
        last = rows[-1]
        return {
            "ticker": ticker,
            "name": self.profile(ticker)["name"],
            "latest_price": last["close"],
            "close": last["close"],
            "daily_volume": last["volume"],
            "daily_turnover": last["turnover"],
            "change_pct": round((last["close"] / rows[-2]["close"] - 1.0) * 100.0, 2),
        }

    def intraday(self, ticker: str) -> dict[str, Any]:
        latest = self.latest_price(ticker)
        price = float(latest["latest_price"])
        base_volume = max(1, int(latest["daily_volume"] / 30))
        bars = []
        for idx, offset in enumerate([-0.006, -0.002, 0.001, 0.003, 0.0]):
            bar_price = round(price * (1 + offset), 2)
            bars.append(
                {
                    "time": f"{9 + idx:02d}:30",
                    "price": bar_price,
                    "volume": base_volume + idx * int(base_volume * 0.15),
                }
            )
        vwap = sum(row["price"] * row["volume"] for row in bars) / sum(row["volume"] for row in bars)
        return {
            "ticker": ticker,
            "latest_price": price,
            "intraday_volume": sum(row["volume"] for row in bars),
            "intraday_turnover": round(sum(row["price"] * row["volume"] for row in bars), 0),
            "vwap": round(vwap, 2),
            "bars": bars,
        }

    def market_cap(self, ticker: str) -> dict[str, Any]:
        profile = self.profile(ticker)
        return {
            "ticker": ticker,
            "name": profile["name"],
            "market_cap_krw": profile.get("market_cap_krw"),
            "listing_market": profile.get("listing_market", "KOSPI"),
            "status_flags": deepcopy(profile.get("status_flags", [])),
        }

    def news(self, ticker: str) -> list[dict[str, Any]]:
        profile = self.profile(ticker)
        current = now_kst()
        return [
            {
                "headline": headline,
                "published_at_kst": iso_kst(current - timedelta(hours=idx + 1)),
                "source": "mock_news",
                "url": "",
            }
            for idx, headline in enumerate(profile.get("news", []))
        ]

    def financials(self, ticker: str) -> dict[str, Any]:
        return deepcopy(self.profile(ticker).get("financials", {}))

    def supply_demand(self, ticker: str) -> dict[str, Any]:
        return deepcopy(self.profile(ticker).get("supply_demand", {}))

    def disclosures(self, ticker: str) -> list[dict[str, Any]]:
        profile = self.profile(ticker)
        current = now_kst()
        return [
            {
                "title": title,
                "published_at_kst": iso_kst(current - timedelta(days=idx + 1)),
                "severity": severity,
                "source": "mock_disclosure",
            }
            for idx, (title, severity) in enumerate(profile.get("disclosures", []))
        ]

    def themes(self, ticker: str) -> list[dict[str, Any]]:
        return deepcopy(self.profile(ticker).get("themes", []))

    def _build_profiles(self) -> dict[str, dict[str, Any]]:
        return {
            "000660": {
                "ticker": "000660",
                "name": "SK하이닉스",
                "listing_market": "KOSPI",
                "market_cap_krw": 145_000_000_000_000,
                "base_price": 180_000,
                "base_volume": 2_500_000,
                "drift": 0.0036,
                "cycle": 0.003,
                "pattern": "none",
                "themes": [
                    {"name": "HBM", "strength": 94, "stage": "expanding", "catalyst": "AI 메모리 수요"},
                    {"name": "반도체", "strength": 91, "stage": "expanding", "catalyst": "업황 개선"},
                    {"name": "AI 인프라", "strength": 88, "stage": "expanding", "catalyst": "데이터센터 투자"},
                ],
                "news": ["AI 서버향 HBM 수요 증가 기대", "메모리 가격 반등 전망"],
                "financials": {"debt_ratio": 58, "operating_margin": 23, "cashflow": "positive", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "net_buy_strong", "institution": "net_buy", "retail": "net_sell", "program": "net_buy"},
                "disclosures": [],
                "status_flags": [],
            },
            "010120": {
                "ticker": "010120",
                "name": "LS ELECTRIC",
                "listing_market": "KOSPI",
                "market_cap_krw": 7_200_000_000_000,
                "base_price": 125_000,
                "base_volume": 850_000,
                "drift": 0.0026,
                "cycle": 0.004,
                "pattern": "pattern_1",
                "themes": [
                    {"name": "전력기기", "strength": 92, "stage": "expanding", "catalyst": "전력망 투자"},
                    {"name": "변압기", "strength": 86, "stage": "expanding", "catalyst": "북미 인프라 수주"},
                    {"name": "AI 전력", "strength": 82, "stage": "early", "catalyst": "데이터센터 전력 수요"},
                ],
                "news": ["북미 전력망 투자 수혜 기대", "전력기기 수주잔고 증가"],
                "financials": {"debt_ratio": 72, "operating_margin": 11, "cashflow": "positive", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "net_buy", "institution": "net_buy_strong", "retail": "net_sell", "program": "neutral"},
                "disclosures": [],
                "status_flags": [],
            },
            "042700": {
                "ticker": "042700",
                "name": "한미반도체",
                "listing_market": "KOSPI",
                "market_cap_krw": 14_000_000_000_000,
                "base_price": 135_000,
                "base_volume": 1_900_000,
                "drift": 0.0029,
                "cycle": 0.006,
                "pattern": "pattern_2",
                "themes": [
                    {"name": "HBM 장비", "strength": 95, "stage": "crowded", "catalyst": "TC 본더 수요"},
                    {"name": "반도체 장비", "strength": 90, "stage": "expanding", "catalyst": "설비투자 확대"},
                    {"name": "AI 반도체", "strength": 84, "stage": "expanding", "catalyst": "패키징 병목"},
                ],
                "news": ["HBM 장비 수주 기대감 지속", "반도체 장비주 강세"],
                "financials": {"debt_ratio": 24, "operating_margin": 34, "cashflow": "positive", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "net_buy", "institution": "neutral", "retail": "net_sell", "program": "net_buy"},
                "disclosures": [],
                "status_flags": [],
            },
            "247540": {
                "ticker": "247540",
                "name": "에코프로비엠",
                "listing_market": "KOSDAQ",
                "market_cap_krw": 11_500_000_000_000,
                "base_price": 210_000,
                "base_volume": 950_000,
                "drift": 0.0018,
                "cycle": 0.005,
                "pattern": "pattern_3",
                "themes": [
                    {"name": "2차전지", "strength": 78, "stage": "forming", "catalyst": "소재 반등"},
                    {"name": "양극재", "strength": 75, "stage": "forming", "catalyst": "가격 안정"},
                    {"name": "전기차", "strength": 69, "stage": "early", "catalyst": "정책 기대"},
                ],
                "news": ["2차전지 소재주 반등 시도", "양극재 판가 안정 기대"],
                "financials": {"debt_ratio": 96, "operating_margin": 7, "cashflow": "normal", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "neutral", "institution": "net_buy", "retail": "net_sell", "program": "neutral"},
                "disclosures": [],
                "status_flags": [],
            },
            "005930": {
                "ticker": "005930",
                "name": "삼성전자",
                "listing_market": "KOSPI",
                "market_cap_krw": 460_000_000_000_000,
                "base_price": 78_000,
                "base_volume": 12_000_000,
                "drift": 0.0012,
                "cycle": 0.002,
                "pattern": "none",
                "themes": [
                    {"name": "메모리", "strength": 76, "stage": "expanding", "catalyst": "가격 반등"},
                    {"name": "파운드리", "strength": 63, "stage": "forming", "catalyst": "수율 개선"},
                    {"name": "AI 반도체", "strength": 70, "stage": "expanding", "catalyst": "고대역 메모리"},
                ],
                "news": ["메모리 업황 개선 기대", "외국인 대형주 순매수"],
                "financials": {"debt_ratio": 27, "operating_margin": 14, "cashflow": "positive", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "net_buy", "institution": "neutral", "retail": "net_sell", "program": "net_buy"},
                "disclosures": [],
                "status_flags": [],
            },
            "035420": {
                "ticker": "035420",
                "name": "NAVER",
                "listing_market": "KOSPI",
                "market_cap_krw": 32_000_000_000_000,
                "base_price": 195_000,
                "base_volume": 550_000,
                "drift": -0.0001,
                "cycle": 0.002,
                "pattern": "none",
                "themes": [
                    {"name": "AI검색", "strength": 67, "stage": "forming", "catalyst": "검색 개편"},
                    {"name": "플랫폼", "strength": 61, "stage": "forming", "catalyst": "광고 회복"},
                    {"name": "커머스", "strength": 58, "stage": "early", "catalyst": "수수료 개선"},
                ],
                "news": ["AI 검색 서비스 개편", "광고 경기 회복 기대"],
                "financials": {"debt_ratio": 42, "operating_margin": 16, "cashflow": "positive", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "neutral", "institution": "net_sell", "retail": "net_buy", "program": "neutral"},
                "disclosures": [],
                "status_flags": [],
            },
            "066570": {
                "ticker": "066570",
                "name": "LG전자",
                "listing_market": "KOSPI",
                "market_cap_krw": 18_000_000_000_000,
                "base_price": 105_000,
                "base_volume": 780_000,
                "drift": 0.0005,
                "cycle": 0.002,
                "pattern": "none",
                "themes": [
                    {"name": "전장", "strength": 64, "stage": "forming", "catalyst": "차량용 부품"},
                    {"name": "가전", "strength": 55, "stage": "mature", "catalyst": "수익성 개선"},
                    {"name": "로봇", "strength": 52, "stage": "early", "catalyst": "신사업"},
                ],
                "news": ["전장 사업 수익성 개선 기대"],
                "financials": {"debt_ratio": 81, "operating_margin": 5, "cashflow": "positive", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "net_sell", "institution": "neutral", "retail": "net_buy", "program": "neutral"},
                "disclosures": [],
                "status_flags": [],
            },
            "123456": {
                "ticker": "123456",
                "name": "리스크테크",
                "listing_market": "KOSDAQ",
                "market_cap_krw": 650_000_000_000,
                "base_price": 9_500,
                "base_volume": 80_000,
                "drift": 0.004,
                "cycle": 0.01,
                "pattern": "none",
                "themes": [
                    {"name": "테마성 재료", "strength": 71, "stage": "crowded", "catalyst": "단기 급등"},
                    {"name": "바이오", "strength": 45, "stage": "uncertain", "catalyst": "불확실"},
                    {"name": "정책", "strength": 44, "stage": "uncertain", "catalyst": "루머"},
                ],
                "news": ["투자경고 지정 이후 변동성 확대"],
                "financials": {"debt_ratio": 220, "operating_margin": -18, "cashflow": "negative", "audit_opinion": "emphasis"},
                "supply_demand": {"foreign": "net_sell", "institution": "net_sell", "retail": "net_buy", "program": "neutral"},
                "disclosures": [("대규모 유상증자 결정", "high")],
                "status_flags": ["investment_warning"],
            },
            "999999": {
                "ticker": "999999",
                "name": "소형테스트",
                "listing_market": "KOSDAQ",
                "market_cap_krw": 120_000_000_000,
                "base_price": 4_200,
                "base_volume": 40_000,
                "drift": 0.005,
                "cycle": 0.008,
                "pattern": "none",
                "themes": [
                    {"name": "테스트", "strength": 40, "stage": "unknown", "catalyst": "mock"},
                    {"name": "소형주", "strength": 35, "stage": "unknown", "catalyst": "mock"},
                    {"name": "유동성", "strength": 30, "stage": "unknown", "catalyst": "mock"},
                ],
                "news": ["소형주 단기 급등"],
                "financials": {"debt_ratio": 180, "operating_margin": -5, "cashflow": "negative", "audit_opinion": "clean"},
                "supply_demand": {"foreign": "neutral", "institution": "neutral", "retail": "net_buy", "program": "neutral"},
                "disclosures": [],
                "status_flags": [],
            },
        }

    def _unknown_profile(self, ticker: str) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "name": f"UNKNOWN-{ticker}",
            "listing_market": "KOSPI",
            "market_cap_krw": None,
            "base_price": 10_000,
            "base_volume": 10_000,
            "drift": 0.0,
            "cycle": 0.001,
            "pattern": "none",
            "themes": [],
            "news": [],
            "financials": {"audit_opinion": "unknown"},
            "supply_demand": {"foreign": "unknown", "institution": "unknown", "retail": "unknown", "program": "unknown"},
            "disclosures": [],
            "status_flags": [],
        }

    def _generate_ohlcv(self, profile: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        price = float(profile.get("base_price", 10_000))
        start_date = date.today() - timedelta(days=90)
        current_date = start_date
        day_count = 0
        while len(rows) < 70:
            current_date += timedelta(days=1)
            if current_date.weekday() >= 5:
                continue
            cycle = float(profile.get("cycle", 0.002))
            drift = float(profile.get("drift", 0.0))
            wave = ((day_count % 7) - 3) * cycle
            ret = drift + wave
            open_price = price * (1 + ret * 0.25)
            close = price * (1 + ret)
            high = max(open_price, close) * (1 + 0.012 + abs(wave))
            low = min(open_price, close) * (1 - 0.010 - abs(wave) / 2)
            volume = int(float(profile.get("base_volume", 100_000)) * (1 + (day_count % 5) * 0.08 + max(ret, 0) * 8))
            rows.append(self._row(current_date, open_price, high, low, close, volume))
            price = close
            day_count += 1

        pattern = profile.get("pattern")
        if pattern == "pattern_1":
            self._inject_pattern_1(rows, float(profile["base_price"]), int(profile["base_volume"]))
        elif pattern == "pattern_2":
            self._inject_pattern_2(rows, float(profile["base_price"]), int(profile["base_volume"]))
        elif pattern == "pattern_3":
            self._inject_pattern_3(rows, float(profile["base_price"]), int(profile["base_volume"]))
        return rows

    def _row(self, day: date, open_price: float, high: float, low: float, close: float, volume: int) -> dict[str, Any]:
        turnover = close * volume
        return {
            "date": day.isoformat(),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": int(volume),
            "turnover": round(turnover, 0),
        }

    def _replace(self, rows: list[dict[str, Any]], index: int, open_mul: float, high_mul: float, low_mul: float, close_mul: float, volume: int, base: float) -> None:
        day = date.fromisoformat(rows[index]["date"])
        rows[index] = self._row(day, base * open_mul, base * high_mul, base * low_mul, base * close_mul, volume)

    def _inject_pattern_1(self, rows: list[dict[str, Any]], base: float, base_volume: int) -> None:
        for offset, close_mul in zip([-6, -5, -4, -3], [1.00, 1.01, 1.02, 1.03], strict=True):
            self._replace(rows, offset, close_mul * 0.995, close_mul * 1.015, close_mul * 0.985, close_mul, base_volume, base)
        self._replace(rows, -2, 1.02, 1.135, 1.005, 1.12, base_volume * 4, base)
        self._replace(rows, -1, 1.12, 1.125, 1.075, 1.09, int(base_volume * 2.2), base)

    def _inject_pattern_2(self, rows: list[dict[str, Any]], base: float, base_volume: int) -> None:
        for offset, close_mul in zip([-7, -6, -5, -4, -3], [1.00, 1.01, 1.02, 1.025, 1.03], strict=True):
            self._replace(rows, offset, close_mul * 0.995, close_mul * 1.012, close_mul * 0.985, close_mul, base_volume, base)
        self._replace(rows, -2, 1.03, 1.24, 1.01, 1.095, base_volume * 4, base)
        self._replace(rows, -1, 1.065, 1.078, 1.045, 1.05, int(base_volume * 1.7), base)

    def _inject_pattern_3(self, rows: list[dict[str, Any]], base: float, base_volume: int) -> None:
        self._replace(rows, -8, 1.00, 1.105, 0.992, 1.085, base_volume * 4, base)
        volumes = [int(base_volume * ratio) for ratio in [2.8, 2.4, 2.0, 1.7, 1.4, 1.1, 0.95]]
        closes_mul = [1.09, 1.082, 1.087, 1.078, 1.084, 1.081, 1.088]
        for offset, close_mul, volume in zip(range(-7, 0), closes_mul, volumes, strict=True):
            self._replace(rows, offset, close_mul * 0.998, close_mul * 1.012, close_mul * 0.988, close_mul, volume, base)


MOCK_DATA_STORE = MockDataStore()
