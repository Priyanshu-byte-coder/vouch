"""Collect candidates for every citation in a split, once, so thresholds can be tuned offline.

For each citation: LLM-parse it, query the cascade, and save every candidate. The cascade stops early
only on a near-certain match (title >= 95, composite >= 95, authors >= 80 or unknown), so the saved
candidates support any thresholds below those bars. Output is resumable JSONL in eval/data/raw/collect/
(gitignored: it contains CiteAudit text).

    backend/.venv/Scripts/python eval/collect.py dev_1000 [--sources crossref,openalex,arxiv,datacite,openlibrary]
"""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW, load_split  # noqa: E402

from app.llm import Usage, current_usage  # noqa: E402
from app.models import ParsedRef  # noqa: E402
from app.pipeline.match import best_match  # noqa: E402
from app.pipeline.parse_refs import parse_references  # noqa: E402
from app.pipeline.resolvers import SOURCES, SourceError, api_calls  # noqa: E402
from app.pipeline.run import DEFAULT_BUDGET, TIME_BUDGET, cascade_order  # noqa: E402

OUT_DIR = RAW / "collect"
DEFAULT_SOURCES = ["crossref", "openalex", "arxiv", "datacite", "openlibrary"]  # S2 excluded (throttled); see E3


def near_certain(ref: ParsedRef, candidates) -> bool:
    b = best_match(ref, candidates)
    if not b:
        return False
    s = b.scores
    return (s.title or 0) >= 95 and (s.composite or 0) >= 95 and (s.authors is None or s.authors >= 80)


async def resolve_all(ref: ParsedRef, sources: list[str]) -> dict:
    cands, tried, failed = [], [], []
    for name in cascade_order(ref, sources):
        try:
            found = await asyncio.wait_for(SOURCES[name].find(ref), TIME_BUDGET.get(name, DEFAULT_BUDGET))
        except (SourceError, asyncio.TimeoutError):
            failed.append(name)
            continue
        tried.append(name)
        cands += found
        if near_certain(ref, cands):
            break
    return {"candidates": [c.model_dump() for c in cands], "tried": tried, "failed": failed}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("split")
    ap.add_argument("--sources", default=",".join(DEFAULT_SOURCES))
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--chunk", type=int, default=48, help="citations parsed per chunk")
    args = ap.parse_args()
    sources = args.sources.split(",")
    tag = "" if sources == DEFAULT_SOURCES else "__" + "-".join(sources)
    out = OUT_DIR / f"{args.split}{tag}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    records = load_split(args.split)
    done = set()
    if out.exists():
        done = {json.loads(line)["hash"] for line in out.read_text(encoding="utf-8").splitlines() if line.strip()}
    todo = [r for r in records if r["hash"] not in done]
    print(f"{args.split}: {len(records)} citations, {len(done)} already collected, {len(todo)} to go · sources={sources}",
          flush=True)

    usage, calls = Usage(), Counter()
    current_usage.set(usage)
    api_calls.set(calls)
    sem = asyncio.Semaphore(args.concurrency)
    t0, n_done = time.perf_counter(), 0

    async def one(rec: dict, ref: ParsedRef, fh) -> None:
        nonlocal n_done
        async with sem:
            t = time.perf_counter()
            res = await resolve_all(ref, sources)
        row = {"index": rec["index"], "hash": rec["hash"], "GT": rec["GT"], "source_type": rec["source_type"],
               "citation": rec["citation"], "parsed": ref.model_dump(mode="json"), **res,
               "seconds": round(time.perf_counter() - t, 2)}
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        n_done += 1
        if n_done % 25 == 0 or n_done == len(todo):
            el = time.perf_counter() - t0
            print(f"  {n_done}/{len(todo)} · {el / 60:.1f} min · ~{el / n_done * (len(todo) - n_done) / 60:.0f} min left · "
                  f"LLM ${usage.cost_usd:.3f} · API {dict(calls)}", flush=True)

    with open(out, "a", encoding="utf-8") as fh:
        for start in range(0, len(todo), args.chunk):
            chunk = todo[start:start + args.chunk]
            parsed = await parse_references([r["citation"] for r in chunk])
            await asyncio.gather(*(one(rec, ref, fh) for rec, ref in zip(chunk, parsed)))
    print(f"done in {(time.perf_counter() - t0) / 60:.1f} min · LLM {usage.calls} calls ${usage.cost_usd:.3f} · "
          f"API {dict(calls)} · wrote {out}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
