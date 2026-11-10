"""Step 3.2 / E1: evaluate the FROZEN config on the untouched test sets. No tuning happens here.

- Metrics with bootstrap 95% CIs, by citation type, label distribution
- Paired comparison with the AtomGPT baseline's released per-citation outputs (same citations),
  with an exact McNemar test on correct/incorrect decisions

    backend/.venv/Scripts/python eval/run_rq1_detection.py
"""

import json
import math
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW, citation_hash  # noqa: E402
from metrics import bootstrap_ci, evaluate, fmt  # noqa: E402
from tune_rq1 import bests, load, predict  # noqa: E402

from app.pipeline.match import WEIGHTS  # noqa: E402
from app.pipeline.verdict import DEFAULT, Thresholds, decide  # noqa: E402

FROZEN = json.loads((EVAL / "configs" / "rq1.json").read_text(encoding="utf-8"))
BASELINE_FILES = {"test_citeaudit300": RAW / "atomgpt" / "results" / "citeaudit_300_v2.json",
                  "test_neurips100": RAW / "atomgpt" / "results" / "neurips2025_v1.json"}


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value: b = only ours correct, c = only baseline correct."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def cis(gt, flagged) -> dict:
    return {m: bootstrap_ci(gt, flagged, m) for m in ("precision", "recall", "f1", "fpr")}


def evaluate_split(split: str, w: dict, t: Thresholds) -> dict:
    rows = load(split)
    raw = [json.loads(line) for line in (RAW / "collect" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    gt = [r["GT"] for r in rows]
    b = bests(rows, w)
    flagged = predict(rows, b, t)
    labels = Counter(decide(r["ref"], x, all_sources_failed=r["failed_all"], t=t).status.value for r, x in zip(rows, b))
    by_type = {}
    for st in sorted({r["source_type"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["source_type"] == st]
        by_type[st] = evaluate([gt[i] for i in idx], [flagged[i] for i in idx])
    out = {"n": len(rows), "metrics": evaluate(gt, flagged), "ci95": cis(gt, flagged), "by_source_type": by_type,
           "labels": dict(labels), "failed_sources": dict(Counter(f for x in raw for f in x["failed"]))}

    # Paired comparison with the baseline's released outputs, joined on the citation text
    base = json.loads(BASELINE_FILES[split].read_text(encoding="utf-8"))["results"]
    base_flag = {citation_hash(r["citation"]): r["status"] != "verified" for r in base}
    ours = {citation_hash(x["citation"]): (x["GT"], f) for x, f in zip(raw, flagged)}
    common = [h for h in ours if h in base_flag]
    g = [ours[h][0] for h in common]
    fo = [ours[h][1] for h in common]
    fb = [base_flag[h] for h in common]
    # A decision is correct when a fake is flagged or a real citation is not
    ours_ok = [o == (not real) for real, o in zip(g, fo)]
    base_ok = [b_ == (not real) for real, b_ in zip(g, fb)]
    only_ours = sum(a and not b_ for a, b_ in zip(ours_ok, base_ok))
    only_base = sum(b_ and not a for a, b_ in zip(ours_ok, base_ok))
    out["paired_vs_baseline"] = {
        "n_common": len(common), "ours": evaluate(g, fo), "baseline": evaluate(g, fb),
        "only_ours_correct": only_ours, "only_baseline_correct": only_base,
        "mcnemar_p": mcnemar_exact(only_ours, only_base)}
    return out


def main() -> None:
    w, t = FROZEN["weights"], Thresholds(**FROZEN["thresholds"])
    results = {"config": FROZEN, "splits": {}}
    for split in ("test_citeaudit300", "test_neurips100"):
        tuned = evaluate_split(split, w, t)
        default = evaluate_split(split, WEIGHTS, DEFAULT)
        results["splits"][split] = {"tuned": tuned, "default_untuned": {"metrics": default["metrics"], "labels": default["labels"]}}
        pv = tuned["paired_vs_baseline"]
        print(f"\n=== {split} (n={tuned['n']})")
        print("  Vouch (frozen) :", fmt(tuned["metrics"]))
        print("  95% CIs        :", {k: tuple(round(x, 3) for x in v) if v else None for k, v in tuned["ci95"].items()})
        print("  Vouch (untuned):", fmt(default["metrics"]))
        for st, m in tuned["by_source_type"].items():
            print(f"    {st:12s}: {fmt(m)}")
        print("  labels:", tuned["labels"], "| failed sources:", tuned["failed_sources"])
        print(f"  paired vs AtomGPT on {pv['n_common']} shared citations:")
        print("    baseline:", fmt(pv["baseline"]))
        print("    Vouch   :", fmt(pv["ours"]))
        print(f"    only Vouch correct: {pv['only_ours_correct']} · only baseline correct: {pv['only_baseline_correct']} · "
              f"exact McNemar p = {pv['mcnemar_p']:.2g}")
    out = EVAL / "results" / "e1_test_results.json"
    out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nwrote {out.relative_to(EVAL.parent)}")


if __name__ == "__main__":
    main()
