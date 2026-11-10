"""Orchestrator: references -> resolver cascade -> matcher -> verdict -> Report."""

import asyncio
import time
from collections import Counter
from collections.abc import Awaitable, Callable

from ..cache import get_cache
from ..config import get_settings
from ..llm import Usage, current_usage
from ..models import (Candidate, PaperInfo, ParsedRef, RefResult, RefType, Report, RunMeta, Status)
from .match import best_match
from .ingest import grobid_references, ingest_arxiv, normalize_arxiv_id
from .parse_refs import parse_references, split_bibliography
from .resolvers import SOURCES, SourceError, api_calls
from .retraction import describe
from .retraction import get_index as get_retractions
from .verdict import DEFAULT, Thresholds, decide

# Per-source time budget per reference (S2 throttles hard; never let it stall a report)
TIME_BUDGET = {"s2": 20.0}
DEFAULT_BUDGET = 30.0
CONCURRENCY = 6

EventFn = Callable[[str, dict], Awaitable[None]] | None


def cascade_order(ref: ParsedRef, sources: list[str]) -> list[str]:
    """Route each reference to the sources most likely to hold it first."""
    first: list[str] = []
    if ref.arxiv_id or ref.type_guess is RefType.preprint:
        first.append("arxiv")
    if ref.type_guess in (RefType.dataset, RefType.software):
        first.append("datacite")
    if ref.isbn or ref.type_guess in (RefType.book, RefType.chapter):
        first.append("openlibrary")
    base = ["crossref", "openalex", "arxiv", "datacite", "openlibrary", "s2"]  # S2 last: rate-limited
    order = [s for s in ["crossref", "openalex", *first] if s in sources]
    return order + [s for s in base if s in sources and s not in order]


async def check_reference(ref: ParsedRef, sources: list[str], t: Thresholds = DEFAULT) -> RefResult:
    candidates: list[Candidate] = []
    tried, failed = [], []
    for name in cascade_order(ref, sources):
        try:
            found = await asyncio.wait_for(SOURCES[name].find(ref), TIME_BUDGET.get(name, DEFAULT_BUDGET))
        except (SourceError, asyncio.TimeoutError):
            failed.append(name)
            continue
        tried.append(name)
        candidates += found
        if decide(ref, best_match(ref, candidates), t=t).status is Status.verified:
            break  # confident match: stop early
    best = best_match(ref, candidates)
    v = decide(ref, best, all_sources_failed=not tried, t=t)
    # keep the record as evidence when it explains the verdict (e.g. a hijacked DOI)
    match = best.candidate if best and ((best.scores.composite or 0) >= t.found
                                         or v.status is Status.detail_mismatch) else None
    # Check ③: retraction / correction / expression of concern, by cited DOI, matched DOI, then exact title
    retraction = get_retractions().lookup(
        dois=[ref.doi, match.doi if match and v.status is Status.verified else None],
        title=ref.title if v.status is Status.verified else None)
    issues = ([describe(retraction)] if retraction else []) + v.issues
    issues += [f"sources unavailable: {', '.join(failed)}"] if failed else []
    return RefResult(idx=ref.idx, raw=ref.raw, parsed=ref, status=v.status, confidence=v.confidence,
                     match=match, retraction=retraction,
                     field_scores=best.scores if best else None, issues=issues,
                     sources_tried=tried + [f"{f} (failed)" for f in failed])


async def check_references(refs: list[ParsedRef], paper: PaperInfo, *, sources: list[str] | None = None,
                           t: Thresholds = DEFAULT, on_event: EventFn = None) -> Report:
    sources = sources or list(SOURCES)
    sem = asyncio.Semaphore(CONCURRENCY)
    report = Report(paper=paper)

    async def one(ref: ParsedRef) -> RefResult:
        async with sem:
            res = await check_reference(ref, sources, t)
        if on_event:
            await on_event("ref_done", res.model_dump(mode="json"))
        return res

    report.references = sorted(await asyncio.gather(*(one(r) for r in refs)), key=lambda r: r.idx)
    return report.refresh_summary()


async def _run(load: Callable[[], Awaitable[tuple[list[ParsedRef], PaperInfo, list[str]]]], *,
               sources: list[str] | None, t: Thresholds, on_event: EventFn) -> Report:
    """Shared wrapper: load references, check them, attach timing / LLM usage / API calls / cache stats."""
    t0 = time.perf_counter()
    usage, calls, cache = Usage(), Counter(), get_cache()
    hits0 = cache.hits
    u_tok, c_tok = current_usage.set(usage), api_calls.set(calls)
    try:
        refs, paper, notes = await load()
        if on_event:
            await on_event("parsed", {"n_refs": len(refs), "title": paper.title, "notes": notes})
        report = await check_references(refs, paper, sources=sources, t=t, on_event=on_event)
    finally:
        current_usage.reset(u_tok)
        api_calls.reset(c_tok)
    s = get_settings()
    report.meta = RunMeta(models={"parse": s.llm_model_parse, "judge": s.llm_model_judge},
                          seconds=round(time.perf_counter() - t0, 1), llm_calls=usage.calls,
                          llm_tokens_in=usage.tokens_in, llm_tokens_out=usage.tokens_out,
                          cost_usd=round(usage.cost_usd, 5), api_calls=dict(calls), cache_hits=cache.hits - hits0)
    report.meta.notes = notes
    if on_event:
        await on_event("done", {"summary": report.summary.model_dump()})
    return report


async def check_bibliography(text: str, *, sources: list[str] | None = None, t: Thresholds = DEFAULT,
                             on_event: EventFn = None, source_label: str = "bibliography") -> Report:
    """Full run on pasted bibliography text."""
    async def load():
        return await parse_references(split_bibliography(text)), PaperInfo(source=source_label), []
    return await _run(load, sources=sources, t=t, on_event=on_event)


async def check_arxiv(arxiv_id: str, *, sources: list[str] | None = None, t: Thresholds = DEFAULT,
                      on_event: EventFn = None) -> Report:
    """Full run on an arXiv paper (LaTeX source preferred, PDF via GROBID as fallback)."""
    async def load():
        ing = await ingest_arxiv(arxiv_id)
        aid = normalize_arxiv_id(arxiv_id)
        return ing.refs, PaperInfo(title=ing.title, source=f"arxiv:{aid}"), [f"references read from: {ing.method}", *ing.notes]
    return await _run(load, sources=sources, t=t, on_event=on_event)


async def check_pdf(pdf: bytes, filename: str = "upload.pdf", *, sources: list[str] | None = None,
                    t: Thresholds = DEFAULT, on_event: EventFn = None) -> Report:
    """Full run on an uploaded PDF (references extracted by GROBID)."""
    async def load():
        refs = await grobid_references(pdf)
        return refs, PaperInfo(source=f"pdf:{filename}"), ["references read from: PDF (GROBID)"]
    return await _run(load, sources=sources, t=t, on_event=on_event)
