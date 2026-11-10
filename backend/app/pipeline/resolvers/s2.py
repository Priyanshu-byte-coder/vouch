"""Semantic Scholar Graph API: ID lookup (DOI/arXiv) and title search. 1 request/second (licence)."""

from urllib.parse import quote

from ...config import get_settings
from ...models import Candidate, ParsedRef
from ...text import name_from_display, normalize_doi, title_query
from .base import get

NAME = "s2"
BASE = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,authors,year,venue,publicationVenue,externalIds,abstract,url,publicationTypes"


def _headers() -> dict:
    key = get_settings().s2_api_key
    return {"x-api-key": key} if key else {}


def to_candidate(p: dict) -> Candidate | None:
    title = (p.get("title") or "").strip()
    if not title:
        return None
    ext = p.get("externalIds") or {}
    venue = p.get("venue") or ((p.get("publicationVenue") or {}).get("name"))
    types = p.get("publicationTypes") or []
    return Candidate(source=NAME, id=p.get("paperId"), title=title,
                     authors=[name_from_display(a.get("name") or "") for a in p.get("authors", []) if a.get("name")],
                     year=p.get("year"), venue=venue or None, doi=normalize_doi(ext.get("DOI")), url=p.get("url"),
                     abstract=p.get("abstract"), type=types[0] if types else None)


async def by_id(paper_id: str) -> Candidate | None:
    """paper_id like 'DOI:10.1038/nature14539' or 'arXiv:1706.03762'."""
    data = await get(NAME, f"{BASE}/paper/{quote(paper_id, safe=':/')}", params={"fields": FIELDS},
                     headers=_headers(), max_attempts=6)
    return to_candidate(data) if data else None


async def search(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    q = title_query(ref)
    if not q:
        return []
    data = await get(NAME, f"{BASE}/paper/search", params={"query": q[:300], "limit": n, "fields": FIELDS},
                     headers=_headers(), max_attempts=6)
    return [c for c in map(to_candidate, (data or {}).get("data", []) or []) if c]


async def find(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    out = []
    for pid in ([f"DOI:{normalize_doi(ref.doi)}"] if ref.doi else []) + ([f"arXiv:{ref.arxiv_id}"] if ref.arxiv_id else []):
        if hit := await by_id(pid):
            out.append(hit)
            break
    return out + [c for c in await search(ref, n) if not out or c.id != out[0].id]
