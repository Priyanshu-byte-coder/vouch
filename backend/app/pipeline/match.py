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


# Records that are notices *about* a paper, not the paper itself
_NOTICE = re.compile(r"^\s*(?:retraction note|retraction notice|notice of retraction|retracted article|retracted|retraction|"
                     r"correction to|correction|erratum to|erratum|corrigendum to|corrigendum|expression of concern|"
                     r"editorial expression of concern|withdrawn|withdrawal)\s*[:\-–—]\s*", re.IGNORECASE)


def strip_notice_prefix(t: str | None) -> str:
    return _NOTICE.sub("", t or "")


def is_notice(t: str | None) -> bool:
    return bool(_NOTICE.match(t or ""))


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
    """Return (surname_key, given-name initials) from 'Smith, John A.', 'J. A. Smith', 'Smith JA', 'John Smith'."""
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
    given = fold(given)
    # "JR" (packed initials) -> "jr"; "John A." / "J.-P." -> "ja" / "jp"
    if re.fullmatch(r"[A-Z]{2,3}\.?", given.strip()):
        initials = given.strip().lower()
    else:
        initials = "".join(w[0].lower() for w in re.split(r"[\s.\-]+", given) if w and w[0].isalpha())
    return (key, initials.rstrip(".")) if key else None


def _same_person(a: tuple[str, str], b: tuple[str, str]) -> bool:
    (sa, ia), (sb, ib) = a, b
    same_surname = sa == sb or (min(len(sa), len(sb)) > 3 and (sa in sb or sb in sa))
    if not same_surname:
        return False
    # Initials agree if either is unknown, the first initials match, or one person's first initial appears among
    # the other's (people often drop or reorder a first name: "Mohammad Samar Ansari" vs "Samar Ansari").
    return not ia or not ib or ia[0] == ib[0] or ia[0] in ib or ib[0] in ia


def author_score(cited: list[str], cand: list[str]) -> float | None:
    """0-100: share of cited authors found in the record (surname + compatible initials).
    'et al.' entries are ignored, so a truncated list is not penalised."""
    people = [p for p in (parse_person(a) for a in cited if not _ETAL.fullmatch(a.strip())) if p]
    record = [p for p in (parse_person(a) for a in cand) if p]
    if not people or not record:
        return None
    matched = sum(any(_same_person(p, r) for r in record) for p in people)
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

NOTICE_PENALTY = 10.0  # composite points: prefer the original paper over a notice about it


@dataclass
class Scored:
    candidate: Candidate
    scores: FieldScores
    issues: list[str] = field(default_factory=list)
    doi_match: bool = False
    notice: bool = False


def composite(s: FieldScores, weights: dict[str, float] = WEIGHTS, notice: bool = False) -> float | None:
    """Weighted mean over the fields that are present (weights renormalised)."""
    parts = {"title": s.title, "authors": s.authors, "venue": s.venue,
             "year": None if s.year is None else 100 * s.year}
    present = {k: v for k, v in parts.items() if v is not None}
    total_w = sum(weights[k] for k in present)
    if not total_w:
        return None
    value = round(sum(weights[k] * v for k, v in present.items()) / total_w, 1)
    return max(0.0, value - NOTICE_PENALTY) if notice else value


def score_candidate(ref: ParsedRef, cand: Candidate, weights: dict[str, float] = WEIGHTS) -> Scored:
    notice = is_notice(cand.title) and not is_notice(ref.title)
    s = FieldScores(title=title_score(ref.title, strip_notice_prefix(cand.title) if notice else cand.title),
                    authors=author_score(ref.authors, cand.authors),
                    venue=venue_score(ref.venue, cand.venue), year=year_score(ref.year, cand.year))
    s.composite = composite(s, weights, notice)

    issues = []
    if notice and s.composite is not None:
        issues.append(f"best record is a notice about the work: '{cand.title[:80]}'")
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
    return Scored(cand, s, issues, doi_match, notice)


def select_best(scored: list[Scored]) -> Scored | None:
    """Pick the record that best explains the reference.

    If the cited DOI resolves, that record is what the reference points to, so it wins even with a
    low title score (that is how identifier hijacking gets reported). The exception is when some other
    record matches the title almost exactly: then the work exists and only the DOI is wrong."""
    if not scored:
        return None
    # tie-break by year agreement (up to 0.5 points) so the right-year copy/edition wins among equals
    best = max(scored, key=lambda x: (x.scores.composite or 0) + (5 if x.doi_match and (x.scores.title or 0) >= 85 else 0)
               + 0.5 * (x.scores.year or 0))
    doi_hits = [x for x in scored if x.doi_match]
    if doi_hits and not best.doi_match and (best.scores.title or 0) < 90:
        return max(doi_hits, key=lambda x: x.scores.composite or 0)
    return best


def best_match(ref: ParsedRef, candidates: list[Candidate], weights: dict[str, float] = WEIGHTS) -> Scored | None:
    return select_best([score_candidate(ref, c, weights) for c in candidates])
