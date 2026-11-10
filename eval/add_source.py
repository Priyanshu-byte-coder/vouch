"""Add one more source (default: Semantic Scholar) to an existing collection, as the cascade would:
only for citations that are not already a near-certain match. Resumable; saves progress as it goes.

    backend/.venv/Scripts/python eval/add_source.py dev_1000 [--source s2]
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from collect import near_certain  # noqa: E402
from common import RAW  # noqa: E402

from app.models import Candidate, ParsedRef  # noqa: E402
from app.pipeline.resolvers import SOURCES, SourceError  # noqa: E402

BUDGET = 90.0


def save(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    tmp.replace(path)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("split")
    ap.add_argument("--source", default="s2")
    args = ap.parse_args()
    path = RAW / "collect" / f"{args.split}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    src = args.source

    def needs(r: dict) -> bool:
        if src in r["tried"] or src in r["failed"]:
            return False
        ref = ParsedRef.model_validate(r["parsed"])
        return not near_certain(ref, [Candidate.model_validate(c) for c in r["candidates"]])

    todo = [i for i, r in enumerate(rows) if needs(r)]
    print(f"{args.split}: {len(rows)} rows · {len(todo)} need {src}", flush=True)
    t0 = time.perf_counter()
    ok = fail = 0
    for n, i in enumerate(todo, 1):
        r = rows[i]
        ref = ParsedRef.model_validate(r["parsed"])
        try:
            found = await asyncio.wait_for(SOURCES[src].find(ref), BUDGET)
            r["candidates"] += [c.model_dump() for c in found]
            r["tried"].append(src)
            ok += 1
        except (SourceError, asyncio.TimeoutError):
            r["failed"].append(src)
            fail += 1
        if n % 10 == 0 or n == len(todo):
            save(path, rows)
            el = time.perf_counter() - t0
            print(f"  {n}/{len(todo)} · ok {ok} · failed {fail} · {el / 60:.1f} min · ~{el / n * (len(todo) - n) / 60:.0f} min left",
                  flush=True)
    save(path, rows)
    print(f"done: ok {ok}, failed {fail}, {(time.perf_counter() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
