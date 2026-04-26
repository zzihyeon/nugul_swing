"""Parser for weekly Korean theme notes."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .models import DataSource, ThemeFollowSnapshot, ThemeSectorSnapshot

DATE_RE = re.compile(r"^(?P<date>\d{4})\.\s*(?P<month>\d{2})\.\s*(?P<day>\d{2})\s+(?P<body>.+)$")
LEADERS_RE = re.compile(r"주도주\s*[:：]\s*(?P<leaders>[^)]+)")
POSITIVE_WORDS = ("상승", "급등", "강세", "부각", "기대", "수혜", "추진", "계약", "호조", "확대")
NEGATIVE_WORDS = ("하락", "급락", "약세", "부담", "우려", "중단", "취소", "결렬", "불안")


@dataclass(frozen=True)
class ThemeEvent:
    event_date: date
    description: str
    leaders: tuple[str, ...] = ()


@dataclass
class ThemeSummary:
    name: str
    note: str = ""
    events: list[ThemeEvent] = field(default_factory=list)


def parse_theme_file(path: str | Path) -> list[ThemeSummary]:
    text = Path(path).read_text(encoding="utf-8-sig")
    return parse_theme_text(text)


def parse_theme_text(text: str) -> list[ThemeSummary]:
    themes: list[ThemeSummary] = []
    current: ThemeSummary | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = DATE_RE.match(line)
        if match and current:
            event_date = date(
                int(match.group("date")),
                int(match.group("month")),
                int(match.group("day")),
            )
            body = match.group("body").strip()
            current.events.append(
                ThemeEvent(
                    event_date=event_date,
                    description=body,
                    leaders=_extract_leaders(body),
                )
            )
            continue

        name, note = _split_heading(line)
        current = ThemeSummary(name=name, note=note)
        themes.append(current)

    return themes


def build_theme_snapshot(
    themes: list[ThemeSummary],
    stock_name: str,
    source_name: str = "theme_week",
    source_url: str | None = None,
    as_of: date | None = None,
) -> ThemeSectorSnapshot:
    as_of = as_of or date.today()
    matched_themes: list[str] = []
    recent_event_count = 0
    max_breadth = 0
    leading_stock = False

    for theme in themes:
        matched_events = [
            event for event in theme.events if _stock_in_event(stock_name, event)
        ]
        if not matched_events:
            continue
        matched_themes.append(theme.name)
        max_breadth = max(max_breadth, *(len(event.leaders) for event in matched_events))
        if any(_stock_matches(stock_name, leader) for event in matched_events for leader in event.leaders):
            leading_stock = True
        recent_event_count += sum(
            1 for event in matched_events if 0 <= (as_of - event.event_date).days <= 60
        )

    return ThemeSectorSnapshot(
        themes=matched_themes,
        leading_stock=leading_stock if matched_themes else None,
        sector_breadth=max_breadth or None,
        theme_persistence_days=recent_event_count if matched_themes else None,
        sources=[
            DataSource(
                name=source_name,
                url=source_url,
                retrieved_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                delay="user-supplied theme file",
            )
        ],
    )


def build_theme_snapshot_from_file(path: str | Path, stock_name: str) -> ThemeSectorSnapshot:
    path = Path(path)
    themes = parse_theme_file(path)
    return build_theme_snapshot(
        themes,
        stock_name=stock_name,
        source_name=path.name,
        source_url=str(path),
    )


def build_theme_follow_snapshot(
    themes: list[ThemeSummary],
    stock_name: str | None = None,
    target_theme: str | None = None,
    source_name: str = "theme_week",
    source_url: str | None = None,
    as_of: date | None = None,
    recent_days: int = 60,
) -> ThemeFollowSnapshot:
    as_of = as_of or date.today()
    selected = _select_theme(themes, stock_name, target_theme, as_of, recent_days)
    source = DataSource(
        name=source_name,
        url=source_url,
        retrieved_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        delay="user-supplied theme file",
    )
    if selected is None:
        return ThemeFollowSnapshot(sources=[source])

    events = sorted(selected.events, key=lambda event: event.event_date, reverse=True)
    latest = events[0] if events else None
    recent_events = [
        event
        for event in events
        if 0 <= (as_of - event.event_date).days <= recent_days
    ]
    leader_counts: Counter[str] = Counter()
    for event in recent_events:
        leader_counts.update(event.leaders)

    positive_count = sum(1 for event in recent_events if _event_polarity(event) > 0)
    negative_count = sum(1 for event in recent_events if _event_polarity(event) < 0)
    recurring_leaders = [
        name for name, count in leader_counts.most_common() if count >= 2
    ][:5]
    follow_candidates = list(dict.fromkeys(recurring_leaders + list(latest.leaders if latest else ())))[:8]

    return ThemeFollowSnapshot(
        target_theme=selected.name,
        latest_event_date=latest.event_date.isoformat() if latest else None,
        freshness_days=(as_of - latest.event_date).days if latest else None,
        recent_event_count=len(recent_events),
        positive_event_count=positive_count,
        negative_event_count=negative_count,
        latest_event=latest.description if latest else None,
        latest_leaders=list(latest.leaders if latest else ()),
        recurring_leaders=recurring_leaders,
        follow_candidates=follow_candidates,
        sources=[source],
    )


def build_theme_follow_snapshot_from_file(
    path: str | Path,
    stock_name: str | None = None,
    target_theme: str | None = None,
) -> ThemeFollowSnapshot:
    path = Path(path)
    themes = parse_theme_file(path)
    return build_theme_follow_snapshot(
        themes,
        stock_name=stock_name,
        target_theme=target_theme,
        source_name=path.name,
        source_url=str(path),
    )


def _split_heading(line: str) -> tuple[str, str]:
    line = line.removeprefix("NEW!").strip()
    if " - " in line:
        name, note = line.split(" - ", 1)
        return name.strip(), note.strip()
    return line, ""


def _extract_leaders(text: str) -> tuple[str, ...]:
    match = LEADERS_RE.search(text)
    if not match:
        return ()
    raw = match.group("leaders")
    items = re.split(r"[,/·]", raw)
    return tuple(item.strip() for item in items if item.strip())


def _stock_in_event(stock_name: str, event: ThemeEvent) -> bool:
    if stock_name in event.description:
        return True
    return any(_stock_matches(stock_name, leader) for leader in event.leaders)


def _stock_matches(stock_name: str, candidate: str) -> bool:
    stock = _normalize(stock_name)
    other = _normalize(candidate)
    return bool(stock and other and (stock in other or other in stock))


def _select_theme(
    themes: list[ThemeSummary],
    stock_name: str | None,
    target_theme: str | None,
    as_of: date,
    recent_days: int,
) -> ThemeSummary | None:
    if target_theme:
        target = _normalize(target_theme)
        matches = [theme for theme in themes if target in _normalize(theme.name)]
        if matches:
            return max(matches, key=lambda theme: _theme_rank(theme, as_of, recent_days))

    if stock_name:
        matches = [
            theme
            for theme in themes
            if any(_stock_in_event(stock_name, event) for event in theme.events)
        ]
        if matches:
            return max(matches, key=lambda theme: _theme_rank(theme, as_of, recent_days))

    if not themes:
        return None
    return max(themes, key=lambda theme: _theme_rank(theme, as_of, recent_days))


def _theme_rank(theme: ThemeSummary, as_of: date, recent_days: int) -> tuple[int, int, int]:
    recent_events = [
        event
        for event in theme.events
        if 0 <= (as_of - event.event_date).days <= recent_days
    ]
    latest_age = min(((as_of - event.event_date).days for event in theme.events), default=9999)
    positive_count = sum(1 for event in recent_events if _event_polarity(event) > 0)
    return (len(recent_events), positive_count, -latest_age)


def _event_polarity(event: ThemeEvent) -> int:
    text = event.description
    positive = any(word in text for word in POSITIVE_WORDS)
    negative = any(word in text for word in NEGATIVE_WORDS)
    if positive and not negative:
        return 1
    if negative and not positive:
        return -1
    if positive and negative:
        return 0
    return 0


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()
