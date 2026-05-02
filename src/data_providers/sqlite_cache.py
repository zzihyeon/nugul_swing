from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.utils.market_time import KST, iso_kst, now_kst, parse_kst


class SQLiteCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    fetched_at_kst TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_entries_category ON cache_entries(category)"
            )
            connection.commit()
        finally:
            connection.close()

    def set(self, cache_key: str, category: str, payload: Any, *, fetched_at_kst: str | None = None) -> None:
        fetched_at = fetched_at_kst or iso_kst()
        payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO cache_entries(cache_key, category, fetched_at_kst, payload_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    category = excluded.category,
                    fetched_at_kst = excluded.fetched_at_kst,
                    payload_json = excluded.payload_json
                """,
                (cache_key, category, fetched_at, payload_json),
            )
            connection.commit()
        finally:
            connection.close()

    def get(
        self,
        cache_key: str,
        *,
        max_age_seconds: int | None = None,
        allow_stale: bool = False,
        current_time: datetime | None = None,
    ) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT fetched_at_kst, payload_json FROM cache_entries WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            return None
        fetched_at = parse_kst(row["fetched_at_kst"])
        current = (current_time or now_kst()).astimezone(KST)
        is_stale = False
        if max_age_seconds is not None:
            is_stale = current - fetched_at > timedelta(seconds=max_age_seconds)
            if is_stale and not allow_stale:
                return None
        return {
            "payload": json.loads(row["payload_json"]),
            "fetched_at_kst": row["fetched_at_kst"],
            "is_stale": is_stale,
        }

    def set_universe(self, provider: str, universe: str, tickers: list[str]) -> None:
        self.set(self._universe_key(provider, universe), "universe", {"tickers": tickers})

    def get_universe(
        self,
        provider: str,
        universe: str,
        *,
        max_age_seconds: int | None = None,
        allow_stale: bool = False,
    ) -> list[str] | None:
        entry = self.get(
            self._universe_key(provider, universe),
            max_age_seconds=max_age_seconds,
            allow_stale=allow_stale,
        )
        if entry is None:
            return None
        return list(entry["payload"].get("tickers", []))

    def set_context(self, provider: str, ticker: str, context: dict[str, Any]) -> None:
        self.set(self._context_key(provider, ticker), "ticker_context", context)

    def get_context(
        self,
        provider: str,
        ticker: str,
        *,
        max_age_seconds: int | None = None,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        entry = self.get(
            self._context_key(provider, ticker),
            max_age_seconds=max_age_seconds,
            allow_stale=allow_stale,
        )
        if entry is None:
            return None
        context = dict(entry["payload"])
        context["cache_fetched_at_kst"] = entry["fetched_at_kst"]
        context["loaded_from_cache"] = True
        context["cache_stale"] = entry["is_stale"]
        return context

    def count(self, category: str | None = None) -> int:
        connection = self._connect()
        try:
            if category is None:
                row = connection.execute("SELECT COUNT(*) AS count FROM cache_entries").fetchone()
            else:
                row = connection.execute(
                    "SELECT COUNT(*) AS count FROM cache_entries WHERE category = ?",
                    (category,),
                ).fetchone()
        finally:
            connection.close()
        return int(row["count"])

    def _universe_key(self, provider: str, universe: str) -> str:
        return f"{provider}:universe:{universe}"

    def _context_key(self, provider: str, ticker: str) -> str:
        return f"{provider}:ticker_context:{ticker}"
