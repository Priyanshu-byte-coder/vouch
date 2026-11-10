"""Smoke test: one request to every external source Vouch depends on.

Run from the repo root:
    backend/.venv/Scripts/python backend/scripts/smoke_test.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MAILTO = os.getenv("CROSSREF_MAILTO", "")
OPENALEX_KEY = os.getenv("OPENALEX_API_KEY", "")
S2_KEY = os.getenv("S2_API_KEY", "")
LLM_BASE = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_KEY = os.getenv("LLM_API_KEY", "")
LLM_PARSE = os.getenv("LLM_MODEL_PARSE", "")
GROBID = os.getenv("GROBID_URL", "http://localhost:8070").rstrip("/")

TITLE = "Attention is all you need"
UA = {"User-Agent": f"Vouch/0.1 (research-integrity hackathon project; mailto:{MAILTO})"}


async def crossref(c):
    r = await c.get("https://api.crossref.org/works",
                    params={"query.bibliographic": TITLE, "rows": 1, "mailto": MAILTO})
    r.raise_for_status()
    item = r.json()["message"]["items"][0]
    return f"{item['title'][0][:50]} · DOI {item.get('DOI')}"


async def openalex(c):
    r = await c.get("https://api.openalex.org/works",
                    params={"search": TITLE, "per_page": 1, "api_key": OPENALEX_KEY,
                            "select": "display_name,publication_year,doi"})
    r.raise_for_status()
    w = r.json()["results"][0]
    return f"{w['display_name'][:50]} ({w['publication_year']})"


async def semantic_scholar(c):
    headers = {"x-api-key": S2_KEY} if S2_KEY else {}
    r = await c.get("https://api.semanticscholar.org/graph/v1/paper/search/match",
                    params={"query": TITLE, "fields": "title,year"}, headers=headers)
    if r.status_code == 429:
        raise RuntimeError("429 rate-limited (no API key yet; shared pool busy)")
    r.raise_for_status()
    p = r.json()["data"][0]
    return f"{p['title'][:50]} ({p['year']}) · key={'yes' if S2_KEY else 'no'}"


async def arxiv(c):
    r = await c.get("https://export.arxiv.org/api/query", params={"id_list": "1706.03762"})
    r.raise_for_status()
    ok = "Attention Is All You Need" in r.text
    if not ok:
        raise RuntimeError("unexpected response")
    return "1706.03762 → Attention Is All You Need"


async def dblp(c):
    r = await c.get("https://dblp.org/search/publ/api", params={"q": TITLE, "format": "json", "h": 1})
    r.raise_for_status()
    if "json" not in r.headers.get("content-type", ""):
        raise RuntimeError(f"HTTP {r.status_code}, anti-bot page instead of JSON (not used in the cascade)")
    hit = r.json()["result"]["hits"]["hit"][0]["info"]
    return f"{hit['title'][:50]} · {hit.get('venue')}"


async def datacite(c):
    r = await c.get("https://api.datacite.org/dois", params={"query": "ImageNet", "page[size]": 1})
    r.raise_for_status()
    d = r.json()["data"][0]["attributes"]
    return f"{d['titles'][0]['title'][:50]} · DOI {d['doi']}"


async def open_library(c):
    r = await c.get("https://openlibrary.org/search.json",
                    params={"title": "Deep Learning", "author": "Goodfellow", "limit": 1})
    r.raise_for_status()
    doc = r.json()["docs"][0]
    return f"{doc['title'][:50]} ({doc.get('first_publish_year')})"


async def retraction_watch(c):
    # HEAD-like check on the CSV in the Crossref GitLab repo (full download happens in step 1.1)
    r = await c.get("https://gitlab.com/api/v4/projects/crossref%2Fretraction-watch-data/repository/commits",
                    params={"per_page": 1})
    r.raise_for_status()
    commit = r.json()[0]
    return f"latest data commit: {commit['title']}"


async def llm(c):
    h = {"Authorization": f"Bearer {LLM_KEY}"}
    r = await c.get(f"{LLM_BASE}/models", headers=h)
    r.raise_for_status()
    n_models = len(r.json()["data"])
    body = {"model": LLM_PARSE, "temperature": 0, "max_tokens": 50,
            "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none",
            "messages": [{"role": "user", "content": 'Reply with only this JSON: {"ok": true}'}]}
    r = await c.post(f"{LLM_BASE}/chat/completions", headers=h, json=body)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    json.loads(content[content.find("{"):content.rfind("}") + 1])
    return f"{n_models} models · {LLM_PARSE} JSON ok"


async def grobid(c):
    r = await c.get(f"{GROBID}/api/isalive")
    r.raise_for_status()
    return f"isalive={r.text.strip()}"


CHECKS = [
    ("Crossref", crossref, True), ("OpenAlex", openalex, True), ("Semantic Scholar", semantic_scholar, False),
    ("arXiv", arxiv, True), ("DBLP (dropped)", dblp, False), ("DataCite", datacite, True),
    ("Open Library", open_library, True), ("Retraction Watch", retraction_watch, True),
    ("LLM endpoint", llm, True), ("GROBID (step 0.4)", grobid, False),
]


async def main():
    missing = [k for k, v in {"CROSSREF_MAILTO": MAILTO, "OPENALEX_API_KEY": OPENALEX_KEY,
                              "LLM_API_KEY": LLM_KEY, "LLM_MODEL_PARSE": LLM_PARSE}.items() if not v]
    if missing:
        print("Missing in .env:", ", ".join(missing))
    failures = 0
    async with httpx.AsyncClient(timeout=30, headers=UA, follow_redirects=True) as c:
        for name, fn, required in CHECKS:
            t = time.perf_counter()
            try:
                info = await fn(c)
                status = "OK  "
            except Exception as e:  # noqa: BLE001 - report every failure, keep going
                info = f"{type(e).__name__}: {e}"[:120]
                status = "FAIL" if required else "WARN"
                failures += required
            print(f"[{status}] {name:18s} {time.perf_counter() - t:5.2f}s  {info}")
    print("\nAll required sources OK." if not failures else f"\n{failures} required source(s) failed.")
    return failures


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
