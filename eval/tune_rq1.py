"""Step 3.1: tune matcher weights and verdict thresholds on the DEV split only (offline replay).

Reads candidates saved by collect.py, replays best-match selection + verdicts for many configurations,
and picks the one with the highest F1 (fake = positive), tie-broken by lower false-positive rate.
Reports: default config, tuned config (optimistic, in-sample) and 5-fold cross-validated estimate
(the whole search is re-run inside each fold).

    backend/.venv/Scripts/python eval/tune_rq1.py dev_1000
"""

import itertools
import json
import random
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW  # noqa: E402
from metrics import bootstrap_ci, evaluate, fmt  # noqa: E402

from app.models import Candidate, ParsedRef, Status  # noqa: E402
from app.pipeline.match import WEIGHTS, Scored, composite, score_candidate, select_best  # noqa: E402
from app.pipeline.verdict import DEFAULT, Thresholds, decide  # noqa: E402

SEED = 20261110
T_GRID = dict(verified=[75, 80, 85, 90], title_min=[75, 80, 85, 90], author_min=[34, 50, 60, 75],
              same_work_title=[85, 90, 95], found=[50, 60, 70])
W_GRID = dict(title=[0.45, 0.55, 0.65], authors=[0.2, 0.3, 0.4], venue=[0.05, 0.1, 0.15], year=[0.0, 0.05, 0.1])


def load(split: str) -> list[dict]:
    rows = []
    for line in (RAW / "collect" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        ref = ParsedRef.model_validate(r["parsed"])
        cands = [Candidate.model_validate(c) for c in r["candidates"]]
        rows.append({"ref": ref, "scored": [score_candidate(ref, c) for c in cands], "GT": r["GT"],
                     "source_type": r["source_type"], "failed_all": not r["tried"]})
    return rows


def bests(rows: list[dict], w: dict) -> list[Scored | None]:
    out = []
    for r in rows:
        rescored = [Scored(s.candidate, s.scores.model_copy(update={"composite": composite(s.scores, w, s.notice)}),
                           s.issues, s.doi_match, s.notice) for s in r["scored"]]
        out.append(select_best(rescored))
    return out


def predict(rows: list[dict], best: list, t: Thresholds) -> list[bool]:
    return [decide(r["ref"], b, all_sources_failed=r["failed_all"], t=t).status is not Status.verified
            for r, b in zip(rows, best)]


def score(rows, flagged) -> tuple:
    m = evaluate([r["GT"] for r in rows], flagged)
    return (m["f1"] or 0, -(m["fpr"] or 0)), m


def grid(d: dict):
    keys = list(d)
    for vals in itertools.product(*(d[k] for k in keys)):
        yield dict(zip(keys, vals))


def search(rows: list[dict]) -> tuple[dict, Thresholds, dict]:
    """Staged search: thresholds @ default weights -> weights @ top-5 thresholds -> thresholds @ best weights."""
    def best_t(b, cands_t):
        ranked = sorted(((score(rows, predict(rows, b, t))[0], i, t) for i, t in enumerate(cands_t)), reverse=True)
        return ranked
    all_t = [Thresholds(**g) for g in grid(T_GRID)]
    b0 = bests(rows, WEIGHTS)
    top_t = [t for _, _, t in best_t(b0, all_t)[:5]]
    best_w, best_key = WEIGHTS, None
    for w in grid(W_GRID):
        b = bests(rows, w)
        for t in top_t:
            key = score(rows, predict(rows, b, t))[0]
            if best_key is None or key > best_key:
                best_key, best_w = key, w
    bw = bests(rows, best_w)
    (key, _, t_final) = best_t(bw, all_t)[0]
    return best_w, t_final, score(rows, predict(rows, bw, t_final))[1]


def by_type(rows, flagged) -> dict:
    out = {}
    for st in sorted({r["source_type"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["source_type"] == st]
        out[st] = evaluate([rows[i]["GT"] for i in idx], [flagged[i] for i in idx])
    return out


def main() -> None:
    split = sys.argv[1] if len(sys.argv) > 1 else "dev_1000"
    t0 = time.perf_counter()
    rows = load(split)
    gt = [r["GT"] for r in rows]
    print(f"{split}: {len(rows)} citations ({Counter(gt)[True]} real / {Counter(gt)[False]} fake) · "
          f"{sum(r['failed_all'] for r in rows)} with every source failed")

    # 1. Default configuration (as shipped before tuning)
    b_def = bests(rows, WEIGHTS)
    f_def = predict(rows, b_def, DEFAULT)
    m_def = evaluate(gt, f_def)
    print("default :", fmt(m_def))

    # 2. Tuned on all of dev (in-sample, optimistic)
    w, t, m_tuned = search(rows)
    f_tuned = predict(rows, bests(rows, w), t)
    print("tuned   :", fmt(m_tuned), "\n          weights", w, "\n          thresholds", asdict(t))

    # 3. 5-fold cross-validation (search re-run inside each fold) -> honest dev estimate
    rng = random.Random(SEED)
    folds = [[], [], [], [], []]
    for cls in (True, False):
        idx = [i for i, r in enumerate(rows) if r["GT"] is cls]
        rng.shuffle(idx)
        for k, i in enumerate(idx):
            folds[k % 5].append(i)
    cv_flag = [None] * len(rows)
    fold_cfg = []
    for k in range(5):
        train = [rows[i] for f in range(5) if f != k for i in folds[f]]
        test_idx = folds[k]
        wk, tk, _ = search(train)
        test = [rows[i] for i in test_idx]
        for i, fl in zip(test_idx, predict(test, bests(test, wk), tk)):
            cv_flag[i] = fl
        fold_cfg.append({"weights": wk, "thresholds": asdict(tk)})
        print(f"  fold {k + 1}: thresholds {asdict(tk)} weights {wk}")
    m_cv = evaluate(gt, cv_flag)
    print("5-fold CV:", fmt(m_cv), "| F1 95% CI", bootstrap_ci(gt, cv_flag))

    # Label distribution under the tuned config (verified / mismatch / not found / can't verify)
    bw = bests(rows, w)
    labels = Counter(decide(r["ref"], b, all_sources_failed=r["failed_all"], t=t).status.value for r, b in zip(rows, bw))

    result = {
        "split": split, "n": len(rows), "seconds": round(time.perf_counter() - t0, 1),
        "grids": {"thresholds": T_GRID, "weights": W_GRID},
        "default": {"weights": WEIGHTS, "thresholds": asdict(DEFAULT), "metrics": m_def, "by_source_type": by_type(rows, f_def)},
        "tuned": {"weights": w, "thresholds": asdict(t), "metrics": m_tuned, "by_source_type": by_type(rows, f_tuned),
                  "labels": dict(labels), "ci95_f1": bootstrap_ci(gt, f_tuned)},
        "cv5": {"metrics": m_cv, "by_source_type": by_type(rows, cv_flag), "ci95_f1": bootstrap_ci(gt, cv_flag),
                "fold_configs": fold_cfg},
    }
    out = EVAL / "results" / f"e1_{split}_tuning.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    cfg = EVAL / "configs" / "rq1_candidate.json"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps({"tuned_on": split, "weights": w, "thresholds": asdict(t),
                               "dev_cv5_f1": m_cv["f1"], "dev_cv5_fpr": m_cv["fpr"]}, indent=1), encoding="utf-8")
    print(f"\nlabels: {dict(labels)}\nwrote {out.relative_to(EVAL.parent)} and {cfg.relative_to(EVAL.parent)} "
          f"({result['seconds']} s)")


if __name__ == "__main__":
    main()
