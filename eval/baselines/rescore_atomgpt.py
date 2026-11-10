"""E0a: re-score the AtomGPT baseline's *released* per-citation outputs (no API calls).

Checks that our metric code reproduces their published table, and breaks results
down by source_type (generated vs real-world citations) for RQ2.

Run from the repo root:
    backend/.venv/Scripts/python eval/baselines/rescore_atomgpt.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RAW  # noqa: E402
from metrics import bootstrap_ci, evaluate, fmt  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parents[1] / "results" / "e0a_atomgpt_released_rescored.json"

RUNS = {
    "citeaudit300_v2": RAW / "atomgpt" / "results" / "citeaudit_300_v2.json",
    "neurips100_v1": RAW / "atomgpt" / "results" / "neurips2025_v1.json",
}


def main() -> None:
    report = {}
    for name, path in RUNS.items():
        d = json.loads(path.read_text(encoding="utf-8"))
        rows = d["results"]
        gt = [r["GT"] for r in rows]
        flagged = [r["status"] != "verified" for r in rows]
        overall = evaluate(gt, flagged)
        by_type = {}
        for st in sorted({r.get("source_type") for r in rows}):
            sub = [r for r in rows if r.get("source_type") == st]
            by_type[st] = evaluate([r["GT"] for r in sub], [r["status"] != "verified" for r in sub])
        report[name] = {
            "published_summary": {k: d["summary"].get(k) for k in
                                  ("total", "precision", "recall", "f1", "false_positive_rate")},
            "config": {k: d["config"].get(k) for k in ("scoring_version", "extraction_model", "weights")},
            "recomputed": overall,
            "ci95": {m: bootstrap_ci(gt, flagged, m) for m in ("f1", "recall", "precision", "fpr")},
            "status_counts": dict(Counter(r["status"] for r in rows)),
            "by_source_type": by_type,
        }
        print(f"== {name}\n   published : {report[name]['published_summary']}\n   recomputed: {fmt(overall)}")
        for st, m in by_type.items():
            print(f"   {st:12s}: {fmt(m)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(OUT.parents[2])}")


if __name__ == "__main__":
    main()
