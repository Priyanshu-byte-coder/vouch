"""Vouch HTTP API.

    uvicorn app.main:app --port 8000          (from backend/)

POST /api/check          {"arxiv_id": "..."} or {"bibliography": "..."}  -> {"job_id": ...}
POST /api/check/pdf      multipart "file"                                -> {"job_id": ...}
GET  /api/jobs/{id}      status + partial or final report
GET  /api/jobs/{id}/events  Server-Sent Events: status, parsed, ref_done, done, report | error
GET  /api/health
"""

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, model_validator
from sse_starlette.sse import EventSourceResponse

from .cache import get_cache, make_key
from .config import get_settings
from .jobs import Job, JobStore
from .models import Report
from .pipeline.ingest import is_arxiv_id, normalize_arxiv_id
from .pipeline.resolvers import SOURCES
from .pipeline.retraction import get_index as get_retractions
from .pipeline.run import check_arxiv, check_bibliography, check_pdf

REPORT_VERSION = "v4"           # bump when the pipeline changes so cached reports are recomputed
MAX_BIB_CHARS = 100_000
MAX_PDF_BYTES = 20 * 1024 * 1024
RATE_LIMIT = (int(os.getenv("VOUCH_RATE_LIMIT", "12")), 600)  # jobs per IP per 10 minutes

store = JobStore()
_hits: dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.get_running_loop().run_in_executor(None, get_retractions)  # warm the 70 MB index in the background
    yield


app = FastAPI(title="Vouch API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("VOUCH_CORS_ORIGINS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])


class CheckRequest(BaseModel):
    arxiv_id: str | None = None
    bibliography: str | None = None
    skip_s2: bool = False
    refresh: bool = False  # ignore a cached report

    @model_validator(mode="after")
    def exactly_one(self):
        if bool(self.arxiv_id) == bool(self.bibliography):
            raise ValueError("send exactly one of arxiv_id or bibliography")
        if self.bibliography and len(self.bibliography) > MAX_BIB_CHARS:
            raise ValueError(f"bibliography too long (max {MAX_BIB_CHARS} characters)")
        return self


def _rate_limit(request: Request) -> None:
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    limit, window = RATE_LIMIT
    q, now = _hits[ip], time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, f"rate limit: {limit} checks per {window // 60} minutes")
    q.append(now)


def _sources(skip_s2: bool) -> list[str]:
    return [s for s in SOURCES if not (skip_s2 and s == "s2")]


async def _cached_or_run(job: Job, key: str, run, refresh: bool) -> Report:
    cache = get_cache()
    hit = None if refresh else cache.get("report", key)
    if hit and hit is not cache._MISS:
        report = Report.model_validate(hit)
        await job.emit("parsed", {"n_refs": len(report.references), "title": report.paper.title,
                                  "notes": report.meta.notes, "cached": True})
        for r in report.references:
            await job.emit("ref_done", r.model_dump(mode="json"))
        await job.emit("done", {"summary": report.summary.model_dump(), "cached": True})
        return report
    report = await run(on_event=job.emit)
    cache.set("report", key, report.model_dump(mode="json"))
    return report


@app.post("/api/check")
async def create_check(req: CheckRequest, request: Request) -> dict:
    sources = _sources(req.skip_s2)
    if req.arxiv_id and not is_arxiv_id(normalize_arxiv_id(req.arxiv_id)):
        raise HTTPException(422, f"'{req.arxiv_id[:60]}' is not an arXiv ID (expected e.g. 2602.23452 or an arxiv.org/abs/ link)")
    _rate_limit(request)  # only accepted requests count
    if req.arxiv_id:
        aid = normalize_arxiv_id(req.arxiv_id)
        key = make_key(REPORT_VERSION, "arxiv", aid, sources)
        job = store.start("arxiv", aid, lambda j: _cached_or_run(
            j, key, lambda on_event: check_arxiv(aid, sources=sources, on_event=on_event), req.refresh))
    else:
        text = req.bibliography or ""
        key = make_key(REPORT_VERSION, "bib", text, sources)
        job = store.start("bibliography", f"{len(text)} chars", lambda j: _cached_or_run(
            j, key, lambda on_event: check_bibliography(text, sources=sources, on_event=on_event), req.refresh))
    return {"job_id": job.id}


@app.post("/api/check/pdf")
async def create_check_pdf(request: Request, file: UploadFile = File(...)) -> dict:
    data = await file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF too large (max 20 MB)")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "not a PDF file")
    _rate_limit(request)  # only accepted uploads count
    name = (file.filename or "upload.pdf")[:120]
    key = make_key(REPORT_VERSION, "pdf", data)
    job = store.start("pdf", name, lambda j: _cached_or_run(
        j, key, lambda on_event: check_pdf(data, name, sources=_sources(False), on_event=on_event), False))
    return {"job_id": job.id}


def _job(job_id: str) -> Job:
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job (jobs are kept in memory and expire)")
    return job


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    return _job(job_id).summary()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    job = _job(job_id)
    start = int(request.headers.get("last-event-id", "-1")) + 1

    async def stream():
        i = start
        while True:
            if await request.is_disconnected():
                return
            while i < len(job.events):
                e = job.events[i]
                yield {"id": str(e["id"]), "event": e["event"], "data": json.dumps(e["data"])}
                i += 1
            if job.status in ("done", "error") and i >= len(job.events):
                return
            await job.wait_for_events(i)

    return EventSourceResponse(stream(), ping=15)


@app.get("/api/health")
async def health() -> dict:
    s = get_settings()
    grobid = False
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            grobid = (await c.get(f"{s.grobid_url}/api/isalive")).text.strip() == "true"
    except httpx.HTTPError:
        pass
    return {"ok": True, "version": REPORT_VERSION, "sources": list(SOURCES), "grobid": grobid,
            "keys": {"openalex": len(s.openalex_keys), "s2": bool(s.s2_api_key), "llm": bool(s.llm_api_key)},
            "retraction_index_loaded": get_retractions.cache_info().currsize > 0,
            "jobs": {"total": len(store.jobs), "running": sum(j.status == "running" for j in store.jobs.values())}}
