from __future__ import annotations

from datetime import datetime, time, timedelta, timezone


KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(tz=KST)


def iso_kst(dt: datetime | None = None) -> str:
    dt = dt or now_kst()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt.astimezone(KST).isoformat(timespec="seconds")


def parse_kst(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST)


def is_market_open_kst(dt: datetime | None = None) -> bool:
    dt = (dt or now_kst()).astimezone(KST)
    if dt.weekday() >= 5:
        return False
    return time(9, 0) <= dt.time() <= time(15, 30)


def stale_cutoff_delta(config: dict, market_open: bool) -> timedelta:
    if market_open:
        return timedelta(minutes=int(config.get("market_open_stale_minutes", 15)))
    return timedelta(hours=int(config.get("market_closed_stale_hours", 24)))
