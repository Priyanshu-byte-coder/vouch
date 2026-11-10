"""Split a bibliography into references and parse each into fields.

The LLM extracts title/authors/year/venue/type. Identifiers (DOI, arXiv ID, ISBN, URL) are taken
only from the raw text by regex, so the parser can never invent an identifier that would send the
checker to the wrong paper.
"""

import re

from ..llm import LLMJSONError, chat_json
from ..models import ParsedRef, RefType
from ..text import normalize_doi, strip_ref_number

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
ARXIV_RE = re.compile(r"(?:arxiv[:\s/]*(?:abs/)?|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?",
                      re.IGNORECASE)
ISBN_RE = re.compile(r"\bISBN(?:-1[03])?:?\s*([0-9Xx][0-9Xx\- ]{8,16}[0-9Xx])")
URL_RE = re.compile(r"https?://[^\s<>\"]+")
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
_NUMBERED = re.compile(r"^\s*(?:\[\d{1,4}\]|\d{1,4}\.\s|\(\d{1,4}\))", re.MULTILINE)

BATCH = 8
_SYSTEM = """You extract bibliographic fields from reference strings. For each reference return an object with:
title (string or null), authors (list of "Surname, Initials"; omit "et al."), year (integer or null),
venue (journal/conference/publisher/"arXiv", or null),
type (one of: article, conference, preprint, book, chapter, report, thesis, dataset, software, web, other).
Copy the title exactly as written (fix only hyphenation from line breaks). Never invent missing fields: use null.
Reply with ONLY a JSON array, one object per reference, in the same order."""


def split_bibliography(text: str) -> list[str]:
    """Split on [1]/1./(1) markers if present, else on blank lines, else one reference per line."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    starts = [m.start() for m in _NUMBERED.finditer(text)]
    if len(starts) >= 2:
        chunks = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    elif "\n\n" in text:
        chunks = re.split(r"\n\s*\n", text)
    else:
        chunks = text.split("\n")
    refs = [re.sub(r"\s+", " ", c).strip() for c in chunks]
    return [r for r in refs if len(r) >= 15]


def identifiers(raw: str) -> dict:
    """Deterministic identifier extraction from the raw reference text."""
    doi = None
    if m := DOI_RE.search(raw):
        doi = normalize_doi(m.group(1))
    arxiv_id = None
    if m := ARXIV_RE.search(raw):
        arxiv_id = m.group(1)
    elif doi and doi.startswith("10.48550/arxiv."):
        arxiv_id = doi.split("arxiv.", 1)[1]
    isbn = re.sub(r"[\s-]", "", m.group(1)) if (m := ISBN_RE.search(raw)) else None
    urls = [u.rstrip(".,;)") for u in URL_RE.findall(raw) if "doi.org" not in u and "arxiv.org" not in u]
    return {"doi": doi, "arxiv_id": arxiv_id, "isbn": isbn, "url": urls[0] if urls else None}


def _coerce(idx: int, raw: str, d: dict | None) -> ParsedRef:
    d = d if isinstance(d, dict) else {}
    year = d.get("year")
    try:
        year = int(str(year)[:4]) if year else None
    except ValueError:
        year = None
    if year is None and (m := YEAR_RE.search(raw)):
        year = int(m.group(1))
    try:
        rtype = RefType(str(d.get("type") or "other").lower())
    except ValueError:
        rtype = RefType.other
    ids = identifiers(raw)
    if ids["arxiv_id"] and rtype is RefType.other:
        rtype = RefType.preprint
    authors = [a.strip() for a in d.get("authors") or [] if isinstance(a, str) and a.strip()
               and not re.fullmatch(r"et\.? ?al\.?", a.strip(), re.IGNORECASE)]
    title = (d.get("title") or "").strip() or None
    return ParsedRef(idx=idx, raw=raw, title=title, authors=authors, year=year,
                     venue=(d.get("venue") or None), type_guess=rtype, **ids)


async def parse_references(raws: list[str]) -> list[ParsedRef]:
    """Parse references with the LLM in batches; falls back to identifiers-only on failure."""
    out: list[ParsedRef] = []
    for start in range(0, len(raws), BATCH):
        batch = raws[start:start + BATCH]
        listing = "\n".join(f"{i + 1}. {strip_ref_number(r)}" for i, r in enumerate(batch))
        try:
            parsed = await chat_json(f"References:\n{listing}", system=_SYSTEM, max_tokens=350 * len(batch) + 200)
            if isinstance(parsed, dict):  # some models wrap the array
                parsed = next((v for v in parsed.values() if isinstance(v, list)), [parsed])
        except LLMJSONError:
            parsed = []
        parsed = parsed if isinstance(parsed, list) and len(parsed) == len(batch) else [None] * len(batch)
        out += [_coerce(start + i, raw, d) for i, (raw, d) in enumerate(zip(batch, parsed))]
    return out
