"""Export chart data for the website's research page into frontend/src/lib/research.json.

Reads only committed results files and the local raw collections (replayed with the FROZEN config, no tuning).
Adds keys to the existing research.json; never changes the headline numbers.

    backend/.venv/Scripts/python eval/export_frontend_stats.py
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW  # noqa: E402
from tune_rq1 import bests, load  # noqa: E402

from app.pipeline.verdict import Thresholds, decide  # noqa: E402

OUT = EVAL.parent / "frontend" / "src" / "lib" / "research.json"
FROZEN = json.loads((EVAL / "configs" / "rq1.json").read_text(encoding="utf-8"))
W, T = FROZEN["weights"], Thresholds(**FROZEN["thresholds"])
TITLE_OK = T.title_min

ISSUE_KIND = [("DOI", "doi"), ("author", "authors"), ("year", "year"), ("venue", "venue"), ("title", "title"), ("short title", "title")]


def issue_kind(issues: list[str]) -> str:
    for i in issues:
        low = i.lower()
        for key, kind in ISSUE_KIND:
            if key.lower() in low:
                return kind
    return "other"


def replay(split: str) -> dict:
    rows = load(split)
    raw = [json.loads(l) for l in (RAW / "collect" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    b = bests(rows, W)
    verdicts = [decide(r["ref"], x, all_sources_failed=r["failed_all"], t=T) for r, x in zip(rows, b)]

    labels = {"real": Counter(), "fake": Counter()}
    winning_source = Counter()
    fake_issue_kind = Counter()
    coverage_tried, coverage_hit = Counter(), Counter()
    for r, x, v, rw in zip(rows, b, verdicts, raw):
        truth = "real" if r["GT"] else "fake"
        labels[truth][v.status.value] += 1
        if r["GT"] and v.status.value == "verified" and x is not None:
            winning_source[x.candidate.source] += 1
        if not r["GT"] and v.status.value == "detail_mismatch":
            fake_issue_kind[issue_kind(v.issues)] += 1
        if r["GT"]:
            hits = {s.candidate.source for s in r["scored"] if (s.scores.title or 0) >= TITLE_OK}
            for src in rw["tried"]:
                coverage_tried[src] += 1
                if src in hits:
                    coverage_hit[src] += 1
    coverage = {s: {"tried": coverage_tried[s], "hit": coverage_hit[s], "rate": round(coverage_hit[s] / coverage_tried[s], 3)}
                for s in coverage_tried if coverage_tried[s] >= 10}
    return {"n": len(rows), "labels_by_truth": {k: dict(v) for k, v in labels.items()},
            "winning_source_real_verified": dict(winning_source), "fake_mismatch_issue_kind": dict(fake_issue_kind),
            "source_coverage_real": coverage}


def baseline_labels() -> dict:
    d = json.loads((RAW / "atomgpt" / "results" / "citeaudit_300_v2.json").read_text(encoding="utf-8"))
    out = {"real": Counter(), "fake": Counter()}
    for r in d["results"]:
        out["real" if r["GT"] else "fake"][r["status"]] += 1
    return {k: dict(v) for k, v in out.items()}


def main() -> None:
    research = json.loads(OUT.read_text(encoding="utf-8"))
    tuning = json.loads((EVAL / "results" / "e1_dev_1000_tuning.json").read_text(encoding="utf-8"))
    test6 = json.loads((EVAL / "results" / "e1_test_results_6sources.json").read_text(encoding="utf-8"))
    test5 = json.loads((EVAL / "results" / "e1_test_results_retried.json").read_text(encoding="utf-8"))
    test_as = json.loads((EVAL / "results" / "e1_test_results_as_collected.json").read_text(encoding="utf-8"))
    e0a = json.loads((EVAL / "results" / "e0a_atomgpt_released_rescored.json").read_text(encoding="utf-8"))

    m = lambda d: {k: d[k] for k in ("n", "precision", "recall", "f1", "fpr", "TP", "FN", "FP", "TN") if k in d}  # noqa: E731
    research["story"] = {
        "dev_default": m(tuning["default"]["metrics"]),
        "dev_tuned_in_sample": m(tuning["tuned"]["metrics"]),
        "dev_cv5": m(tuning["cv5"]["metrics"]),
        "test_untuned_6src": m(test6["splits"]["test_citeaudit300"]["default_untuned"]["metrics"]),
        "test_5src_as_collected": m(test_as["splits"]["test_citeaudit300"]["tuned"]["metrics"]),
        "test_5src_retried": m(test5["splits"]["test_citeaudit300"]["tuned"]["metrics"]),
        "test_6src": m(test6["splits"]["test_citeaudit300"]["tuned"]["metrics"]),
        "fold_configs": [{"verified": f["thresholds"]["verified"], "title_min": f["thresholds"]["title_min"],
                          "author_min": f["thresholds"]["author_min"], "year_tolerance": f["thresholds"]["year_tolerance"],
                          "w_authors": f["weights"]["authors"]} for f in tuning["cv5"]["fold_configs"]],
        "grid": tuning["grids"],
        "frozen": {"weights": W, "thresholds": FROZEN["thresholds"]},
        "by_type": {
            "baseline": {k: m(v) for k, v in e0a["citeaudit300_v2"]["by_source_type"].items()},
            "vouch": {k: m(v) for k, v in test6["splits"]["test_citeaudit300"]["tuned"]["by_source_type"].items()},
            "dev_cv5": {k: m(v) for k, v in tuning["cv5"]["by_source_type"].items()},
        },
        "adjudicator": {"frozen": {"recall": 0.830, "f1": 0.870, "fpr": 0.078}, "best_adjudicated": {"recall": 0.646, "f1": 0.756, "fpr": 0.062},
                        "unflagged_fakes": 89, "rescued_real": 4, "cv_folds_off": 5, "cost_usd": 0.651, "calls": 422},
        "s2_on_dev": {"five": {"precision": 0.914, "recall": 0.830, "f1": 0.870, "fpr": 0.078},
                      "six": {"precision": 0.930, "recall": 0.822, "f1": 0.873, "fpr": 0.062}},
        "data": {"citeaudit_total": 9442, "citeaudit_real": 6475, "citeaudit_fake": 2967, "removed_exact": 303, "removed_near": 144,
                 "dev_full": 8995, "dev_1000": 1000, "test_citeaudit300": 300, "test_neurips100": 100, "retraction_notices": 73718},
        "neurips_labels": test6["splits"]["test_neurips100"]["tuned"]["labels"],
        "test_labels": test6["splits"]["test_citeaudit300"]["tuned"]["labels"],
        "baseline_labels_by_truth": baseline_labels(),
        "ablations": json.loads((EVAL / "results" / "e3_ablations.json").read_text(encoding="utf-8")),
        "scifact": json.loads((EVAL / "results" / "e4_scifact.json").read_text(encoding="utf-8")),
        "coverage": json.loads((EVAL / "results" / "e2_coverage.json").read_text(encoding="utf-8")),
        "audit": json.loads((EVAL / "results" / "e5_audit.json").read_text(encoding="utf-8")),
        "test": replay("test_citeaudit300"),
        "dev": replay("dev_1000"),
    }
    OUT.write_text(json.dumps(research, indent=1, ensure_ascii=False), encoding="utf-8")
    s = research["story"]
    print("test labels by truth", s["test"]["labels_by_truth"])
    print("baseline labels by truth", s["baseline_labels_by_truth"])
    print("winning source (test, real verified)", s["test"]["winning_source_real_verified"])
    print("coverage (test)", s["test"]["source_coverage_real"])
    print("coverage (dev)", s["dev"]["source_coverage_real"])
    print("fake mismatch issue kinds (test)", s["test"]["fake_mismatch_issue_kind"], "(dev)", s["dev"]["fake_mismatch_issue_kind"])
    print("story keys", list(s.keys()))


if __name__ == "__main__":
    main()
