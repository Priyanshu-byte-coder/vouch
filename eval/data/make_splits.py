"""Build dev/test splits for RQ1 (step 1.2).

- test_citeaudit300: CiteAudit-300 as released by AtomGPT (the baseline's published test set)
- test_neurips100:   100 confirmed fabricated citations from NeurIPS 2025
- dev_full:          CiteAudit minus anything that duplicates (exactly or nearly) a test item
- dev_1000:          stratified, seeded sample of dev_full for threshold tuning within the API budget

Run from the repo root:
    backend/.venv/Scripts/python eval/data/make_splits.py
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import SPLITS, citation_hash, load_records, normalize_citation  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

SEED = 20261110
NEAR_DUP = 95  # token_sort_ratio threshold for near-duplicates
DEV_SAMPLE = 1000


def write(name: str, source: str, rows: list[dict], indices: list[int], note: str) -> None:
    SPLITS.mkdir(parents=True, exist_ok=True)
    items = [{"index": i, "hash": citation_hash(rows[i]["citation"]), "GT": rows[i]["GT"],
              "source_type": rows[i].get("source_type")} for i in indices]
    spec = {"name": name, "source": source, "seed": SEED, "n": len(items), "note": note,
            "GT_counts": dict(Counter(str(x["GT"]) for x in items)),
            "source_type_counts": dict(Counter(str(x["source_type"]) for x in items)), "items": items}
    (SPLITS / f"{name}.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    print(f"{name:18s} n={len(items):5d}  GT={spec['GT_counts']}  types={spec['source_type_counts']}")


def main() -> None:
    ca, c300, n100 = load_records("citeaudit"), load_records("citeaudit300"), load_records("neurips100")

    test_norm = [normalize_citation(r["citation"]) for r in c300 + n100]
    test_hashes = {citation_hash(r["citation"]) for r in c300 + n100}

    exact, near, keep = [], [], []
    for i, r in enumerate(ca):
        if citation_hash(r["citation"]) in test_hashes:
            exact.append(i)
            continue
        best = process.extractOne(normalize_citation(r["citation"]), test_norm,
                                  scorer=fuzz.token_sort_ratio, score_cutoff=NEAR_DUP)
        (near if best else keep).append(i)

    # How much of CiteAudit-300 is literally inside CiteAudit (sanity check of provenance)
    ca_hashes = {citation_hash(r["citation"]) for r in ca}
    in_ca = sum(citation_hash(r["citation"]) in ca_hashes for r in c300)
    n100_in_ca = sum(citation_hash(r["citation"]) in ca_hashes for r in n100)
    print(f"CiteAudit-300 items found verbatim in CiteAudit: {in_ca}/300 · NeurIPS-100 in CiteAudit: {n100_in_ca}/100")
    print(f"Removed from dev: {len(exact)} exact + {len(near)} near-duplicates (token_sort_ratio ≥ {NEAR_DUP})\n")

    write("test_citeaudit300", "citeaudit300", c300, list(range(len(c300))),
          "Baseline's published test set (AtomGPT data/citeaudit_300.json). Never tune on it.")
    write("test_neurips100", "neurips100", n100, list(range(len(n100))),
          "Confirmed fabricated citations in accepted NeurIPS 2025 papers. Never tune on it.")
    write("dev_full", "citeaudit", ca, keep,
          "CiteAudit minus exact and near duplicates of any test item.")

    # Stratified sample: equal real/fake, preserving the generated/realworld mix within each class
    rng = random.Random(SEED)
    strata: dict[tuple, list[int]] = {}
    for i in keep:
        strata.setdefault((ca[i]["GT"], ca[i].get("source_type")), []).append(i)
    per_class = DEV_SAMPLE // 2
    sample = []
    for gt in (True, False):
        cls = {k: v for k, v in strata.items() if k[0] == gt}
        total = sum(len(v) for v in cls.values())
        for k, idx in sorted(cls.items(), key=lambda kv: str(kv[0])):
            take = round(per_class * len(idx) / total)
            sample += rng.sample(idx, min(take, len(idx)))
    write("dev_1000", "citeaudit", ca, sorted(sample),
          "Stratified seeded sample of dev_full (balanced real/fake) for tuning within API budgets.")


if __name__ == "__main__":
    main()
