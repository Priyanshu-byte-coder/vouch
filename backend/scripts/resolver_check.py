"""Step 2.2 check: 5 known references against every source.

For each (reference, source) prints the best candidate and its title similarity.
Run from backend/:  .venv/Scripts/python scripts/resolver_check.py
"""

import asyncio
import sys
import time
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.models import ParsedRef, RefType  # noqa: E402
from app.pipeline.resolvers import SOURCES, SourceError, api_calls  # noqa: E402
from app.text import fold  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

REFS = {
    "article (DOI)": ParsedRef(idx=0, raw="LeCun Y, Bengio Y, Hinton G. Deep learning. Nature 521, 436-444 (2015).",
                               title="Deep learning", authors=["LeCun, Y.", "Bengio, Y.", "Hinton, G."], year=2015,
                               venue="Nature", doi="10.1038/nature14539", type_guess=RefType.article),
    "preprint (arXiv)": ParsedRef(idx=1, raw="Vaswani et al. Attention is all you need. arXiv:1706.03762, 2017.",
                                  title="Attention is all you need", authors=["Vaswani, A.", "Shazeer, N."],
                                  year=2017, arxiv_id="1706.03762", type_guess=RefType.preprint),
    "book": ParsedRef(idx=2, raw="Goodfellow I, Bengio Y, Courville A. Deep Learning. MIT Press, 2016.",
                      title="Deep Learning", authors=["Goodfellow, I.", "Bengio, Y.", "Courville, A."], year=2016,
                      venue="MIT Press", type_guess=RefType.book),
    "dataset (DataCite)": ParsedRef(
        idx=3, raw="Cabanac G, Labbé C, Magazinov A. Tortured phrases: A dubious writing style emerging in science. "
                   "Zenodo, 2021. doi:10.5281/zenodo.5031935",
        title="Tortured phrases: A dubious writing style emerging in science. Evidence of critical issues affecting "
              "established journals", authors=["Cabanac, G.", "Labbé, C.", "Magazinov, A."], year=2021,
        doi="10.5281/zenodo.5031935", type_guess=RefType.dataset),
    "FAKE": ParsedRef(idx=4, raw="Zhang W, Kumar R. Hierarchical contrastive attention networks for low-resource "
                                 "citation verification. ACL 2023.",
                      title="Hierarchical contrastive attention networks for low-resource citation verification",
                      authors=["Zhang, W.", "Kumar, R."], year=2023, venue="ACL", type_guess=RefType.conference),
}


def sim(a: str, b: str) -> float:
    """Strict title similarity (token_sort_ratio: word order-insensitive, but extra words cost)."""
    return fuzz.token_sort_ratio(fold(a).lower(), fold(b).lower())


def lenient(a: str, b: str) -> float:
    """The baseline's measure (token_set_ratio): a short title scores 100 against any superset."""
    return fuzz.token_set_ratio(fold(a).lower(), fold(b).lower())


def rank(ref: ParsedRef, c) -> float:
    surnames = {fold(a.split(",")[0]).lower() for a in ref.authors}
    cand = {fold(a.split(",")[0]).lower() for a in c.authors}
    authors = 100 * len(surnames & cand) / len(surnames) if surnames else 0
    doi = 100 if ref.doi and c.doi == ref.doi.lower() else 0
    return 0.6 * sim(ref.title or ref.raw, c.title) + 0.3 * authors + 0.1 * doi


async def run_one(label: str, ref: ParsedRef, name: str):
    t = time.perf_counter()
    try:
        cands = await SOURCES[name].find(ref, 5)
    except SourceError as e:
        return label, name, None, str(e), time.perf_counter() - t
    if not cands:
        return label, name, None, "no candidates", time.perf_counter() - t
    best = max(cands, key=lambda c: rank(ref, c))
    return label, name, best, len(cands), time.perf_counter() - t


async def main():
    calls = Counter()
    api_calls.set(calls)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(run_one(lbl, ref, n) for lbl, ref in REFS.items() for n in SOURCES))
    current = None
    for label, name, best, info, dt in results:
        if label != current:
            current = label
            print(f"\n=== {label}: {REFS[label].title[:70]}")
        if best is None:
            print(f"  {name:12s} {dt:5.1f}s  —  {info}")
        else:
            s, ls = sim(REFS[label].title, best.title), lenient(REFS[label].title, best.title)
            au = ", ".join(a.split(",")[0] for a in best.authors[:3])
            print(f"  {name:12s} {dt:5.1f}s  sim={s:5.1f} (baseline-style {ls:5.1f})  {best.title[:55]!r} · {au} · {best.year} "
                  f"· doi={best.doi} · {info} cands")
    print(f"\nTotal {time.perf_counter() - t0:.1f}s · API calls: {dict(calls)}")


if __name__ == "__main__":
    asyncio.run(main())
