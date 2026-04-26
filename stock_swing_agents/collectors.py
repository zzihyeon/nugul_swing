"""Market data collectors for Korean stock analysis."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from statistics import mean
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import (
    AnalysisInput,
    DataSource,
    ExecutionSnapshot,
    MarketDataSnapshot,
    RiskSnapshot,
    TechnicalSnapshot,
    YangEumYangSnapshot,
)


NAVER_REALTIME_URL = "https://polling.finance.naver.com/api/realtime?query={query}"
NAVER_DAILY_URL = "https://finance.naver.com/item/sise_day.naver?code={ticker}&page={page}"


@dataclass(frozen=True)
class RealtimeQuote:
    ticker: str
    name: str | None
    price: float | None
    change_pct: float | None
    open: float | None
    high: float | None
    low: float | None
    previous_close: float | None
    volume: int | None
    trading_value: float | None
    market_status: str | None
    retrieved_at: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class DailyCandle:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class CollectionError(RuntimeError):
    pass


class NaverFinanceCollector:
    provider_name = "Naver Finance"

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def fetch_realtime_quote(self, ticker: str) -> RealtimeQuote:
        ticker = normalize_ticker(ticker)
        query = f"SERVICE_ITEM:{ticker}|SERVICE_RECENT_ITEM:{ticker}"
        url = NAVER_REALTIME_URL.format(query=quote(query, safe=":|"))
        text = self._get_text(url, encoding="euc-kr")
        return parse_realtime_quote(text, ticker=ticker, retrieved_at=_now())

    def fetch_daily_candles(self, ticker: str, pages: int = 8) -> list[DailyCandle]:
        ticker = normalize_ticker(ticker)
        candles: dict[str, DailyCandle] = {}
        for page in range(1, pages + 1):
            url = NAVER_DAILY_URL.format(ticker=ticker, page=page)
            html = self._get_text(url, encoding="euc-kr")
            for candle in parse_daily_candles(html):
                candles[candle.date] = candle
        return [candles[key] for key in sorted(candles)]

    def build_analysis_input(
        self,
        ticker: str,
        stock_name: str | None = None,
        daily_pages: int = 8,
    ) -> AnalysisInput:
        quote_data = self.fetch_realtime_quote(ticker)
        candles = self.fetch_daily_candles(ticker, pages=daily_pages)
        if not candles:
            raise CollectionError(f"No daily candles collected for {ticker}")
        return build_analysis_input_from_market_data(
            ticker=normalize_ticker(ticker),
            stock_name=stock_name or quote_data.name or normalize_ticker(ticker),
            quote_data=quote_data,
            candles=candles,
        )

    def _get_text(self, url: str, encoding: str) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
                ),
                "Referer": "https://finance.naver.com/",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            raw = response.read()
        return raw.decode(encoding, errors="replace")


def normalize_ticker(ticker: str) -> str:
    digits = re.sub(r"\D", "", ticker)
    if not digits:
        raise ValueError("ticker must contain digits")
    return digits.zfill(6)


def parse_realtime_quote(
    text: str,
    ticker: str,
    retrieved_at: str | None = None,
) -> RealtimeQuote:
    data = json.loads(text)
    if data.get("resultCode") != "success":
        raise CollectionError(f"Naver realtime response failed: {data!r}")

    areas = data.get("result", {}).get("areas", [])
    row = None
    for area in areas:
        if area.get("name") == "SERVICE_ITEM" and area.get("datas"):
            row = area["datas"][0]
            break
    if row is None:
        for area in areas:
            if area.get("datas"):
                row = area["datas"][0]
                break
    if row is None:
        raise CollectionError("No realtime quote row found")

    return RealtimeQuote(
        ticker=ticker,
        name=row.get("nm"),
        price=_number(row.get("nv")),
        change_pct=_number(row.get("cr")),
        open=_number(row.get("ov")),
        high=_number(row.get("hv")),
        low=_number(row.get("lv")),
        previous_close=_number(row.get("pcv")),
        volume=_int(row.get("aq")),
        trading_value=_number(row.get("aa")),
        market_status=row.get("ms"),
        retrieved_at=retrieved_at or _now(),
        raw=row,
    )


def parse_daily_candles(html: str) -> list[DailyCandle]:
    rows = re.findall(
        r"<tr[^>]*onMouseOver=.*?</tr>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candles: list[DailyCandle] = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.IGNORECASE | re.DOTALL)
        values = [_clean_cell(cell) for cell in cells]
        if len(values) < 7 or not re.match(r"\d{4}\.\d{2}\.\d{2}", values[0]):
            continue
        try:
            candles.append(
                DailyCandle(
                    date=values[0],
                    close=_to_float(values[1]),
                    open=_to_float(values[3]),
                    high=_to_float(values[4]),
                    low=_to_float(values[5]),
                    volume=_to_int(values[6]),
                )
            )
        except ValueError:
            continue
    return candles


def build_analysis_input_from_market_data(
    ticker: str,
    stock_name: str,
    quote_data: RealtimeQuote,
    candles: list[DailyCandle],
) -> AnalysisInput:
    source = DataSource(
        name="Naver Finance",
        url=f"https://finance.naver.com/item/main.naver?code={ticker}",
        retrieved_at=quote_data.retrieved_at,
        delay="realtime quote + daily OHLCV page",
    )
    sorted_candles = sorted(candles, key=lambda candle: candle.date)
    latest = sorted_candles[-1]
    current_price = quote_data.price or latest.close
    current_volume = quote_data.volume or latest.volume
    avg_volume = _avg([c.volume for c in sorted_candles[-20:]])
    volume_ratio = current_volume / avg_volume if avg_volume else None

    technical = build_technical_snapshot(sorted_candles, current_price, source)
    yang_eum_yang = build_yang_eum_yang_snapshot(sorted_candles, source)
    risk = build_risk_snapshot(sorted_candles, technical)
    execution = build_execution_snapshot(current_price, technical)

    return AnalysisInput(
        stock_name=stock_name,
        ticker=ticker,
        market_data=MarketDataSnapshot(
            price=current_price,
            change_pct=quote_data.change_pct,
            volume_ratio=volume_ratio,
            sources=[source],
        ),
        technical=technical,
        risk=risk,
        execution=execution,
        yang_eum_yang=yang_eum_yang,
    )


def build_technical_snapshot(
    candles: list[DailyCandle],
    current_price: float,
    source: DataSource | None = None,
) -> TechnicalSnapshot:
    closes = [c.close for c in candles]
    ma5 = _ma(closes, 5)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    rsi = _rsi(closes, 14)
    macd_histogram = _macd_histogram(closes)
    support = min(c.low for c in candles[-10:]) if candles else None
    resistance = max(c.high for c in candles[-20:]) if candles else None

    if ma20 and current_price >= ma20 and (ma5 or 0) >= ma20:
        trend = "up"
    elif ma20 and current_price < ma20:
        trend = "down"
    else:
        trend = "neutral"

    return TechnicalSnapshot(
        trend=trend,
        close_above_ma20=current_price >= ma20 if ma20 else None,
        close_above_ma60=current_price >= ma60 if ma60 else None,
        rsi=rsi,
        macd_histogram=macd_histogram,
        support=support,
        resistance=resistance,
        stop_loss=support,
        sources=[source] if source else [],
    )


def build_yang_eum_yang_snapshot(
    candles: list[DailyCandle],
    source: DataSource | None = None,
) -> YangEumYangSnapshot:
    if len(candles) < 3:
        return YangEumYangSnapshot(sources=[source] if source else [])

    first, pullback, current = _select_yang_eum_yang_window(candles)
    first_index = candles.index(first)
    pullback_index = candles.index(pullback)
    current_index = candles.index(current)
    first_avg_volume = _avg([c.volume for c in candles[max(0, first_index - 20):first_index]])
    first_volume_ratio = first.volume / first_avg_volume if first_avg_volume else None
    ma5_pullback = _ma_at(candles, pullback_index, 5)
    ma5_current = _ma_at(candles, current_index, 5)
    pullback_volume_pct = (
        pullback.volume / first.volume * 100 if first.volume else None
    )
    short_ma_distance = (
        (current.close - ma5_current) / current.close * 100
        if ma5_current and current.close
        else None
    )

    completed_pattern = current is not pullback
    pattern = "pattern1"
    if completed_pattern and first.close > first.open and pullback.close < pullback.open:
        pattern = "pattern1"

    return YangEumYangSnapshot(
        pattern=pattern,
        first_candle_gain_pct=_pct(first.close, first.open),
        first_candle_has_upper_shadow=_has_long_upper_shadow(first),
        first_candle_volume_ratio=first_volume_ratio,
        pullback_is_bearish=pullback.close < pullback.open,
        pullback_holds_ma5=pullback.low >= ma5_pullback * 0.995 if ma5_pullback else None,
        pullback_volume_pct_of_first=pullback_volume_pct,
        short_ma_distance_pct=short_ma_distance,
        current_above_short_ma=current.close >= ma5_current if ma5_current else None,
        consecutive_volume_decline_days=_consecutive_volume_decline_days(candles),
        sideways_above_short_ma=_sideways_above_ma(candles, ma5_current),
        entry_near_previous_low=_near(current.close, pullback.low, 0.03),
        entry_near_short_ma=_near(current.close, ma5_current, 0.05) if ma5_current else None,
        opening_volume_spike=None,
        pullback_low_broken=current.low < pullback.low if completed_pattern else False,
        short_ma_broken=current.close < ma5_current if ma5_current else None,
        sources=[source] if source else [],
    )


def build_risk_snapshot(
    candles: list[DailyCandle],
    technical: TechnicalSnapshot,
) -> RiskSnapshot:
    recent = candles[-5:]
    ranges = [
        (c.high - c.low) / c.close * 100
        for c in recent
        if c.close and c.high >= c.low
    ]
    return RiskSnapshot(
        volatility_pct=_avg(ranges),
        gap_risk=False,
        trade_halt_risk=False,
        investment_warning=False,
        bad_disclosure_risk=False,
        max_position_pct=15,
        stop_loss=technical.stop_loss,
    )


def build_execution_snapshot(
    current_price: float,
    technical: TechnicalSnapshot,
) -> ExecutionSnapshot:
    support_distance = (
        (current_price - technical.support) / current_price * 100
        if technical.support and current_price
        else None
    )
    resistance_distance = (
        (technical.resistance - current_price) / current_price * 100
        if technical.resistance and current_price
        else None
    )
    return ExecutionSnapshot(
        price_vs_support_pct=support_distance,
        price_vs_resistance_pct=resistance_distance,
        pullback_ready=support_distance is not None and 0 <= support_distance <= 5,
        breakout_confirmed=(
            resistance_distance is not None and resistance_distance <= 0
        ),
        entry_mode="분할 진입" if support_distance is not None and support_distance <= 5 else "관망",
    )


def _select_yang_eum_yang_window(
    candles: list[DailyCandle],
) -> tuple[DailyCandle, DailyCandle, DailyCandle]:
    latest = candles[-1]
    previous = candles[-2]
    before_previous = candles[-3]
    if latest.close < latest.open and previous.close > previous.open:
        return previous, latest, latest
    if (
        latest.close > latest.open
        and previous.close < previous.open
        and before_previous.close > before_previous.open
    ):
        return before_previous, previous, latest
    return before_previous, previous, latest


def _clean_cell(cell: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", cell)
    return re.sub(r"\s+", " ", unescape(no_tags)).strip()


def _to_float(value: str) -> float:
    return float(re.sub(r"[^0-9.\-]", "", value))


def _to_int(value: str) -> int:
    return int(re.sub(r"[^0-9\-]", "", value))


def _number(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _avg(values: list[float | int]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return mean(clean) if clean else None


def _ma(values: list[float], days: int) -> float | None:
    if len(values) < days:
        return None
    return mean(values[-days:])


def _ma_at(candles: list[DailyCandle], index: int, days: int) -> float | None:
    if index + 1 < days:
        return None
    return mean(c.close for c in candles[index + 1 - days:index + 1])


def _pct(new: float, old: float) -> float | None:
    return (new - old) / old * 100 if old else None


def _near(value: float | None, target: float | None, threshold: float) -> bool | None:
    if value is None or target is None or value == 0:
        return None
    return abs(value - target) / value <= threshold


def _has_long_upper_shadow(candle: DailyCandle) -> bool:
    if candle.close <= candle.open:
        return False
    body = abs(candle.close - candle.open)
    upper_shadow = candle.high - max(candle.open, candle.close)
    return body > 0 and upper_shadow / body >= 0.35


def _consecutive_volume_decline_days(candles: list[DailyCandle]) -> int:
    count = 0
    for idx in range(len(candles) - 1, 0, -1):
        if candles[idx].volume < candles[idx - 1].volume:
            count += 1
        else:
            break
    return count


def _sideways_above_ma(
    candles: list[DailyCandle],
    ma_value: float | None,
) -> bool | None:
    if ma_value is None or len(candles) < 3:
        return None
    recent = candles[-3:]
    range_pct = (max(c.high for c in recent) - min(c.low for c in recent)) / recent[-1].close
    return min(c.low for c in recent) >= ma_value * 0.98 and range_pct <= 0.12


def _macd_histogram(closes: list[float]) -> float | None:
    if len(closes) < 35:
        return None
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
    signal = _ema_series(macd, 9)
    if not signal:
        return None
    return round(macd[-1] - signal[-1], 4)


def _ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    ema = [values[0]]
    for value in values[1:]:
        ema.append((value - ema[-1]) * multiplier + ema[-1])
    return ema


def _rsi(closes: list[float], period: int) -> float | None:
    if len(closes) <= period:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for prev, curr in zip(closes[-period - 1:-1], closes[-period:]):
        diff = curr - prev
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

