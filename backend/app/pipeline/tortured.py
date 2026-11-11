"""Check ⑤: tortured phrases, the synonym-swapped jargon left by paraphrasing tools ("counterfeit consciousness"
for "artificial intelligence"), a known fingerprint of paper-mill text (Cabanac, Labbé & Magazinov 2021).

Fingerprints: app/data/tortured_phrases.csv (documented examples from the 2021 paper plus the CC-BY-4.0
social-science list, Zenodo 14753785). Matching is case-insensitive on whole words, allowing any whitespace
or line break between words. A hit is a reason to read the passage, not proof of misconduct.
"""

import csv
import re
from functools import lru_cache
from pathlib import Path

from ..models import TorturedHit

DATA = Path(__file__).resolve().parents[1] / "data" / "tortured_phrases.csv"
MAX_PER_PHRASE = 2
SNIPPET = 90


@lru_cache
def fingerprints() -> list[tuple[str, str, re.Pattern]]:
    out = []
    with DATA.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            words = [re.escape(w) for w in row["fingerprint"].split()]
            out.append((row["fingerprint"], row["expected"], re.compile(r"\b" + r"[\s-]+".join(words) + r"\b", re.I)))
    return out


def scan(text: str | None) -> list[TorturedHit]:
    if not text:
        return []
    flat = re.sub(r"\s+", " ", text)
    hits = []
    for phrase, expected, pat in fingerprints():
        for k, m in enumerate(pat.finditer(flat)):
            if k == MAX_PER_PHRASE:
                break
            a, b = max(0, m.start() - SNIPPET), min(len(flat), m.end() + SNIPPET)
            snippet = ("…" if a else "") + flat[a:b].strip() + ("…" if b < len(flat) else "")
            hits.append(TorturedHit(phrase=m.group(0), expected=expected, snippet=snippet))
    return hits
