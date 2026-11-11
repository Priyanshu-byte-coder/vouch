"""Minimal LaTeX handling for arXiv sources: text cleanup, .bbl entries, .bib entries, \\cite contexts."""

import logging
import re
import unicodedata

import bibtexparser
from bibtexparser.bparser import BibTexParser

from ..models import ParsedRef, RefType
from ..text import name_from_display, normalize_doi

logging.getLogger("bibtexparser").setLevel(logging.ERROR)  # it logs every duplicate @string as a warning

_ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304", ".": "\u0307",
            "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a"}
_SPECIAL = {r"\ss": "ss", r"\o": "o", r"\O": "O", r"\aa": "a", r"\AA": "A", r"\ae": "ae", r"\AE": "AE",
            r"\l": "l", r"\L": "L", r"\i": "i", r"\oe": "oe", r"\&": "&", r"\%": "%", r"\$": "$", r"\_": "_",
            r"\#": "#", "---": "—", "--": "–", "``": '"', "''": '"'}
_KEEP_ARG = r"(?:emph|textit|textbf|textsc|textrm|texttt|textsf|mbox|text|mathrm|mathit|mathbf|bibinfo\s*\{[^}]*\}|bibfield\s*\{[^}]*\}|em|bf|it|sc|url|path|doi|BIBentryALTinterwordspacing|BIBentrySTDinterwordspacing)"


def _accent(m: re.Match) -> str:
    return unicodedata.normalize("NFC", m.group(2) + _ACCENTS[m.group(1)])


def latex_to_text(s: str) -> str:
    """Turn a LaTeX snippet into plain text (good enough for references and sentences)."""
    s = re.sub(r"(?<!\\)%.*", "", s)                                    # comments
    s = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:newblock|bibitem|penalty\d*|allowbreak|relax|protect|nobreak|ignorespaces)\b", " ", s)
    # RevTeX (APS) bibliographies: \BibitemOpen, \BibitemShut {NoStop}, \href@noop {} {...}, \doibase
    s = re.sub(r"\\BibitemShut\s*\{[^}]*\}|\\BibitemOpen|\\doibase\s*\{?[^\s}]*\}?|\\href@noop\s*\{\}|@noop", " ", s)
    s = re.sub(r"\\(?:bibinfo|bibfield)\s*\{[^}]*\}", " ", s)              # drop the field name, keep {content}
    s = re.sub(r"\\([`'^\"~=.uvHckr])\s*\{?\\?([A-Za-z])\}?", _accent, s)  # \"{o}, \'e, \c{c}
    for k, v in _SPECIAL.items():
        s = s.replace("{" + k + "}", v).replace(k + "{}", v)
    for k, v in _SPECIAL.items():
        s = re.sub(re.escape(k) + r"(?![A-Za-z])", v, s)
    s = re.sub(r"\{\\" + _KEEP_ARG + r"\s+([^{}]*)\}", r"\1", s)     # {\em x}
    for _ in range(3):                                                  # \emph{x}, nested
        s = re.sub(r"\\" + _KEEP_ARG + r"\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", s)                # remaining commands
    s = s.replace("~", " ").replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", s).strip(" ,.;") + ("." if s.strip().endswith(".") else "")


# ------------------------------------------------------------------ .bbl

_BIBITEM = re.compile(r"\\bibitem\s*(?:\[(?:[^\[\]]|\[[^\]]*\])*\])?\s*\{([^}]+)\}")


def parse_bbl(text: str) -> list[tuple[str, str]]:
    """Return [(key, plain-text reference)] in printed order."""
    body = text.split(r"\end{thebibliography}")[0]
    items = list(_BIBITEM.finditer(body))
    out = []
    for m, nxt in zip(items, items[1:] + [None]):
        chunk = body[m.end(): nxt.start() if nxt else len(body)]
        raw = latex_to_text(chunk)
        if len(raw) > 10:
            out.append((m.group(1).strip(), raw))
    return out


# ------------------------------------------------------------------ .bib

_BIB_TYPES = {"article": RefType.article, "inproceedings": RefType.conference, "conference": RefType.conference,
              "proceedings": RefType.conference, "book": RefType.book, "inbook": RefType.chapter,
              "incollection": RefType.chapter, "phdthesis": RefType.thesis, "mastersthesis": RefType.thesis,
              "techreport": RefType.report, "misc": RefType.other, "online": RefType.web, "software": RefType.software,
              "dataset": RefType.dataset, "unpublished": RefType.other}


def parse_bib(text: str) -> dict[str, dict]:
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    parser.homogenise_fields = True
    try:
        db = bibtexparser.loads(text, parser=parser)
    except Exception:  # noqa: BLE001 - malformed .bib files are common; fall back to .bbl
        return {}
    return {e["ID"]: e for e in db.entries if "ID" in e}


def bib_to_ref(idx: int, key: str, e: dict) -> ParsedRef:
    clean = lambda v: latex_to_text(v) if v else None  # noqa: E731
    authors = [name_from_display(clean(a) or "") for a in re.split(r"\s+and\s+", e.get("author", "")) if a.strip()]
    authors = [a for a in authors if a and a.lower() not in ("others", "et al")]
    title, venue = clean(e.get("title")), clean(e.get("journal") or e.get("booktitle") or e.get("publisher")
                                                 or e.get("howpublished") or e.get("school") or e.get("institution"))
    year = None
    if m := re.search(r"(19|20)\d\d", e.get("year", "") or e.get("date", "")):
        year = int(m.group(0))
    arxiv_id = e.get("eprint") if (e.get("archiveprefix", "").lower() == "arxiv" or re.fullmatch(r"\d{4}\.\d{4,5}", e.get("eprint", ""))) else None
    rtype = _BIB_TYPES.get(e.get("ENTRYTYPE", "").lower(), RefType.other)
    if arxiv_id and rtype is RefType.other:
        rtype = RefType.preprint
    parts = [", ".join(authors[:6]) + (" et al." if len(authors) > 6 else ""), title, venue, str(year or "")]
    raw = ". ".join(p for p in parts if p)
    return ParsedRef(idx=idx, raw=raw, title=title, authors=authors, year=year, venue=venue,
                     doi=normalize_doi(e.get("doi")), arxiv_id=arxiv_id, isbn=e.get("isbn"), url=e.get("url"),
                     type_guess=rtype, key=key)


# ------------------------------------------------------------------ \cite contexts

_CITE = re.compile(r"\\(?:[a-zA-Z]*cite[a-zA-Z]*\*?|citealp|citet|citep|autocite|parencite|textcite)"
                   r"(?:\[[^\]]*\]){0,2}\{([^}]+)\}")


def strip_tex_noise(tex: str) -> str:
    tex = re.sub(r"(?<!\\)%.*", "", tex)
    tex = re.sub(r"\\begin\{(equation|align|figure|table|tabular|algorithm|lstlisting|verbatim)\*?\}.*?"
                 r"\\end\{\1\*?\}", " ", tex, flags=re.S)
    return tex


def cite_order_and_contexts(tex: str, max_per_key: int = 3) -> tuple[list[str], dict[str, list[str]]]:
    """Cited keys in order of first appearance, and up to N citing sentences per key."""
    tex = strip_tex_noise(tex)
    text = re.sub(r"\s+", " ", tex)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z\\])", text)
    order: list[str] = []
    contexts: dict[str, list[str]] = {}
    for sent in sentences:
        keys = [k.strip() for m in _CITE.finditer(sent) for k in m.group(1).split(",") if k.strip()]
        if not keys:
            continue
        plain = latex_to_text(_CITE.sub("[CITATION]", sent))
        for k in keys:
            if k not in contexts:
                order.append(k)
                contexts[k] = []
            if len(contexts[k]) < max_per_key and 20 <= len(plain) <= 800 and plain not in contexts[k]:
                contexts[k].append(plain)
    return order, contexts
