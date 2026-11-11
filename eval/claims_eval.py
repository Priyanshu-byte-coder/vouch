"""E4 / RQ4: claim support on SciFact (step 6.2).

Each (claim, cited abstract) pair has a gold label: SUPPORTS / CONTRADICTS (from the rationale annotations) or
NOT_ENOUGH_INFO (cited abstract without a rationale). Three variants of app/pipeline/claims.py:
  direct      model label as is
  grounding   SUPPORTS/CONTRADICTS need a quote that is really in the abstract
  abstention  grounding + abstain below a confidence threshold tau
tau is chosen on a train sample (the lowest-confidence 20% abstain, hypothesis H4) and applied unchanged to dev.
SciFact's test labels are hidden, so dev is our test set; it is not used for any choice.

    backend/.venv/Scripts/python eval/claims_eval.py [--train 200] [--thinking]
"""

import argparse
import asyncio
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

EVAL = Path(__file__).resolve().parent
sys.path.insert(0, str(EVAL.parent / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.llm import Usage, current_usage  # noqa: E402
from app.pipeline.claims import apply_policy, judge  # noqa: E402

SCI = EVAL / "data" / "raw" / "scifact" / "data"
LABELS = ["SUPPORTS", "CONTRADICTS", "NOT_ENOUGH_INFO"]
GOLD = {"SUPPORT": "SUPPORTS", "CONTRADICT": "CONTRADICTS"}


def pairs(split: str) -> list[dict]:
    corpus = {d["doc_id"]: d for d in map(json.loads, (SCI / "corpus.jsonl").read_text(encoding="utf-8").splitlines())}
    out = []
    for c in map(json.loads, (SCI / f"claims_{split}.jsonl").read_text(encoding="utf-8").splitlines()):
        for doc in c.get("cited_doc_ids", []):
            ev = c.get("evidence", {}).get(str(doc))
            gold = GOLD[ev[0]["label"]] if ev else "NOT_ENOUGH_INFO"
            d = corpus[doc]
            out.append({"claim_id": c["id"], "doc_id": doc, "claim": c["claim"], "abstract": " ".join(d["abstract"]), "gold": gold})
    return out


def macro_f1(gold: list[str], pred: list[str]) -> float:
    f1s = []
    for lab in LABELS:
        tp = sum(g == lab and p == lab for g, p in zip(gold, pred))
        fp = sum(g != lab and p == lab for g, p in zip(gold, pred))
        fn = sum(g == lab and p != lab for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def ece(conf: list[float], correct: list[bool], bins: int = 10) -> float:
    n, total = len(conf), 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(conf) if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if idx:
            acc = sum(correct[i] for i in idx) / len(idx)
            avg = sum(conf[i] for i in idx) / len(idx)
            total += len(idx) / n * abs(acc - avg)
    return total


def score(rows: list[dict], raws: list[dict], *, grounding: bool, tau: float | None) -> dict:
    preds = [apply_policy(r, x["abstract"], grounding=grounding, tau=tau) for x, r in zip(rows, raws)]
    gold = [x["gold"] for x in rows]
    answered = [i for i, p in enumerate(preds) if p[0] != "ABSTAIN"]
    g = [gold[i] for i in answered]
    p = [preds[i][0] for i in answered]
    acc = sum(a == b for a, b in zip(g, p)) / len(g) if g else 0.0
    conf = [preds[i][1] for i in answered]
    return {"n": len(rows), "answered": len(answered), "coverage": len(answered) / len(rows), "accuracy": acc,
            "macro_f1": macro_f1(g, p), "ece": ece(conf, [a == b for a, b in zip(g, p)]),
            "pred_counts": dict(Counter(p)), "gold_counts": dict(Counter(gold))}


def coverage_curve(rows: list[dict], raws: list[dict]) -> list[dict]:
    """Accuracy of the grounded answers when abstaining on the least-confident k% (k = 0..60)."""
    preds = [apply_policy(r, x["abstract"], grounding=True, tau=None) for x, r in zip(rows, raws)]
    order = sorted(range(len(rows)), key=lambda i: preds[i][1], reverse=True)
    out = []
    for k in range(0, 65, 5):
        keep = order[: max(1, round(len(order) * (1 - k / 100)))]
        g = [rows[i]["gold"] for i in keep]
        p = [preds[i][0] for i in keep]
        out.append({"abstain_pct": k, "coverage": len(keep) / len(rows),
                    "accuracy": sum(a == b for a, b in zip(g, p)) / len(keep), "macro_f1": macro_f1(g, p)})
    return out


async def run_all(rows: list[dict], thinking: bool, conc: int = 8) -> list[dict]:
    sem = asyncio.Semaphore(conc)

    async def one(x):
        async with sem:
            return await judge(x["claim"], x["abstract"], thinking=thinking)

    return await asyncio.gather(*(one(x) for x in rows))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=200)
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--abstain", type=float, default=0.20, help="share of least-confident train answers to abstain on")
    args = ap.parse_args()

    random.seed(20261111)
    train = random.sample(pairs("train"), args.train)
    dev = pairs("dev")
    usage = Usage()
    current_usage.set(usage)
    t0 = time.time()
    async def both():  # one event loop: the LLM client is shared
        return await run_all(train, args.thinking), await run_all(dev, args.thinking)

    raw_train, raw_dev = asyncio.run(both())

    # tau from TRAIN only: the confidence below which the lowest-confidence share of grounded answers falls
    tr_conf = sorted(apply_policy(r, x["abstract"], grounding=True)[1] for x, r in zip(train, raw_train))
    tau = tr_conf[int(len(tr_conf) * args.abstain)] if tr_conf else 0.0

    res = {
        "config": {"model": "deepseek-v4.1-flash-1017", "thinking": args.thinking, "train_pairs": len(train), "dev_pairs": len(dev),
                   "abstain_share_on_train": args.abstain, "tau": tau, "seed": 20261111},
        "train": {"direct": score(train, raw_train, grounding=False, tau=None),
                  "grounding": score(train, raw_train, grounding=True, tau=None),
                  "abstention": score(train, raw_train, grounding=True, tau=tau)},
        "dev": {"direct": score(dev, raw_dev, grounding=False, tau=None),
                "grounding": score(dev, raw_dev, grounding=True, tau=None),
                "abstention": score(dev, raw_dev, grounding=True, tau=tau)},
        "dev_coverage_curve": coverage_curve(dev, raw_dev),
        "grounding_effect_dev": {
            "ungrounded_support_or_contradict": sum(1 for x, r in zip(dev, raw_dev) if r["label"] in ("SUPPORTS", "CONTRADICTS")
                                                    and apply_policy(r, x["abstract"])[0] == "NOT_ENOUGH_INFO"),
        },
        "cost": {"llm_calls": usage.calls, "usd": round(usage.cost_usd, 4), "seconds": round(time.time() - t0, 1)},
    }
    name = "e4_scifact_thinking.json" if args.thinking else "e4_scifact.json"
    (EVAL / "results" / name).write_text(json.dumps(res, indent=1), encoding="utf-8")
    for split in ("train", "dev"):
        for v, m in res[split].items():
            print(f"{split:5} {v:10} coverage {m['coverage']:.2f}  acc {m['accuracy']:.3f}  macroF1 {m['macro_f1']:.3f}  ECE {m['ece']:.3f}  pred {m['pred_counts']}")
    print("gold dev", res["dev"]["direct"]["gold_counts"], "| tau", round(tau, 3), "| grounding downgrades (dev):", res["grounding_effect_dev"])
    print("curve", [(c["abstain_pct"], round(c["accuracy"], 3)) for c in res["dev_coverage_curve"]])
    print("cost", res["cost"], "->", name)


if __name__ == "__main__":
    main()
