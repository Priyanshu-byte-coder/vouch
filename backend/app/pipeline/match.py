"""Field-level matching of a parsed reference against candidate records.

Designed against the documented weaknesses of single-source checkers:
- short titles over-matching longer ones (token_set_ratio gives "Deep learning" 100 vs "PyTorch: ... Deep Learning")
- diacritics, hyphenated surnames, "et al.", surname-first vs given-first author formats
- venue abbreviations ("Phys. Rev. Lett." vs "Physical Review Letters", NIPS vs NeurIPS)
- a real DOI attached to a different paper (identifier hijacking)
"""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from ..models import Candidate, FieldScores, ParsedRef
from ..text import fold, normalize_doi

WEIGHTS = {"title": 0.55, "authors": 0.30, "venue": 0.10, "year": 0.05}

# ---------------------------------------------------------------- titles

_LATEX = re.compile(r"\\[a-zA-Z]+\*?|[{}$]")


def norm_title(t: str | None) -> str:
    t = _LATEX.sub(" ", fold(t or "")).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_score(cited: str | None, cand: str | None) -> float | None:
    """0-100. Order-insensitive, but extra or missing words cost points (unlike token_set_ratio),
    except when one title is a clean prefix of the other (subtitle omitted or title truncated)."""
    a, b = norm_title(cited), norm_title(cand)
    if not a or not b:
        return None
    if a == b:
        return 100.0
    short, long_ = sorted((a, b), key=len)
    if len(short.split()) >= 4 and long_.startswith(short + " "):
        return 95.0
    score = fuzz.token_sort_ratio(a, b)
    wa, wb = len(a.split()), len(b.split())
    if min(wa, wb) / max(wa, wb) >= 0.75:  # similar length: tolerate reordering / small insertions
        score = max(score, fuzz.token_set_ratio(a, b) - 5)
    return float(score)


# ---------------------------------------------------------------- authors

_ETAL = re.compile(r"\bet\.?\s*al\.?|\band others\b|\.\.\.", re.IGNORECASE)


def _surname_key(s: str) -> str:
    return re.sub(r"[^a-z]", "", fold(s).lower())


def parse_person(name: str) -> tuple[str, str] | None:
    """Return (surname_key, first_initial) from 'Smith, John', 'J. Smith', 'Smith J', 'John Smith'."""
    name = re.sub(r"\s+", " ", _ETAL.sub("", name)).strip(" ,;")
    if not name:
        return None
    if "," in name:
        surname, given = (p.strip() for p in name.split(",", 1))
    else:
        tokens = name.split(" ")
        if len(tokens) == 1:
            return _surname_key(tokens[0]), ""
        # "Smith J" / "Smith JR": trailing token is initials
        if re.fullmatch(r"[A-Z]{1,3}\.?", tokens[-1]) and not re.fullmatch(r"[A-Z]\.?", tokens[0]):
            surname, given = " ".join(tokens[:-1]), tokens[-1]
        else:
            surname, given = tokens[-1], " ".join(tokens[:-1])
    key = _surname_key(surname)
    initial = fold(given.strip())[:1].lower()
    return (key, initial) if key else None


def author_score(cited: list[str], cand: list[str]) -> float | None:
    """0-100: share of cited authors found in the record (surname + first initial if both known).
    'et al.' entries are ignored, so a truncated list is not penalised."""
    people = [p for p in (parse_person(a) for a in cited if not _ETAL.fullmatch(a.strip())) if p]
    record = [p for p in (parse_person(a) for a in cand) if p]
    if not people or not record:
        return None
    matched = 0
    for surname, initial in people:
        for rs, ri in record:
            same_surname = surname == rs or (len(surname) > 3 and (surname in rs or rs in surname))
            if same_surname and (not initial or not ri or initial == ri):
                matched += 1
                break
    return 100.0 * matched / len(people)


# ---------------------------------------------------------------- venue / year

_ABBREV = {
    "adv": "advances", "inf": "information", "process": "processing", "syst": "systems", "proc": "proceedings",
    "conf": "conference", "int": "international", "intl": "international", "j": "journal", "jour": "journal",
    "trans": "transactions", "comput": "computing", "lett": "letters", "phys": "physical", "rev": "review",
    "sci": "science", "res": "research", "intell": "intelligence", "mach": "machine", "learn": "learning",
    "ling": "linguistics", "assoc": "association", "natl": "national", "acad": "academy", "eng": "engineering",
    "appl": "applied", "math": "mathematics", "stat": "statistics", "soc": "society", "am": "american",
    "med": "medicine", "biol": "biology", "chem": "chemistry", "neurosci": "neuroscience", "psychol": "psychology",
    "econ": "economics", "theor": "theoretical", "anal": "analysis", "artif": "artificial", "commun": "communications",
    "netw": "networks", "softw": "software", "technol": "technology", "manag": "management", "ann": "annals",
    "annu": "annual", "q": "quarterly", "mol": "molecular", "comp": "computer", "vis": "vision",
    "recogn": "recognition", "pattern": "pattern", "lang": "language", "nat": "natural",
}
_ALIASES = {
    "nips": "neural information processing systems", "neurips": "neural information processing systems",
    "icml": "international conference on machine learning", "iclr": "international conference on learning representations",
    "acl": "association for computational linguistics", "emnlp": "empirical methods in natural language processing",
    "naacl": "north american chapter of the association for computational linguistics",
    "cvpr": "computer vision and pattern recognition", "iccv": "international conference on computer vision",
    "eccv": "european conference on computer vision", "aaai": "aaai conference on artificial intelligence",
    "ijcai": "international joint conference on artificial intelligence", "kdd": "knowledge discovery and data mining",
    "pnas": "proceedings of the national academy of sciences", "jmlr": "journal of machine learning research",
    "tacl": "transactions of the association for computational linguistics",
}
_PREPRINT = {"arxiv", "corr", "preprint", "biorxiv", "medrxiv", "ssrn", "chemrxiv", "preprints", "techrxiv"}
_VENUE_NOISE = {"of", "the", "on", "in", "and", "for", "annual", "vol", "volume", "pp", "no", "ieee", "acm", "cvf"}


def norm_venue(v: str | None) -> str:
    v = fold(v or "").lower()
    v = re.sub(r"\b(19|20)\d\d\b|\b\d+\b", " ", v)  # years, volumes, pages
    words = re.findall(r"[a-z]+", v)
    out = []
    for w in words:
        out.extend((_ALIASES.get(w) or _ABBREV.get(w, w)).split())
    return " ".join(w for w in out if w not in _VENUE_NOISE)


def venue_score(cited: str | None, cand: str | None) -> float | None:
    a, b = norm_venue(cited), norm_venue(cand)
    if not a or not b or any(p in v.split() for v in (a, b) for p in _PREPRINT):
        return None  # preprint servers and missing venues are not evidence either way
    return float(fuzz.token_set_ratio(a, b))


def year_score(cited: int | None, cand: int | None) -> float | None:
    if not cited or not cand:
        return None
    d = abs(int(cited) - int(cand))
    return 1.0 if d == 0 else 0.5 if d == 1 else 0.0


# ---------------------------------------------------------------- combined

@dataclass
class Scored:
    candidate: Candidate
    scores: FieldScores
    issues: list[str] = field(default_factory=list)
    doi_match: bool = False


def score_candidate(ref: ParsedRef, cand: Candidate) -> Scored:
    s = FieldScores(title=title_score(ref.title, cand.title), authors=author_score(ref.authors, cand.authors),
                    venue=venue_score(ref.venue, cand.venue), year=year_score(ref.year, cand.year))
    parts = {"title": s.title, "authors": s.authors, "venue": s.venue,
             "year": None if s.year is None else 100 * s.year}
    present = {k: v for k, v in parts.items() if v is not None}
    total_w = sum(WEIGHTS[k] for k in present)
    s.composite = round(sum(WEIGHTS[k] * v for k, v in present.items()) / total_w, 1) if total_w else None

    issues = []
    doi_match = bool(ref.doi and cand.doi and normalize_doi(ref.doi) == cand.doi)
    if doi_match and (s.title or 0) < 85:
        issues.append(f"DOI {cand.doi} belongs to a different work: '{cand.title}'")
    if s.authors is not None and s.authors < 60:
        issues.append(f"authors differ: cited {', '.join(ref.authors[:4])} · record {', '.join(cand.authors[:4])}")
    if s.year == 0.0:
        issues.append(f"year {ref.year} vs record {cand.year}")
    elif s.year == 0.5:
        issues.append(f"year off by one: {ref.year} vs record {cand.year} (often preprint vs published)")
    if s.venue is not None and s.venue < 50:
        issues.append(f"venue '{ref.venue}' vs record '{cand.venue}'")
    if ref.doi and cand.doi and not doi_match and (s.title or 0) >= 90:
        issues.append(f"DOI cited as {normalize_doi(ref.doi)} but record has {cand.doi}")
    return Scored(cand, s, issues, doi_match)


def best_match(ref: ParsedRef, candidates: list[Candidate]) -> Scored | None:
    """Highest composite; a DOI that matches *and* agrees on title wins ties."""
    scored = [score_candidate(ref, c) for c in candidates]
    if not scored:
        return None
    return max(scored, key=lambda x: (x.scores.composite or 0) + (5 if x.doi_match and (x.scores.title or 0) >= 85 else 0))
