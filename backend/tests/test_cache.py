import pytest

from app.cache import Cache, make_key


def test_roundtrip_and_namespaces(tmp_path):
    c = Cache(tmp_path / "c.sqlite")
    k = make_key("crossref", "attention is all you need")
    assert c.get("crossref", k) is Cache._MISS
    c.set("crossref", k, {"title": "Attention Is All You Need", "year": 2017})
    assert c.get("crossref", k)["year"] == 2017
    assert c.get("openalex", k) is Cache._MISS  # namespaces are separate
    assert c.hits == 1 and c.misses == 2


def test_negative_results_are_cached(tmp_path):
    c = Cache(tmp_path / "c.sqlite")
    c.set("s2", "k", None)
    assert c.get("s2", "k") is None  # a cached "not found", not a miss


def test_persists_across_instances(tmp_path):
    Cache(tmp_path / "c.sqlite").set("ns", "k", [1, 2])
    assert Cache(tmp_path / "c.sqlite").get("ns", "k") == [1, 2]


def test_make_key_is_order_stable():
    assert make_key({"a": 1, "b": 2}) == make_key({"b": 2, "a": 1})
    assert make_key("x", 1) != make_key("x", 2)


async def test_get_or_fetch_calls_once(tmp_path):
    c = Cache(tmp_path / "c.sqlite")
    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return {"ok": True}

    assert await c.get_or_fetch("ns", "k", fetch) == {"ok": True}
    assert await c.get_or_fetch("ns", "k", fetch) == {"ok": True}
    assert calls == 1
