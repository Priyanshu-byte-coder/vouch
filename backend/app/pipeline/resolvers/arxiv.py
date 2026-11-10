"""arXiv API (Atom XML): lookup by arXiv ID and title search. Max 1 request per 3 s."""

import re
import xml.etree.ElementTree as ET

from ...models import Candidate, ParsedRef
from ...text import name_from_display, title_query
from .base import get

NAME = "arxiv"
BASE = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_ID = re.compile(r"arxiv\.org/abs/([^v\s]+?)(v\d+)?$")


def parse_feed(xml_text: str) -> list[Candidate]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", NS):
        title = re.sub(r"\s+", " ", e.findtext("a:title", "", NS)).strip()
        id_url = e.findtext("a:id", "", NS)
        m = _ID.search(id_url)
        if not title or not m or title.lower() == "error":
            continue
        aid = m.group(1)
        published = e.findtext("a:published", "", NS)
        out.append(Candidate(
            source=NAME, id=aid, title=title,
            authors=[name_from_display(a.findtext("a:name", "", NS)) for a in e.findall("a:author", NS)],
            year=int(published[:4]) if published[:4].isdigit() else None,
            venue=e.findtext("arxiv:journal_ref", None, NS) or "arXiv",
            doi=(e.findtext("arxiv:doi", None, NS) or f"10.48550/arxiv.{aid}").lower(),
            url=f"https://arxiv.org/abs/{aid}",
            abstract=re.sub(r"\s+", " ", e.findtext("a:summary", "", NS)).strip() or None, type="preprint"))
    return out


async def by_id(arxiv_id: str) -> Candidate | None:
    xml = await get(NAME, BASE, params={"id_list": arxiv_id.strip()}, as_text=True)
    hits = parse_feed(xml) if xml else []
    return hits[0] if hits else None


async def search(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    q = title_query(ref)
    if not q:
        return []
    words = [w for w in q.split() if len(w) > 2][:12]
    query = " AND ".join(f"ti:{w}" for w in words) if words else f'ti:"{q}"'
    xml = await get(NAME, BASE, params={"search_query": query, "max_results": n}, as_text=True)
    return parse_feed(xml) if xml else []


async def find(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    out = []
    if ref.arxiv_id and (hit := await by_id(ref.arxiv_id)):
        out.append(hit)
    return out + [c for c in await search(ref, n) if not out or c.id != out[0].id]
