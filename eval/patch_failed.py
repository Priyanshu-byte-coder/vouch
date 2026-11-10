"""Retry the sources that failed or timed out during collect.py, one request at a time.

arXiv allows one request every 3 s, so under concurrency many arXiv calls queue past their time
budget. This pass re-queries only those (reference, source) pairs and rewrites the JSONL in place.

    backend/.venv/Scripts/python eval/patch_failed.py dev_1000
"""

import asyncio
import json
import sys
import time
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW  # noqa: E402

from app.models import ParsedRef  # noqa: E402
from app.pipeline.resolvers import SOURCES, SourceError  # noqa: E402

BUDGET = 120.0


async def main() -> None:
    path = RAW / "collect" / f"{sys.argv[1]}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    todo = [(i, s) for i, r in enumerate(rows) for s in r["failed"]]
    print(f"{len(todo)} failed (citation, source) pairs to retry", flush=True)
    t0, fixed = time.perf_counter(), 0
    for n, (i, source) in enumerate(todo, 1):
        r = rows[i]
        ref = ParsedRef.model_validate(r["parsed"])
        try:
            found = await asyncio.wait_for(SOURCES[source].find(ref), BUDGET)
        except (SourceError, asyncio.TimeoutError):
            continue
        r["candidates"] += [c.model_dump() for c in found]
        r["failed"].remove(source)
        r["tried"].append(source)
        fixed += 1
        if n % 20 == 0:
            print(f"  {n}/{len(todo)} · fixed {fixed} · {(time.perf_counter() - t0) / 60:.1f} min", flush=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    still = sum(len(r["failed"]) for r in rows)
    print(f"done: fixed {fixed}/{len(todo)}, still failing {still}, {(time.perf_counter() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
