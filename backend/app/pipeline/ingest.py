"""Turn an arXiv ID (or a PDF) into parsed references with citation contexts.

arXiv path: e-print source -> .bib entries for cited keys (structured, no LLM needed) ->
.bbl entries for the rest (LLM-parsed) -> contexts from \\cite commands in the .tex files.
If arXiv only has a PDF, GROBID extracts the references instead.
"""

import asyncio
import gzip
import io
import re
import tarfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import httpx

from ..config import ROOT, get_settings
from ..models import ParsedRef, RefType
from ..text import normalize_doi
from . import latex
from .parse_refs import identifiers, parse_references
from .resolvers import arxiv as arxiv_source
from .resolvers.base import SourceError, _throttle, api_calls, http

EPRINT_DIR = ROOT / "cache" / "arxiv"
TEI = {"t": "http://www.tei-c.org/ns/1.0"}


@dataclass
class Ingested:
    title: str | None
    refs: list[ParsedRef]
    method: str  # "bib", "bbl", "bib+bbl", "grobid"
    notes: list[str] = field(default_factory=list)
    text: str | None = None  # full text, for the tortured-phrase scan


ARXIV_ID = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z][a-z-]*(?:\.[A-Za-z]{2})?/\d{7})(?:v\d+)?$")


def is_arxiv_id(s: str) -> bool:
    """New-style (2602.23452, 2602.23452v2) or old-style (hep-th/9901001) arXiv identifier."""
    return bool(ARXIV_ID.match(s))


def normalize_arxiv_id(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^(?:https?://)?(?:www\.)?(?:export\.)?arxiv\.org/(?:abs|pdf)/", "", s, flags=re.I)
    s = re.sub(r"^arxiv:\s*", "", s, flags=re.I)
    s = re.sub(r"\.pdf$", "", s)
    return s


async def _download(url: str, what: str) -> bytes:
    """GET a binary from arXiv with throttling and retries (arXiv answers bursts with 429 / dropped connections)."""
    last = "no attempt"
    for attempt in range(5):
        host = url if attempt % 2 == 0 else url.replace("export.arxiv.org", "arxiv.org")
        await _throttle("arxiv")
        api_calls.get()["arxiv"] += 1
        try:
            r = await http().get(host, timeout=90.0)
        except httpx.HTTPError as e:
            last = type(e).__name__
            await asyncio.sleep(5 * 2 ** attempt)
            continue
        if r.status_code == 200 and r.content:
            return r.content
        last = f"HTTP {r.status_code}"
        if r.status_code == 404:
            break
        try:
            wait = float(r.headers.get("retry-after", ""))
        except ValueError:
            wait = 5 * 2 ** attempt
        await asyncio.sleep(min(wait, 60))
    raise SourceError(f"arxiv {what}: {last}")


async def fetch_eprint(arxiv_id: str) -> bytes:
    """Download (and cache on disk) the e-print: a tar.gz, a gzipped .tex, or a PDF."""
    EPRINT_DIR.mkdir(parents=True, exist_ok=True)
    path = EPRINT_DIR / (arxiv_id.replace("/", "_") + ".bin")
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    blob = await _download(f"https://export.arxiv.org/e-print/{arxiv_id}", "e-print")
    path.write_bytes(blob)
    return blob


async def fetch_pdf(arxiv_id: str) -> bytes:
    EPRINT_DIR.mkdir(parents=True, exist_ok=True)
    path = EPRINT_DIR / (arxiv_id.replace("/", "_") + ".pdf")
    if path.exists() and path.stat().st_size > 0:
        return path.read_bytes()
    blob = await _download(f"https://export.arxiv.org/pdf/{arxiv_id}", "pdf")
    path.write_bytes(blob)
    return blob


def unpack(blob: bytes) -> dict[str, str]:
    """Return {filename: text} for .tex/.bbl/.bib files, or {'__pdf__': ''} for a PDF-only e-print."""
    if blob[:4] == b"%PDF":
        return {"__pdf__": ""}
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tar:
            out = {}
            for m in tar.getmembers():
                if m.isfile() and m.name.lower().endswith((".tex", ".bbl", ".bib")) and m.size < 5_000_000:
                    f = tar.extractfile(m)
                    if f:
                        out[m.name] = f.read().decode("utf-8", errors="replace")
            return out
    except tarfile.TarError:
        pass
    try:  # single gzipped .tex
        return {"main.tex": gzip.decompress(blob).decode("utf-8", errors="replace")}
    except OSError:
        return {"main.tex": blob.decode("utf-8", errors="replace")}


async def from_latex(files: dict[str, str]) -> tuple[list[ParsedRef], str, list[str]]:
    tex = "\n".join(v for k, v in files.items() if k.lower().endswith(".tex"))
    bbl = "\n".join(v for k, v in files.items() if k.lower().endswith(".bbl"))
    bib: dict[str, dict] = {}
    for k, v in files.items():
        if k.lower().endswith(".bib"):
            bib.update(latex.parse_bib(v))
    order, contexts = latex.cite_order_and_contexts(tex)
    bbl_entries = latex.parse_bbl(bbl) if bbl else []
    notes: list[str] = []

    # Reference list = what was printed (.bbl) if available, else the cited keys
    keys = [k for k, _ in bbl_entries] or order
    bbl_raw = dict(bbl_entries)
    refs: list[ParsedRef] = []
    to_llm: list[tuple[int, str, str]] = []
    for i, key in enumerate(keys):
        if key in bib:
            r = latex.bib_to_ref(i, key, bib[key])
            if key in bbl_raw:
                r.raw = bbl_raw[key]  # show what the paper actually printed
                ids = identifiers(bbl_raw[key])
                r.doi = r.doi or ids["doi"]
                r.arxiv_id = r.arxiv_id or ids["arxiv_id"]
            refs.append(r)
        elif key in bbl_raw:
            to_llm.append((i, key, bbl_raw[key]))
    if to_llm:
        parsed = await parse_references([raw for _, _, raw in to_llm])
        for (i, key, _), p in zip(to_llm, parsed):
            p.idx, p.key = i, key
            refs.append(p)
    missing = [k for k in keys if k not in bib and k not in bbl_raw]
    if missing:
        notes.append(f"{len(missing)} cited keys had no bibliography entry: {', '.join(missing[:5])}")
    for r in refs:
        r.contexts = contexts.get(r.key or "", [])
    refs.sort(key=lambda r: r.idx)
    method = "bib+bbl" if bib and to_llm else "bib" if bib else "bbl"
    return refs, method, notes


async def grobid_paper(pdf: bytes) -> tuple[str | None, list[ParsedRef], str | None]:
    """Title, references and body text of a PDF; each reference gets the sentences that cite it (step 6.3).

    GROBID's full-text model links in-text citations (<ref type="bibr" target="#b3">) to bibliography
    entries. GROBID splits the bibliography and keeps each raw reference string; the fields are then
    parsed by the same LLM parser as pasted bibliographies, because GROBID's own field parsing drops
    titles and shifts author names on some references (EXPERIMENTS.md S10). If the full-text call
    fails, the references-only endpoint is used and no citing sentences are attached."""
    try:
        root = await _grobid("processFulltextDocument", pdf, {"segmentSentences": "1"})
        listbibl = root.find(".//t:back//t:listBibl", TEI)
        title = (root.findtext(".//t:teiHeader//t:titleStmt/t:title", "", TEI) or "").strip() or None
        structured, ids = _parse_bibl(listbibl if listbibl is not None else ET.Element("x"))
        contexts = _bibr_contexts(root, ids)
        parts = [root.find(".//t:teiHeader//t:abstract", TEI), root.find(".//t:text/t:body", TEI)]
        text = " ".join(" ".join(p.itertext()) for p in parts if p is not None) or None
    except SourceError:
        root = await _grobid("processReferences", pdf, {})
        title, (structured, ids), contexts, text = None, _parse_bibl(root), {}, None
    raws = [r.raw for r in structured]
    refs = await parse_references(raws) if structured and all(len(r) > 20 for r in raws) else structured
    for i, r in enumerate(refs):
        r.contexts = contexts.get(ids[i], []) if i < len(ids) else []
    return title, refs, text


async def _grobid(endpoint: str, pdf: bytes, extra: dict) -> ET.Element:
    try:
        r = await http().post(f"{get_settings().grobid_url}/api/{endpoint}", timeout=240.0,
                              files={"input": ("paper.pdf", pdf, "application/pdf")},
                              data={"includeRawCitations": "1", "consolidateCitations": "0", **extra})
    except httpx.HTTPError as e:
        raise SourceError(f"grobid: {type(e).__name__} (is the GROBID container running?)") from e
    if r.status_code != 200:
        raise SourceError(f"grobid: HTTP {r.status_code}")
    return ET.fromstring(r.text)


_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def _bibr_contexts(root: ET.Element, ids: list[str], max_per_ref: int = 3) -> dict[str, list[str]]:
    """Body sentences that cite each bibliography entry, citation markers replaced by [CITATION]."""
    out: dict[str, list[str]] = {}
    body = root.find(".//t:text/t:body", TEI)
    if body is None:
        return out
    known = set(ids)
    for sent in body.iter(f"{{{TEI['t']}}}s"):
        targets, parts = [], [sent.text or ""]
        for el in sent:
            if el.tag == f"{{{TEI['t']}}}ref" and el.get("type") == "bibr":
                parts.append("[CITATION]")
                targets += [t.lstrip("#") for t in (el.get("target") or "").split()]
            else:
                parts.append("".join(el.itertext()))
            parts.append(el.tail or "")
        text = re.sub(r"\s+", " ", "".join(parts)).strip()
        text = re.sub(r"(\[CITATION\][\s,;–-]*){2,}", "[CITATION] ", text).strip()
        if not 20 <= len(text) <= 800:
            continue
        for t in dict.fromkeys(targets):
            if t in known and len(out.setdefault(t, [])) < max_per_ref and text not in out[t]:
                out[t].append(text)
    return out


def _parse_bibl(root: ET.Element) -> tuple[list[ParsedRef], list[str]]:
    """GROBID's structured references (raw strings kept as evidence) and their xml:ids, in order."""
    refs, xml_ids = [], []
    for i, b in enumerate(root.iter(f"{{{TEI['t']}}}biblStruct")):
        xml_ids.append(b.get(_XML_ID) or f"b{i}")
        title = (b.findtext(".//t:analytic/t:title", None, TEI) or b.findtext(".//t:monogr/t:title", None, TEI) or "").strip()
        authors = []
        for p in b.findall(".//t:analytic/t:author/t:persName", TEI) or b.findall(".//t:monogr/t:author/t:persName", TEI):
            sur = (p.findtext("t:surname", "", TEI) or "").strip()
            fore = " ".join((f.text or "").strip() for f in p.findall("t:forename", TEI)).strip()
            if sur:
                authors.append(f"{sur}, {fore}" if fore else sur)
        venue = (b.findtext(".//t:monogr/t:title", None, TEI) or "").strip() if b.find(".//t:analytic", TEI) is not None else None
        date = b.find(".//t:imprint/t:date", TEI)
        year = int(m.group(0)) if date is not None and (m := re.search(r"(19|20)\d\d", date.get("when", "") or (date.text or ""))) else None
        raw = (b.findtext(".//t:note[@type='raw_reference']", None, TEI) or "").strip()
        doi = b.findtext(".//t:idno[@type='DOI']", None, TEI)
        arx = b.findtext(".//t:idno[@type='arXiv']", None, TEI)
        if not raw:
            raw = ". ".join(x for x in [", ".join(authors), title, venue or "", str(year or "")] if x)
        ids = identifiers(raw)
        refs.append(ParsedRef(idx=i, raw=raw, title=title or None, authors=authors, year=year, venue=venue or None,
                              doi=ids["doi"] or normalize_doi(doi), arxiv_id=ids["arxiv_id"] or (re.sub(r"^arXiv:", "", arx) if arx else None),
                              url=ids["url"], type_guess=RefType.preprint if (ids["arxiv_id"] or arx) else RefType.other))
    return refs, xml_ids


async def ingest_arxiv(arxiv_id: str) -> Ingested:
    aid = normalize_arxiv_id(arxiv_id)
    try:
        meta = await arxiv_source.by_id(aid)
    except SourceError:  # metadata API throttled: the title is optional, the e-print may still come through
        meta = None
    else:
        if meta is None:
            raise ValueError(f"arXiv has no paper with ID {aid}")
    title = meta.title if meta else None
    files = unpack(await fetch_eprint(aid))
    if "__pdf__" in files or not any(k.lower().endswith((".bbl", ".bib", ".tex")) for k in files):
        _, refs, text = await grobid_paper(await fetch_pdf(aid))
        return Ingested(title, refs, "grobid", ["no LaTeX source on arXiv; parsed the PDF"], text)
    refs, method, notes = await from_latex(files)
    tex = "\n".join(v for k, v in files.items() if k.lower().endswith(".tex"))
    text = latex.latex_to_text(latex.strip_tex_noise(tex)) if tex else None
    if not refs:  # LaTeX without a usable bibliography: fall back to the PDF
        _, refs, pdf_text = await grobid_paper(await fetch_pdf(aid))
        return Ingested(title, refs, "grobid", notes + ["no bibliography in the source; parsed the PDF"], text or pdf_text)
    return Ingested(title, refs, method, notes, text)
