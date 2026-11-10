"""Shared HTTP layer for every scholarly source: one client per event loop, per-source
rate limiting, retries with backoff, response caching and per-job call counting."""

import asyncio
import time
from collections import Counter
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any

import httpx

from ...cache import Cache, get_cache, make_key
from ...config import get_settings

# Minimum seconds between requests to each source (S2 comes from settings: 1 req/s per its licence)
MIN_INTERVAL = {"crossref": 0.1, "openalex": 0.1, "arxiv": 3.0, "datacite": 0.2, "openlibrary": 0.5}

# API calls made in the current job (each pipeline run sets its own Counter)
api_calls: ContextVar[Counter] = ContextVar("api_calls", default=Counter())


class SourceError(RuntimeError):
    """A source failed after retries (distinct from 'not found')."""


_clients: dict[int, httpx.AsyncClient] = {}
_locks: dict[tuple[int, str], asyncio.Lock] = {}
_last_call: dict[str, float] = {}


def _loop_id() -> int:
    return id(asyncio.get_running_loop())


def http() -> httpx.AsyncClient:
    lid = _loop_id()
    client = _clients.get(lid)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0), follow_redirects=True,
            headers={"User-Agent": get_settings().user_agent},
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))
        _clients[lid] = client
    return client


async def _throttle(source: str) -> None:
    interval = get_settings().s2_min_interval if source == "s2" else MIN_INTERVAL.get(source, 0.0)
    if not interval:
        return
    lock = _locks.setdefault((_loop_id(), source), asyncio.Lock())
    async with lock:
        wait = _last_call.get(source, 0.0) + interval - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call[source] = time.monotonic()


def _retry_after(r: httpx.Response, attempt: int) -> float:
    try:
        return min(float(r.headers.get("retry-after", "")), 30.0)
    except ValueError:
        return min(2.0 * 2 ** attempt, 30.0)


async def get(source: str, url: str, *, params: dict | None = None, headers: dict | None = None,
              auth_params: dict | None = None, rotate: Callable[[], dict | None] | None = None,
              as_text: bool = False, max_attempts: int = 5, cache_ns: str | None = None) -> Any:
    """GET a JSON (or text) resource with caching, throttling and retries.

    Returns the parsed body, or None for 404/400 (cached as a negative result).
    `auth_params` (e.g. API keys) are sent but excluded from the cache key; `rotate` may
    return new auth params when a key is rate-limited or out of budget.
    Raises SourceError when the source keeps failing.
    """
    cache = get_cache()
    ns = cache_ns or source
    key = make_key(url, params or {})
    hit = cache.get(ns, key)
    if hit is not Cache._MISS:
        return hit

    last = "no attempt"
    for attempt in range(max_attempts):
        await _throttle(source)
        api_calls.get()[source] += 1
        try:
            r = await http().get(url, params={**(params or {}), **(auth_params or {})}, headers=headers)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last = f"{type(e).__name__}"
            await asyncio.sleep(min(2.0 * 2 ** attempt, 30.0))
            continue
        if r.status_code in (400, 404, 410):
            cache.set(ns, key, None)
            return None
        if r.status_code in (401, 402, 403, 429) and rotate:
            new_auth = rotate()
            if new_auth is not None:
                auth_params = new_auth
                continue
        if r.status_code == 429 or r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            await asyncio.sleep(_retry_after(r, attempt))
            continue
        if r.status_code >= 300:
            raise SourceError(f"{source}: HTTP {r.status_code} for {url}")
        body = r.text if as_text else r.json()
        cache.set(ns, key, body)
        return body
    raise SourceError(f"{source}: gave up after {max_attempts} attempts ({last})")
