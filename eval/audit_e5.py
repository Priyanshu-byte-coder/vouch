"""E5 / RQ5: audit of recent real papers (steps 8.2-8.3).

30 recent arXiv papers: 20 sampled from the newest cs.CL / cs.LG / cs.AI submissions, 10 with an Indian
affiliation (via OpenAlex). Each is checked with the deployed configuration. Ethics (docs/IDEATION.md §8):
per-paper reports and the flag sheet stay in eval/data/raw/audit/ (gitignored); only aggregates are published.

    backend/.venv/Scripts/python eval/audit_e5.py select     # -> raw/audit/papers.json
    backend/.venv/Scripts/python eval/audit_e5.py run        # -> raw/audit/reports/*.json + flags.csv (to hand-label)
    backend/.venv/Scripts/python eval/audit_e5.py report     # -> eval/results/e5_audit.json (uses labels if present)

Hand labels: fill the `label` column of raw/audit/flags.csv with  correct  (the flag is right: the reference
really is wrong/unfindable as cited),  wrong  (false alarm), or  unsure.
"""

import asyncio
import csv
import json
import random
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import httpx

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.config import get_settings  # noqa: E402
from app.pipeline.run import check_arxiv  # noqa: E402

DIR = EVAL / "data" / "raw" / "audit"
PAPERS, FLAGS, OUT = DIR / "papers.json", DIR / "flags.csv", EVAL / "results" / "e5_audit.json"
SEED, N_RECENT, N_INDIA = 20261111, 20, 10
HARD = {"not_found", "detail_mismatch"}


def select() -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    with httpx.Client(timeout=60, headers={"User-Agent": s.user_agent}) as c:
        r = c.get("https://export.arxiv.org/api/query", params={
            "search_query": "cat:cs.CL OR cat:cs.LG OR cat:cs.AI", "sortBy": "submittedDate", "sortOrder": "descending",
            "start": 0, "max_results": 200})
        r.raise_for_status()
        ns = {"a": "http://www.w3.org/2005/Atom"}
        recent = [re.sub(r"v\d+$", "", e.findtext("a:id", "", ns).rsplit("/abs/", 1)[-1])
                  for e in ET.fromstring(r.text).findall("a:entry", ns)]
        india = []
        r = c.get("https://api.openalex.org/works", params={
            "filter": "authorships.institutions.country_code:IN,locations.source.id:S4306400194,publication_year:2026",
            "sample": 80, "seed": SEED, "per_page": 80, "select": "id,locations", "api_key": s.openalex_keys[0]})
        r.raise_for_status()
        for w in r.json()["results"]:
            for loc in w.get("locations") or []:
                m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", loc.get("landing_page_url") or "")
                if m:
                    india.append(m.group(1))
                    break
    rnd = random.Random(SEED)
    picked = [{"arxiv": a, "group": "recent cs"} for a in rnd.sample(recent, N_RECENT)]
    picked += [{"arxiv": a, "group": "India-affiliated"} for a in rnd.sample(sorted(set(india) - {p["arxiv"] for p in picked}), N_INDIA)]
    PAPERS.write_text(json.dumps(picked, indent=1), encoding="utf-8")
    print(len(picked), "papers ->", PAPERS)


async def run() -> None:
    papers = json.loads(PAPERS.read_text(encoding="utf-8"))
    (DIR / "reports").mkdir(exist_ok=True)
    t0 = time.time()
    for n, p in enumerate(papers, 1):
        out = DIR / "reports" / f"{n:02d}.json"
        if out.exists():
            continue
        try:
            rep = await check_arxiv(p["arxiv"])
            out.write_text(json.dumps({"paper_no": n, **p, "report": rep.model_dump(mode="json")}, ensure_ascii=False), encoding="utf-8")
            print(f"{n:02d} {p['group']:17} {len(rep.references):3} refs {dict((k, v) for k, v in rep.summary.model_dump().items() if v)} · {time.time() - t0:.0f}s", flush=True)
        except Exception as e:  # noqa: BLE001 - one bad paper must not stop the audit
            out.write_text(json.dumps({"paper_no": n, **p, "error": f"{type(e).__name__}: {e}"[:300]}), encoding="utf-8")
            print(f"{n:02d} ERROR {e}", flush=True)
    write_flags()


def _reports() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted((DIR / "reports").glob("*.json"))]


def write_flags() -> None:
    old = {}
    if FLAGS.exists():
        with FLAGS.open(encoding="utf-8") as fh:
            old = {(r["paper_no"], r["ref_no"]): r.get("label", "") for r in csv.DictReader(fh)}
    rows = []
    for d in _reports():
        for r in (d.get("report") or {}).get("references", []):
            if r["status"] in HARD or r.get("retraction"):
                m = r.get("match") or {}
                key = (str(d["paper_no"]), str(r["idx"] + 1))
                rows.append({"paper_no": d["paper_no"], "group": d["group"], "ref_no": r["idx"] + 1, "status": r["status"],
                             "retraction": (r.get("retraction") or {}).get("nature", ""), "cited": r["raw"][:400],
                             "best_record": f"{m.get('title', '')} | {'; '.join((m.get('authors') or [])[:4])} | {m.get('year', '')} | {m.get('doi') or m.get('url') or ''}" if m else "",
                             "issue": (r.get("issues") or [""])[0][:300],
                             "check_on_scholar": "https://scholar.google.com/scholar?q=" + urllib.parse.quote((r["parsed"].get("title") or r["raw"])[:200]),
                             "label": old.get(key, "")})
    with FLAGS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["paper_no"])
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "flags ->", FLAGS)


def report() -> None:
    reps = [d for d in _reports() if "report" in d]
    status, per_paper_hard, tortured, retracted = Counter(), [], 0, 0
    claims = Counter()
    for d in reps:
        refs = d["report"]["references"]
        status.update(r["status"] for r in refs)
        per_paper_hard.append(sum(r["status"] in HARD for r in refs))
        tortured += len(d["report"].get("tortured", []))
        retracted += sum(1 for r in refs if (r.get("retraction") or {}).get("nature") == "Retraction")
        claims.update(c["label"] for r in refs for c in r.get("claims", []))
    labels = Counter()
    if FLAGS.exists():
        with FLAGS.open(encoding="utf-8") as fh:
            labels = Counter((r["status"], (r.get("label") or "").strip().lower() or "unlabelled") for r in csv.DictReader(fh))
    n_refs = sum(status.values())
    out = {"papers": len(reps), "errors": len(_reports()) - len(reps), "references": n_refs, "status": dict(status),
           "papers_with_hard_flag": sum(1 for x in per_paper_hard if x), "papers_with_2plus_hard_flags": sum(1 for x in per_paper_hard if x >= 2),
           "retracted_citations": retracted, "tortured_hits": tortured, "claims": dict(claims),
           "hand_labels": {f"{s}|{l}": n for (s, l), n in labels.items()}}
    lab = [(s, l) for (s, l), n in labels.items() for _ in range(n) if l in ("correct", "wrong")]
    if lab:
        out["flag_precision_hand_labelled"] = round(sum(l == "correct" for _, l in lab) / len(lab), 3)
        out["flags_labelled"] = len(lab)
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"select": select, "run": lambda: asyncio.run(run()), "flags": write_flags, "report": report}[cmd]()
