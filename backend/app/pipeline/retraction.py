"""Check ③: was the cited work retracted, corrected, or given an expression of concern?

Data: the Retraction Watch database (Crossref, open, updated daily). Matched by DOI first (the cited
DOI and the DOI of the record we matched), then PubMed ID, then exact long-title match as a fallback.
"""

import csv
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import httpx

from ..config import ROOT
from ..models import RetractionInfo
from ..text import normalize_doi
from .match import norm_title, strip_notice_prefix

CSV_URL = "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
CANDIDATE_PATHS = [ROOT / "eval" / "data" / "raw" / "retraction_watch" / "retraction_watch.csv",
                   ROOT / "cache" / "retraction_watch.csv"]

SEVERITY = {"Retraction": 3, "Expression of concern": 2, "Correction": 1, "Reinstatement": 0}
# Book-keeping reasons that say nothing about the paper itself
_META_REASONS = {"updated to retraction", "upgrade/update of prior notice(s)", "notice - unable to access via current resources",
                 "notice - limited or no information", "date of retraction/other unknown"}
_MIN_TITLE_WORDS = 6  # shorter titles collide too often for a title-only match


def _date(s: str) -> str | None:
    s = (s or "").split(" ")[0]
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _reasons(s: str) -> list[str]:
    out = []
    for r in (s or "").split(";"):
        r = r.strip().lstrip("+").strip()
        if r and r.lower() not in _META_REASONS:
            out.append(r)
    return out


class RetractionIndex:
    def __init__(self, rows: list[dict]):
        self.by_doi: dict[str, list[dict]] = {}
        self.by_pmid: dict[str, list[dict]] = {}
        self.by_title: dict[str, list[dict]] = {}
        self.notice_to_original: dict[str, str] = {}  # retraction-notice DOI -> original paper DOI
        for row in rows:
            n = {"nature": row.get("RetractionNature", "").strip(), "date": _date(row.get("RetractionDate", "")),
                 "reasons": _reasons(row.get("Reason", "")), "notice_doi": normalize_doi(row.get("RetractionDOI")),
                 "urls": [u for u in (row.get("URLS") or "").split(";") if u.startswith("http")],
                 "title": row.get("Title", "")}
            if n["nature"] not in SEVERITY:
                continue
            if (doi := normalize_doi(row.get("OriginalPaperDOI"))) and doi.startswith("10."):
                self.by_doi.setdefault(doi, []).append(n)
                if n["notice_doi"] and n["notice_doi"].startswith("10."):
                    self.notice_to_original[n["notice_doi"]] = doi
            if (pmid := (row.get("OriginalPaperPubMedID") or "").strip()) not in ("", "0"):
                self.by_pmid.setdefault(pmid, []).append(n)
            t = norm_title(n["title"])
            if len(t.split()) >= _MIN_TITLE_WORDS:
                self.by_title.setdefault(t, []).append(n)

    @classmethod
    def from_csv(cls, path: Path) -> "RetractionIndex":
        with open(path, encoding="utf-8", newline="") as f:
            return cls(list(csv.DictReader(f)))

    def __len__(self) -> int:
        return len(self.by_doi)

    @staticmethod
    def _resolve(notices: list[dict]) -> RetractionInfo:
        """The notice that matters now: a reinstatement dated after the last retraction wins,
        otherwise the most severe notice (latest if tied)."""
        ordered = sorted(notices, key=lambda n: n["date"] or "")
        retractions = [n for n in ordered if n["nature"] == "Retraction"]
        reinst = [n for n in ordered if n["nature"] == "Reinstatement"]
        if retractions and reinst and (reinst[-1]["date"] or "") > (retractions[-1]["date"] or ""):
            pick = reinst[-1]
        else:
            pick = max(ordered, key=lambda n: (SEVERITY[n["nature"]], n["date"] or ""))
        url = pick["urls"][0] if pick["urls"] else (f"https://doi.org/{pick['notice_doi']}" if pick["notice_doi"] else None)
        reasons = list(dict.fromkeys(r for n in ordered if n["nature"] == pick["nature"] for r in n["reasons"]))
        return RetractionInfo(nature=pick["nature"], date=pick["date"], reasons=reasons,
                              notice_doi=pick["notice_doi"], url=url)

    def lookup(self, dois: list[str | None] = (), pmid: str | None = None, title: str | None = None) -> RetractionInfo | None:
        for d in dois:
            d = normalize_doi(d)
            if d and d in self.by_doi:
                return self._resolve(self.by_doi[d])
            if d and d in self.notice_to_original:  # the record we matched IS the retraction notice
                return self._resolve(self.by_doi[self.notice_to_original[d]])
        if pmid and pmid in self.by_pmid:
            return self._resolve(self.by_pmid[pmid])
        if title and (hits := self.by_title.get(norm_title(strip_notice_prefix(title)))):
            return self._resolve(hits)
        return None


def ensure_data() -> Path:
    """Return a local copy of the Retraction Watch CSV, downloading it (~70 MB) if missing."""
    for p in CANDIDATE_PATHS:
        if p.exists() and p.stat().st_size > 1_000_000:
            return p
    dest = CANDIDATE_PATHS[-1]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", CSV_URL, timeout=300.0, follow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)
    return dest


@lru_cache
def get_index() -> RetractionIndex:
    return RetractionIndex.from_csv(ensure_data())


def describe(info: RetractionInfo) -> str:
    """One-line issue text for the report."""
    when = f" ({info.date})" if info.date else ""
    why = f": {'; '.join(info.reasons[:4])}" if info.reasons else ""
    label = {"Retraction": "cited work was RETRACTED", "Expression of concern": "cited work has an EXPRESSION OF CONCERN",
             "Correction": "cited work has a published correction", "Reinstatement": "cited work was retracted and later reinstated"}
    return re.sub(r"\s+", " ", f"{label[info.nature]}{when}{why}")
