"""Crossref REST API: DOI lookup and bibliographic search (free, polite pool via mailto)."""

from urllib.parse import quote

from ...config import get_settings
from ...models import Candidate, ParsedRef
from ...text import bibliographic_query, normalize_doi, strip_tags, surname_first
from .base import get

NAME = "crossref"
BASE = "https://api.crossref.org"
SELECT = "DOI,title,subtitle,author,issued,container-title,type,URL,abstract"


def _year(item: dict) -> int | None:
    for k in ("issued", "published-print", "published-online", "created"):
        parts = (item.get(k) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def to_candidate(item: dict) -> Candidate | None:
    title = " ".join((item.get("title") or [""])[:1]).strip()
    if not title:
        return None
    sub = (item.get("subtitle") or [""])[0].strip()
    if sub and sub.lower() not in title.lower():
        title = f"{title}: {sub}"
    authors = [surname_first(a.get("family"), a.get("given"), a.get("name")) for a in item.get("author", [])]
    return Candidate(source=NAME, id=item.get("DOI"), title=title, authors=[a for a in authors if a],
                     year=_year(item), venue=((item.get("container-title") or [None])[0]),
                     doi=normalize_doi(item.get("DOI")), url=item.get("URL"),
                     abstract=strip_tags(item.get("abstract")), type=item.get("type"))


def _mailto() -> dict:
    m = get_settings().crossref_mailto
    return {"mailto": m} if m else {}


async def by_doi(doi: str) -> Candidate | None:
    data = await get(NAME, f"{BASE}/works/{quote(normalize_doi(doi) or '', safe='/')}", params=_mailto())
    return to_candidate(data["message"]) if data else None


async def search(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    data = await get(NAME, f"{BASE}/works",
                     params={"query.bibliographic": bibliographic_query(ref), "rows": n, "select": SELECT, **_mailto()})
    items = (data or {}).get("message", {}).get("items", [])
    return [c for c in map(to_candidate, items) if c]


async def find(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    out = []
    if ref.doi and (hit := await by_doi(ref.doi)):
        out.append(hit)
    return out + [c for c in await search(ref, n) if not out or c.doi != out[0].doi]
