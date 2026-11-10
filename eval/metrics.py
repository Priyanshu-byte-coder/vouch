"""Detection metrics shared by every RQ1 script.

Convention (same as the AtomGPT baseline): a FAKE citation is the positive class.
A citation is "flagged" when the system does not mark it verified.
"""

import random


def confusion(gt_real: list[bool], flagged: list[bool]) -> dict:
    tp = sum(f and not g for g, f in zip(gt_real, flagged))
    fn = sum((not f) and (not g) for g, f in zip(gt_real, flagged))
    fp = sum(f and g for g, f in zip(gt_real, flagged))
    tn = sum((not f) and g for g, f in zip(gt_real, flagged))
    return {"TP": tp, "FN": fn, "FP": fp, "TN": tn}


def scores(c: dict) -> dict:
    tp, fn, fp, tn = c["TP"], c["FN"], c["FP"], c["TN"]
    n = tp + fn + fp + tn
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else None
    return {"n": n, "precision": p, "recall": r, "f1": f1,
            "fpr": fp / (fp + tn) if fp + tn else None,
            "accuracy": (tp + tn) / n if n else None, **c}


def evaluate(gt_real: list[bool], flagged: list[bool]) -> dict:
    return scores(confusion(gt_real, flagged))


def bootstrap_ci(gt_real: list[bool], flagged: list[bool], metric: str = "f1",
                 n_boot: int = 2000, seed: int = 20261110) -> tuple[float, float] | None:
    """95% percentile bootstrap CI for one metric (resampling citations)."""
    rng = random.Random(seed)
    idx = list(range(len(gt_real)))
    vals = []
    for _ in range(n_boot):
        s = [rng.choice(idx) for _ in idx]
        v = evaluate([gt_real[i] for i in s], [flagged[i] for i in s])[metric]
        if v is not None:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def fmt(m: dict) -> str:
    f = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
    return (f"n={m['n']} P={f(m['precision'])} R={f(m['recall'])} F1={f(m['f1'])} "
            f"FPR={f(m['fpr'])} Acc={f(m['accuracy'])} (TP={m['TP']} FN={m['FN']} FP={m['FP']} TN={m['TN']})")
