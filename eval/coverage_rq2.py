"""E2 / RQ2: which REAL references get wrongly flagged, by reference type x author region (step 7.1).

CoverageSet: real works sampled from OpenAlex (metadata CC0, so the set is committed) in 5 types x 3 regions,
formatted as plain citations without DOIs (as most reference lists are). Every item is real, so any flag is a
false accusation. Three systems on the same parsed references:
  - baseline (re-created): Semantic Scholar only, AtomGPT v2 scoring from its released config
    (title token_set_ratio 0.60 / authors 0.25 / journal 0.15, renormalised over available fields;
    verified >= 80, partial >= 60, top-5 hits). Not their code (decision 10 Nov, EXPERIMENTS.md).
  - Vouch, six sources, frozen config.
  - Vouch without OpenAlex: the set is sampled FROM OpenAlex, so this row removes that advantage.

    backend/.venv/Scripts/python eval/coverage_rq2.py build      # sample + format -> eval/data/coverageset.jsonl
    backend/.venv/Scripts/python eval/coverage_rq2.py run        # three systems -> eval/data/raw/coverage_runs.jsonl
    backend/.venv/Scripts/python eval/coverage_rq2.py report     # -> eval/results/e2_coverage.json
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx
from rapidfuzz import fuzz

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings  # noqa: E402
from app.models import ParsedRef  # noqa: E402
from app.pipeline.match import norm_title, parse_person  # noqa: E402
from app.pipeline.parse_refs import parse_references  # noqa: E402
from app.pipeline.resolvers import SOURCES  # noqa: E402
from app.pipeline.run import check_reference  # noqa: E402
from app.pipeline.tuned import TUNED_THRESHOLDS, TUNED_WEIGHTS  # noqa: E402

SET = EVAL / "data" / "coverageset.jsonl"
RUNS = EVAL / "data" / "raw" / "coverage_runs.jsonl"
OUT = EVAL / "results" / "e2_coverage.json"
TYPES = ["article", "book-chapter", "book", "report", "dataset"]
REGIONS = {"India": "IN", "Global South (other)": "BR|NG|ID|PK|BD|KE|ZA|EG|VN|PH|MX|CO",
           "Global North": "US|GB|DE|FR|CA|AU|NL|JP"}
PER_CELL = 15
SEED = 20261111
ATOM = {"title": 0.60, "authors": 0.25, "journal": 0.15, "verified": 80.0, "partial": 60.0, "top_k": 5}


# ---------------------------------------------------------------- build
def _surname_initials(display: str) -> str:
    parts = display.replace(",", " ").split()
    if len(parts) == 1:
        return parts[0]
    return f"{parts[-1]}, {' '.join(p[0] + '.' for p in parts[:-1] if p)}"


def _cite(w: dict) -> str | None:
    title = (w.get("display_name") or "").strip()
    names = [a["author"]["display_name"] for a in w.get("authorships", []) if a.get("author", {}).get("display_name")]
    if len(title.split()) < 3 or not names or not w.get("publication_year"):
        return None
    auth = ", ".join(_surname_initials(n) for n in names[:6]) + (", et al." if len(names) > 6 else "")
    src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    host = (w.get("host_venue") or {}).get("publisher") or ""
    venue = src or host
    return f"{auth} ({w['publication_year']}). {title}." + (f" {venue}." if venue else "")


def build() -> None:
    s = get_settings()
    out = []
    with httpx.Client(timeout=60) as c:
        for t in TYPES:
            for region, cc in REGIONS.items():
                r = c.get("https://api.openalex.org/works", params={
                    "filter": f"type:{t},authorships.institutions.country_code:{cc},publication_year:2012-2024",
                    "sample": 60, "seed": SEED, "per_page": 60, "api_key": s.openalex_keys[0], "mailto": s.crossref_mailto,
                    "select": "id,doi,display_name,publication_year,authorships,primary_location,type"})
                r.raise_for_status()
                cell = []
                for w in r.json()["results"]:
                    cite = _cite(w)
                    if cite and all(norm_title(w["display_name"]) != norm_title(x["title"]) for x in cell):
                        cell.append({"openalex": w["id"], "doi": w.get("doi"), "type": t, "region": region,
                                     "title": w["display_name"], "year": w["publication_year"], "citation": cite})
                    if len(cell) == PER_CELL:
                        break
                print(f"{t:13} {region:22} {len(cell)}")
                out += cell
    SET.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
    print(len(out), "->", SET)


# ---------------------------------------------------------------- baseline re-creation
def _atom_score(ref: ParsedRef, c) -> tuple[float, dict]:
    title = fuzz.token_set_ratio((ref.title or "").lower(), (c.title or "").lower())
    parts = {"title": (title, ATOM["title"])}
    if ref.authors and c.authors:
        cited = {p[0] for a in ref.authors if (p := parse_person(a))}
        rec = {p[0] for a in c.authors if (p := parse_person(a))}
        if cited:
            parts["authors"] = (100.0 * len(cited & rec) / len(cited), ATOM["authors"])
    if ref.venue and c.venue:
        parts["journal"] = (fuzz.token_set_ratio(ref.venue.lower(), c.venue.lower()), ATOM["journal"])
    wsum = sum(w for _, w in parts.values())
    return sum(v * w for v, w in parts.values()) / wsum, {k: round(v, 1) for k, (v, _) in parts.items()}


async def baseline(ref: ParsedRef) -> dict:
    try:
        cands = (await asyncio.wait_for(SOURCES["s2"].find(ref), 60))[: ATOM["top_k"]]
    except Exception as e:  # noqa: BLE001 - a failed lookup is recorded, not fatal
        return {"status": "error", "error": type(e).__name__}
    if not cands:
        return {"status": "likely hallucinated", "score": 0.0}
    score, parts = max((_atom_score(ref, c) for c in cands), key=lambda x: x[0])
    status = "verified" if score >= ATOM["verified"] else "partial" if score >= ATOM["partial"] else "likely hallucinated"
    return {"status": status, "score": round(score, 1), "parts": parts}


# ---------------------------------------------------------------- run
async def run() -> None:
    items = [json.loads(l) for l in SET.read_text(encoding="utf-8").splitlines() if l.strip()]
    done = {json.loads(l)["openalex"] for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()} if RUNS.exists() else set()
    todo = [x for x in items if x["openalex"] not in done]
    print(f"{len(items)} items, {len(todo)} to run")
    refs = await parse_references([x["citation"] for x in todo]) if todo else []
    six = list(SOURCES)
    no_oa = [s for s in six if s != "openalex"]
    sem = asyncio.Semaphore(4)
    t0 = time.time()

    async def one(x: dict, ref: ParsedRef) -> dict:
        async with sem:
            v = await check_reference(ref, six, TUNED_THRESHOLDS, TUNED_WEIGHTS, None, claims=False)
            v2 = await check_reference(ref, no_oa, TUNED_THRESHOLDS, TUNED_WEIGHTS, None, claims=False)
            b = await baseline(ref)
        row = {**x, "parsed": ref.model_dump(mode="json"), "vouch": v.status.value, "vouch_issue": (v.issues or [""])[0],
               "vouch_no_openalex": v2.status.value, "baseline": b["status"], "baseline_detail": b}
        with RUNS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    for k, (x, r) in enumerate(zip(todo, refs)):
        r.idx = k
    rows = []
    for k in range(0, len(todo), 20):
        rows += await asyncio.gather(*(one(x, r) for x, r in zip(todo[k:k + 20], refs[k:k + 20])))
        print(f"  {len(rows)}/{len(todo)} · {time.time() - t0:.0f}s", flush=True)


# ---------------------------------------------------------------- report
HARD = {"vouch": {"not_found", "detail_mismatch"}, "vouch_no_openalex": {"not_found", "detail_mismatch"},
        "baseline": {"likely hallucinated"}}


def report() -> None:
    rows = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["baseline"] != "error"]
    systems = ["baseline", "vouch_no_openalex", "vouch"]
    cells: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "flagged": 0, "hard": 0}))
    for r in rows:
        for key in [(r["type"], r["region"]), (r["type"], "all"), ("all", r["region"]), ("all", "all")]:
            for s in systems:
                c = cells["|".join(key)][s]
                c["n"] += 1
                c["flagged"] += r[s] != "verified"
                c["hard"] += r[s] in HARD[s]
    out = {"n": len(rows), "per_cell": PER_CELL, "seed": SEED, "atomgpt_config": ATOM, "cells": {}}
    for key, d in sorted(cells.items()):
        out["cells"][key] = {s: {**v, "fpr": round(v["flagged"] / v["n"], 3), "hard_rate": round(v["hard"] / v["n"], 3)} for s, v in d.items()}
    errors = sum(1 for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip() and json.loads(l)["baseline"] == "error")
    out["baseline_errors_excluded"] = errors
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"n={len(rows)} (baseline errors excluded: {errors})")
    print(f"{'cell':40} {'baseline':>14} {'vouch-noOA':>14} {'vouch':>14}   (flagged share / hard accusations)")
    for key, d in out["cells"].items():
        print(f"{key:40} " + " ".join(f"{d[s]['fpr']:>6.2f} / {d[s]['hard_rate']:<5.2f}" for s in systems) + f"   n={d['vouch']['n']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "build":
        build()
    elif cmd == "run":
        asyncio.run(run())
    else:
        report()
