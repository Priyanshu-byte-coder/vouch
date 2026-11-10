"""Small text helpers shared by resolvers and the matcher."""

import html
import re
import unicodedata

from .models import ParsedRef

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
_REF_NUMBER = re.compile(r"^\s*(?:\[\d+\]|\d+\.|\(\d+\))\s*")
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
_PARTICLES = {"van", "von", "der", "den", "de", "del", "della", "di", "da", "du", "la", "le", "bin", "al", "el", "ter", "ten"}


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    d = _DOI_PREFIX.sub("", doi.strip()).strip().rstrip(".,;)").lower()
    return d or None


def fold(text: str) -> str:
    """Remove accents: 'Gražulis' -> 'Grazulis'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def surname_first(family: str | None = None, given: str | None = None, full: str | None = None) -> str:
    """Format structured name parts as 'Surname, Given'.

    Without a family name, `full` is returned unchanged: Crossref/DataCite use that field for
    organisations ("ATLAS Collaboration") or for names already written "Surname, Given"."""
    if family:
        return f"{family.strip()}, {given.strip()}" if given and given.strip() else family.strip()
    return re.sub(r"\s+", " ", (full or "").strip())


def name_from_display(name: str) -> str:
    """'Ashish Vaswani' -> 'Vaswani, Ashish'; 'Ludwig van Beethoven' -> 'van Beethoven, Ludwig'.
    Names already in 'Surname, Given' form are returned unchanged."""
    name = re.sub(r"\s+", " ", name.strip())
    if not name or "," in name:
        return name
    tokens = name.split(" ")
    while len(tokens) > 1 and tokens[-1].lower() in _SUFFIXES:
        tokens = tokens[:-1]
    if len(tokens) == 1:
        return tokens[0]
    i = len(tokens) - 1
    while i > 1 and tokens[i - 1].lower() in _PARTICLES:
        i -= 1
    return f"{' '.join(tokens[i:])}, {' '.join(tokens[:i])}"


def strip_tags(text: str | None) -> str | None:
    if not text:
        return None
    out = re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", text))).strip()
    return out or None


def clean_for_query(text: str) -> str:
    """Make a title safe for search endpoints: drop LaTeX, braces and punctuation."""
    t = _LATEX_CMD.sub(" ", text)
    t = re.sub(r"[{}$\\^_~]", " ", t)
    t = re.sub(r"[^\w\s'-]", " ", t, flags=re.UNICODE)
    return re.sub(r"\s+", " ", t).strip()


def strip_ref_number(raw: str) -> str:
    return _REF_NUMBER.sub("", raw).strip()


def reconstruct_abstract(inverted: dict | None) -> str | None:
    """OpenAlex stores abstracts as {word: [positions]}."""
    if not inverted:
        return None
    pos = {i: w for w, idxs in inverted.items() for i in idxs}
    return " ".join(pos[i] for i in sorted(pos)) or None


def first_surname(ref: ParsedRef) -> str | None:
    if not ref.authors:
        return None
    a = ref.authors[0]
    return (a.split(",")[0] if "," in a else a.split(" ")[-1]).strip() or None


def bibliographic_query(ref: ParsedRef) -> str:
    """Free-text query for 'bibliographic' search endpoints (title + first author + year)."""
    if ref.title:
        parts = [ref.title, first_surname(ref) or "", str(ref.year or "")]
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    return strip_ref_number(ref.raw)


def title_query(ref: ParsedRef) -> str:
    """Title-only query; falls back to the raw reference text."""
    return clean_for_query(ref.title or strip_ref_number(ref.raw))
