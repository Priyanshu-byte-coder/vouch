"""Step 3.3: effect of Semantic Scholar and of the LLM adjudicator, with the step-3.1 config FROZEN.

1. Frozen verdicts on the collection with and without S2 candidates.
2. The adjudicator runs on borderline references (not verified, best title >= 50). Results are cached.
3. Only two adjudicator settings are tuned on the split (min title score of the chosen record, min
   confidence), maximising F1 under the same FPR cap, with 5-fold CV. On a test split, pass --apply to use
   the settings frozen in eval/configs/rq1_adjudicator.json without tuning.

    backend/.venv/Scripts/python eval/adjudicate_eval.py dev_1000
    backend/.venv/Scripts/python eval/adjudicate_eval.py test_citeaudit300 --apply
"""

import asyncio
import itertools
import json
import random
import sys
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from common import RAW  # noqa: E402
from metrics import bootstrap_ci, evaluate, fmt  # noqa: E402
from tune_rq1 import bests, load, predict  # noqa: E402

from app.llm import Usage, current_usage  # noqa: E402
from app.pipeline.adjudicate import adjudicate  # noqa: E402
from app.pipeline.verdict import Thresholds  # noqa: E402

FROZEN = json.loads((EVAL / "configs" / "rq1.json").read_text(encoding="utf-8"))
ADJ_CFG = EVAL / "configs" / "rq1_adjudicator.json"
FPR_CAP = 0.10
BAND = [50, 60, 70, 80, 90, 95, 98, 101]  # 101 = adjudicator off (S12: title variants let fakes through)
CONF = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
SEED = 20261110


async def run_adjudicator(split: str, rows: list[dict], flagged: list[bool], best: list) -> list[dict | None]:
    """Adjudicate every flagged reference with a plausible candidate; cached per (split, hash)."""
    out_path = RAW / "collect" / f"adj_{split}.jsonl"
    raw = [json.loads(line) for line in (RAW / "collect" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    done = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            done[d["hash"]] = d
    sem = asyncio.Semaphore(6)
    usage = Usage()
    current_usage.set(usage)
    todo = [i for i, (f, b) in enumerate(zip(flagged, best)) if f and b and (b.scores.title or 0) >= min(BAND)
            and raw[i]["hash"] not in done]
    print(f"adjudicating {len(todo)} borderline references ({len(done)} cached)", flush=True)

    async def one(i: int) -> None:
        async with sem:
            r = await adjudicate(rows[i]["ref"], rows[i]["scored"])
        m = r["match"]
        done[raw[i]["hash"]] = {"hash": raw[i]["hash"], "match_title": m.candidate.title if m else None,
                                "match_source": m.candidate.source if m else None,
                                "match_title_score": m.scores.title if m else None,
                                "confidence": r["confidence"], "reason": r["reason"]}
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(done[raw[i]["hash"]], ensure_ascii=False) + "\n")

    await asyncio.gather(*(one(i) for i in todo))
    print(f"  LLM: {usage.calls} calls, ${usage.cost_usd:.3f}", flush=True)
    return [done.get(x["hash"]) for x in raw]


def apply_adj(flagged: list[bool], adj: list[dict | None], band: float, conf: float) -> list[bool]:
    return [f and not (a and a["match_title"] and (a["match_title_score"] or 0) >= band and a["confidence"] >= conf)
            for f, a in zip(flagged, adj)]


def pick(rows, flagged, adj) -> tuple[float, float, dict]:
    gt = [r["GT"] for r in rows]
    best_key, best = None, None
    for band, conf in itertools.product(BAND, CONF):
        m = evaluate(gt, apply_adj(flagged, adj, band, conf))
        fpr = m["fpr"] or 0
        key = (fpr <= FPR_CAP + 1e-9, round(m["f1"] or 0, 4) if fpr <= FPR_CAP + 1e-9 else -fpr, -round(fpr, 4), band, conf)
        if best_key is None or key > best_key:  # ties -> higher band and confidence (more conservative)
            best_key, best = key, (band, conf, m)
    return best


def main() -> None:
    split = sys.argv[1]
    apply = "--apply" in sys.argv
    w, t = FROZEN["weights"], Thresholds(**FROZEN["thresholds"])
    rows = load(split)
    gt = [r["GT"] for r in rows]
    b = bests(rows, w)
    flagged = predict(rows, b, t)
    m_s2 = evaluate(gt, flagged)

    rows_no = [dict(r, scored=[s for s in r["scored"] if s.candidate.source != "s2"]) for r in rows]
    m_no = evaluate(gt, predict(rows_no, bests(rows_no, w), t))
    print(f"{split}: n={len(rows)}")
    print("  frozen, without S2       :", fmt(m_no))
    print("  frozen, with S2          :", fmt(m_s2))

    adj = asyncio.run(run_adjudicator(split, rows, flagged, b))
    result = {"split": split, "frozen_no_s2": m_no, "frozen_s2": m_s2}
    if apply:
        cfg = json.loads(ADJ_CFG.read_text(encoding="utf-8"))
        f_adj = apply_adj(flagged, adj, cfg["band"], cfg["confidence"])
        m_adj = evaluate(gt, f_adj)
        print(f"  frozen + S2 + adjudicator (band {cfg['band']}, conf {cfg['confidence']}):", fmt(m_adj))
        result.update({"adjudicator_config": cfg, "frozen_s2_adj": m_adj,
                       "ci95": {k: bootstrap_ci(gt, f_adj, k) for k in ("precision", "recall", "f1", "fpr")},
                       "by_source_type": {st: evaluate([g for g, r in zip(gt, rows) if r["source_type"] == st],
                                                       [f for f, r in zip(f_adj, rows) if r["source_type"] == st])
                                          for st in sorted({r["source_type"] for r in rows})},
                       "flags": f_adj})
    else:
        band, conf, m_in = pick(rows, flagged, adj)
        print(f"  + adjudicator, in-sample (band {band}, conf {conf}):", fmt(m_in))
        rng = random.Random(SEED)
        folds = [[] for _ in range(5)]
        for cls in (True, False):
            idx = [i for i, r in enumerate(rows) if r["GT"] is cls]
            rng.shuffle(idx)
            for k, i in enumerate(idx):
                folds[k % 5].append(i)
        cv = [None] * len(rows)
        fold_cfg = []
        for k in range(5):
            tr = [i for f in range(5) if f != k for i in folds[f]]
            bk, ck, _ = pick([rows[i] for i in tr], [flagged[i] for i in tr], [adj[i] for i in tr])
            fold_cfg.append((bk, ck))
            for i, f in zip(folds[k], apply_adj([flagged[i] for i in folds[k]], [adj[i] for i in folds[k]], bk, ck)):
                cv[i] = f
        m_cv = evaluate(gt, cv)
        print(f"  + adjudicator, 5-fold CV  :", fmt(m_cv), "| folds:", fold_cfg, "| F1 CI", bootstrap_ci(gt, cv))
        result.update({"in_sample": {"band": band, "confidence": conf, "metrics": m_in}, "cv5": m_cv,
                       "cv5_ci95_f1": bootstrap_ci(gt, cv), "fold_configs": fold_cfg})
        ADJ_CFG.write_text(json.dumps({"status": "candidate (needs approval)", "tuned_on": split, "fpr_cap": FPR_CAP,
                                       "band": band, "confidence": conf, "dev_cv5_f1": m_cv["f1"], "dev_cv5_fpr": m_cv["fpr"]},
                                      indent=1), encoding="utf-8")
    verdicts = Counter("same" if a and a["match_title"] else "none" if a else "not run" for a in adj)
    print("  adjudicator answers:", dict(verdicts))
    out = EVAL / "results" / f"e3_adjudicator_{split}.json"
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"wrote {out.relative_to(EVAL.parent)}")


if __name__ == "__main__":
    main()
