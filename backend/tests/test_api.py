"""Offline API tests: the pipeline is replaced by a fake that emits events quickly."""

import asyncio
import json

import httpx
import pytest

import app.main as main
from app.cache import Cache
from app.models import PaperInfo, ParsedRef, RefResult, Report, Status


async def fake_check(text, *, sources=None, on_event=None, **_):
    report = Report(paper=PaperInfo(source="bibliography"))
    await on_event("parsed", {"n_refs": 2, "title": None, "notes": []})
    for i in range(2):
        await asyncio.sleep(0.01)
        r = RefResult(idx=i, raw=f"ref {i}", parsed=ParsedRef(idx=i, raw=f"ref {i}"),
                      status=Status.verified if i == 0 else Status.not_found, confidence=0.9)
        report.references.append(r)
        await on_event("ref_done", r.model_dump(mode="json"))
    report.refresh_summary()
    await on_event("done", {"summary": report.summary.model_dump()})
    return report


@pytest.fixture
async def client(tmp_path, monkeypatch):
    cache = Cache(tmp_path / "c.sqlite")
    monkeypatch.setattr(main, "get_cache", lambda: cache)
    monkeypatch.setattr(main, "check_bibliography", fake_check)
    monkeypatch.setattr(main, "store", main.JobStore())
    main._hits.clear()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://t") as c:
        yield c


async def _wait_done(client, job_id):
    for _ in range(100):
        body = (await client.get(f"/api/jobs/{job_id}")).json()
        if body["status"] in ("done", "error"):
            return body
        await asyncio.sleep(0.02)
    raise AssertionError("job did not finish")


async def test_check_job_lifecycle_and_cache(client):
    job_id = (await client.post("/api/check", json={"bibliography": "[1] A ref.\n[2] Another."})).json()["job_id"]
    body = await _wait_done(client, job_id)
    assert body["status"] == "done" and body["report"]["summary"]["verified"] == 1
    assert body["report"]["summary"]["not_found"] == 1

    # identical input -> served from the report cache, same result
    job2 = (await client.post("/api/check", json={"bibliography": "[1] A ref.\n[2] Another."})).json()["job_id"]
    body2 = await _wait_done(client, job2)
    assert body2["report"]["summary"] == body["report"]["summary"]
    assert any(e["event"] == "parsed" and e["data"].get("cached") for e in main.store.get(job2).events)


async def test_sse_stream_replays_events(client):
    job_id = (await client.post("/api/check", json={"bibliography": "[1] One ref here."})).json()["job_id"]
    await _wait_done(client, job_id)
    events = []
    async with client.stream("GET", f"/api/jobs/{job_id}/events") as r:
        async for line in r.aiter_lines():
            if line.startswith("event:"):
                events.append(line.split(":", 1)[1].strip())
    assert events[0] == "status" and events[1] == "parsed"
    assert events.count("ref_done") == 2 and events[-1] == "report"


async def test_validation_and_limits(client, monkeypatch):
    assert (await client.post("/api/check", json={})).status_code == 422
    assert (await client.post("/api/check", json={"arxiv_id": "1", "bibliography": "x"})).status_code == 422
    assert (await client.get("/api/jobs/nope")).status_code == 404
    bad = await client.post("/api/check/pdf", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 415
    monkeypatch.setattr(main, "RATE_LIMIT", (2, 600))
    codes = [(await client.post("/api/check", json={"bibliography": f"[1] Ref {i}."})).status_code for i in range(3)]
    assert codes == [200, 200, 429]


async def test_health(client):
    body = (await client.get("/api/health")).json()
    assert body["ok"] and "crossref" in body["sources"] and body["keys"]["llm"]
