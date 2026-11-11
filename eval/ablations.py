"""E3 / RQ3: what each part of Vouch contributes (step 7.2). Offline replay of collected candidates, frozen config.

Sources
- cumulative cascade (exact): the live cascade always asks Crossref, then OpenAlex, then the type-routed specialist
  indexes (arXiv, DataCite, Open Library), then Semantic Scholar last, and stops at the first confident match. So
  keeping only the candidates of a cascade prefix reproduces exactly what that shorter cascade would have decided.
- leave-one-out (approximate for early sources): removing a source that ended the cascade early leaves later
  sources un-queried in our data, so its effect is an upper bound on harm. Removing S2 (always last) is exact.
Matching
- title-only (no author/venue/year checks), lenient thresholds (AtomGPT-like: verified >= 80, no author floor),
  untuned defaults, frozen. All with six sources.
Cost / latency per reference from the collection logs.

    backend/.venv/Scripts/python eval/ablations.py
"""

import json
import statistics
import sys
from dataclasses import replace
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW  # noqa: E402
from metrics import evaluate  # noqa: E402
from tune_rq1 import bests, load, predict  # noqa: E402

from app.pipeline.match import WEIGHTS as DEFAULT_W  # noqa: E402
from app.pipeline.verdict import DEFAULT, Thresholds  # noqa: E402

FROZEN = json.loads((EVAL / "configs" / "rq1.json").read_text(encoding="utf-8"))
W, T = FROZEN["weights"], Thresholds(**FROZEN["thresholds"])
SPECIALISTS = {"arxiv", "datacite", "openlibrary"}
ALL = {"crossref", "openalex", *SPECIALISTS, "s2"}


def restrict(rows: list[dict], keep: set[str]) -> list[dict]:
    out = []
    for r in rows:
        scored = [s for s in r["scored"] if s.candidate.source in keep]
        out.append({**r, "scored": scored, "failed_all": r["failed_all"] or not scored and not (keep & r["tried"])})
    return out


def run(rows: list[dict], w: dict, t: Thresholds) -> dict:
    gt = [r["GT"] for r in rows]
    m = evaluate(gt, predict(rows, bests(rows, w), t))
    return {k: m[k] for k in ("precision", "recall", "f1", "fpr", "TP", "FN", "FP", "TN")}


def collection_cost(split: str) -> dict:
    raw = [json.loads(l) for l in (RAW / "collect" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    secs = [x["seconds"] for x in raw if x.get("seconds")]
    tried = [len(x["tried"]) for x in raw]
    return {"n": len(raw), "median_seconds_cold": round(statistics.median(secs), 2), "p90_seconds_cold": round(sorted(secs)[int(0.9 * len(secs))], 2),
            "mean_sources_queried": round(statistics.mean(tried), 2)}


def main() -> None:
    out = {"config": {"weights": W, "thresholds": FROZEN["thresholds"]}}
    for split in ("dev_1000", "test_citeaudit300"):
        rows = load(split)
        raw = [json.loads(l) for l in (RAW / "collect" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        for r, x in zip(rows, raw):
            r["tried"] = set(x["tried"])
        res = {}
        res["cumulative"] = {
            "Crossref": run(restrict(rows, {"crossref"}), W, T),
            "+ OpenAlex": run(restrict(rows, {"crossref", "openalex"}), W, T),
            "+ arXiv, DataCite, Open Library": run(restrict(rows, {"crossref", "openalex", *SPECIALISTS}), W, T),
            "+ Semantic Scholar (all six)": run(rows, W, T),
        }
        res["leave_one_out"] = {f"without {s}": run(restrict(rows, ALL - {s}), W, T) for s in ("crossref", "openalex", "arxiv", "datacite", "openlibrary", "s2")}
        res["matching"] = {
            "frozen (strict fields)": run(rows, W, T),
            "untuned defaults": run(rows, dict(DEFAULT_W), DEFAULT),
            "lenient (verified >= 80, no author floor)": run(rows, W, replace(T, verified=80, title_min=80, author_min=0)),
            "title only": run(rows, {"title": 1.0, "authors": 0.0, "venue": 0.0, "year": 0.0}, replace(T, author_min=0, year_tolerance=99, book_year_any=True)),
        }
        res["cost"] = collection_cost(split)
        out[split] = res
        print(f"== {split}")
        for group, d in res.items():
            if group == "cost":
                print("  cost", d)
                continue
            for name, m in d.items():
                print(f"  {group:13} {name:42} P {m['precision']:.3f} R {m['recall']:.3f} F1 {m['f1']:.3f} FPR {m['fpr']:.3f}")
    (EVAL / "results" / "e3_ablations.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
