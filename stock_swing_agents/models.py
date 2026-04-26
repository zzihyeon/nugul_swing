"""Shared data models for the swing-trading agent system."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any


class Signal(str, Enum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    BLOCK = "block"


class Decision(str, Enum):
    ENTRY = "진입 가능"
    WAIT = "대기"
    OBSERVE = "관망"
    FORBIDDEN = "금지"


@dataclass(frozen=True)
class DataSource:
    name: str
    url: str | None = None
    retrieved_at: str | None = None
    delay: str | None = None


@dataclass
class MarketDataSnapshot:
    price: float | None = None
    change_pct: float | None = None
    volume_ratio: float | None = None
    trading_value_rank: int | None = None
    kospi_change_pct: float | None = None
    kosdaq_change_pct: float | None = None
    usdkrw_change_pct: float | None = None
    futures_change_pct: float | None = None
    rate_change_bp: float | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class TechnicalSnapshot:
    trend: str | None = None
    close_above_ma20: bool | None = None
    close_above_ma60: bool | None = None
    rsi: float | None = None
    macd_histogram: float | None = None
    bollinger_position: str | None = None
    support: float | None = None
    resistance: float | None = None
    stop_loss: float | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class SupplyDemandSnapshot:
    foreign_net_buy_krw: float | None = None
    institution_net_buy_krw: float | None = None
    individual_net_buy_krw: float | None = None
    program_net_buy_krw: float | None = None
    consecutive_foreign_buy_days: int | None = None
    consecutive_institution_buy_days: int | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class NewsDisclosureSnapshot:
    positive_events: list[str] = field(default_factory=list)
    negative_events: list[str] = field(default_factory=list)
    high_impact_events: list[str] = field(default_factory=list)
    dart_warnings: list[str] = field(default_factory=list)
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class ThemeSectorSnapshot:
    themes: list[str] = field(default_factory=list)
    leading_stock: bool | None = None
    sector_breadth: int | None = None
    theme_persistence_days: int | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class ThemeFollowSnapshot:
    target_theme: str | None = None
    latest_event_date: str | None = None
    freshness_days: int | None = None
    recent_event_count: int | None = None
    positive_event_count: int | None = None
    negative_event_count: int | None = None
    latest_event: str | None = None
    latest_leaders: list[str] = field(default_factory=list)
    recurring_leaders: list[str] = field(default_factory=list)
    follow_candidates: list[str] = field(default_factory=list)
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class YangEumYangSnapshot:
    pattern: str | None = None
    first_candle_gain_pct: float | None = None
    first_candle_has_upper_shadow: bool | None = None
    first_candle_volume_ratio: float | None = None
    pullback_is_bearish: bool | None = None
    pullback_holds_ma5: bool | None = None
    pullback_volume_pct_of_first: float | None = None
    short_ma_distance_pct: float | None = None
    current_above_short_ma: bool | None = None
    consecutive_volume_decline_days: int | None = None
    sideways_above_short_ma: bool | None = None
    entry_near_previous_low: bool | None = None
    entry_near_short_ma: bool | None = None
    has_theme_or_momentum: bool | None = None
    opening_volume_spike: bool | None = None
    pullback_low_broken: bool | None = None
    short_ma_broken: bool | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class RiskSnapshot:
    volatility_pct: float | None = None
    gap_risk: bool | None = None
    trade_halt_risk: bool | None = None
    investment_warning: bool | None = None
    bad_disclosure_risk: bool | None = None
    max_position_pct: float | None = None
    stop_loss: float | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class ExecutionSnapshot:
    price_vs_support_pct: float | None = None
    price_vs_resistance_pct: float | None = None
    pullback_ready: bool | None = None
    breakout_confirmed: bool | None = None
    entry_mode: str | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class PostTradeSnapshot:
    journal: list[str] = field(default_factory=list)
    last_rule_breach: bool | None = None
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class AnalysisInput:
    stock_name: str
    ticker: str | None = None
    market: str = "KR"
    time_horizon: str = "스윙"
    market_data: MarketDataSnapshot = field(default_factory=MarketDataSnapshot)
    technical: TechnicalSnapshot = field(default_factory=TechnicalSnapshot)
    supply_demand: SupplyDemandSnapshot = field(default_factory=SupplyDemandSnapshot)
    news_disclosure: NewsDisclosureSnapshot = field(default_factory=NewsDisclosureSnapshot)
    theme_sector: ThemeSectorSnapshot = field(default_factory=ThemeSectorSnapshot)
    theme_follow: ThemeFollowSnapshot = field(default_factory=ThemeFollowSnapshot)
    yang_eum_yang: YangEumYangSnapshot = field(default_factory=YangEumYangSnapshot)
    risk: RiskSnapshot = field(default_factory=RiskSnapshot)
    execution: ExecutionSnapshot = field(default_factory=ExecutionSnapshot)
    post_trade: PostTradeSnapshot = field(default_factory=PostTradeSnapshot)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnalysisInput":
        return cls(
            stock_name=data["stock_name"],
            ticker=data.get("ticker"),
            market=data.get("market", "KR"),
            time_horizon=data.get("time_horizon", "스윙"),
            market_data=_dataclass_from_dict(
                MarketDataSnapshot, data.get("market_data", {})
            ),
            technical=_dataclass_from_dict(
                TechnicalSnapshot, data.get("technical", {})
            ),
            supply_demand=_dataclass_from_dict(
                SupplyDemandSnapshot, data.get("supply_demand", {})
            ),
            news_disclosure=_dataclass_from_dict(
                NewsDisclosureSnapshot, data.get("news_disclosure", {})
            ),
            theme_sector=_dataclass_from_dict(
                ThemeSectorSnapshot, data.get("theme_sector", {})
            ),
            theme_follow=_dataclass_from_dict(
                ThemeFollowSnapshot, data.get("theme_follow", {})
            ),
            yang_eum_yang=_dataclass_from_dict(
                YangEumYangSnapshot, data.get("yang_eum_yang", {})
            ),
            risk=_dataclass_from_dict(RiskSnapshot, data.get("risk", {})),
            execution=_dataclass_from_dict(
                ExecutionSnapshot, data.get("execution", {})
            ),
            post_trade=_dataclass_from_dict(
                PostTradeSnapshot, data.get("post_trade", {})
            ),
        )


@dataclass(frozen=True)
class AgentVote:
    agent: str
    signal: Signal
    score: int
    confidence: int
    evidence: tuple[str, ...]
    risk: tuple[str, ...]

    def __post_init__(self) -> None:
        signal = self.signal if isinstance(self.signal, Signal) else Signal(self.signal)
        object.__setattr__(self, "signal", signal)
        object.__setattr__(self, "score", max(-2, min(2, int(self.score))))
        object.__setattr__(self, "confidence", max(0, min(100, int(self.confidence))))
        object.__setattr__(self, "evidence", _compact_tuple(self.evidence, 3))
        object.__setattr__(self, "risk", _compact_tuple(self.risk, 2))


@dataclass(frozen=True)
class TradeDecision:
    decision: Decision
    reason: tuple[str, ...]
    counter_reason: tuple[str, ...]
    stop_loss: str
    time_horizon: str
    score_total: float
    risk_veto: bool
    votes: tuple[AgentVote, ...]
    sources: tuple[DataSource, ...] = ()


def to_plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return {key: to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain(item) for item in value]
    return value


def collect_sources(context: AnalysisInput) -> tuple[DataSource, ...]:
    found: list[DataSource] = []
    seen: set[tuple[str, str | None, str | None, str | None]] = set()
    for snapshot in (
        context.market_data,
        context.technical,
        context.supply_demand,
        context.news_disclosure,
        context.theme_sector,
        context.theme_follow,
        context.yang_eum_yang,
        context.risk,
        context.execution,
        context.post_trade,
    ):
        for source in snapshot.sources:
            key = (source.name, source.url, source.retrieved_at, source.delay)
            if key not in seen:
                found.append(source)
                seen.add(key)
    return tuple(found)


def _dataclass_from_dict(model: type[Any], data: dict[str, Any]) -> Any:
    allowed = {item.name for item in fields(model)}
    kwargs = {key: value for key, value in data.items() if key in allowed}
    if "sources" in allowed:
        kwargs["sources"] = [_source_from_dict(item) for item in data.get("sources", [])]
    return model(**kwargs)


def _source_from_dict(item: Any) -> DataSource:
    if isinstance(item, DataSource):
        return item
    if isinstance(item, dict):
        return DataSource(
            name=str(item.get("name", "unknown")),
            url=item.get("url"),
            retrieved_at=item.get("retrieved_at"),
            delay=item.get("delay"),
        )
    return DataSource(name=str(item))


def _compact_tuple(values: Any, limit: int) -> tuple[str, ...]:
    if values is None:
        items: list[str] = []
    elif isinstance(values, str):
        items = [values]
    else:
        items = [str(item) for item in values if str(item).strip()]
    if not items:
        items = ["충분한 데이터 없음"]
    return tuple(items[:limit])
