"""Persistent SQLite cache for API and LLM responses.

Every external call goes through here: it saves API budget (OpenAlex, S2 rate limits),
makes evaluation runs reproducible, and makes demo papers load instantly.
"""

import hashlib
import json
import sqlite3
import threading
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from .config import get_settings


def make_key(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


class Cache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS cache (ns TEXT, key TEXT, value TEXT, created REAL, PRIMARY KEY (ns, key))")
        self._db.commit()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    _MISS = object()

    def get(self, ns: str, key: str) -> Any:
        """Return the cached value, or Cache._MISS. A cached None is a real (negative) result."""
        with self._lock:
            row = self._db.execute("SELECT value FROM cache WHERE ns=? AND key=?", (ns, key)).fetchone()
        if row is None:
            self.misses += 1
            return Cache._MISS
        self.hits += 1
        return json.loads(row[0])["v"]

    def set(self, ns: str, key: str, value: Any) -> None:
        blob = json.dumps({"v": value}, ensure_ascii=False, default=str)
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (ns, key, blob, time.time()))
            self._db.commit()

    async def get_or_fetch(self, ns: str, key: str, fetch: Callable[[], Awaitable[Any]]) -> Any:
        value = self.get(ns, key)
        if value is not Cache._MISS:
            return value
        value = await fetch()
        self.set(ns, key, value)
        return value

    def count(self, ns: str | None = None) -> int:
        q, args = ("SELECT COUNT(*) FROM cache", ()) if ns is None else ("SELECT COUNT(*) FROM cache WHERE ns=?", (ns,))
        with self._lock:
            return self._db.execute(q, args).fetchone()[0]


_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache(get_settings().cache_file)
    return _cache
