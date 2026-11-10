"""DataCite REST API: datasets, software and other non-article DOIs (Zenodo, Figshare, Dryad...)."""

from urllib.parse import quote

from ...models import Candidate, ParsedRef
from ...text import normalize_doi, strip_tags, surname_first, title_query
from .base import get

NAME = "datacite"
BASE = "https://api.datacite.org/dois"


def to_candidate(item: dict) -> Candidate | None:
    a = item.get("attributes") or {}
    title = ((a.get("titles") or [{}])[0].get("title") or "").strip()
    if not title:
        return None
    authors = [surname_first(c.get("familyName"), c.get("givenName"), c.get("name")) for c in a.get("creators", [])]
    abstract = next((d.get("description") for d in a.get("descriptions", []) or []
                     if d.get("descriptionType") == "Abstract"), None)
    return Candidate(source=NAME, id=a.get("doi"), title=title, authors=[x for x in authors if x],
                     year=a.get("publicationYear"), venue=a.get("publisher") if isinstance(a.get("publisher"), str)
                     else (a.get("publisher") or {}).get("name"), doi=normalize_doi(a.get("doi")),
                     url=a.get("url"), abstract=strip_tags(abstract),
                     type=((a.get("types") or {}).get("resourceTypeGeneral") or "").lower() or None)


async def by_doi(doi: str) -> Candidate | None:
    data = await get(NAME, f"{BASE}/{quote(normalize_doi(doi) or '', safe='/')}")
    return to_candidate(data["data"]) if data and data.get("data") else None


async def search(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    q = title_query(ref)
    if not q:
        return []
    data = await get(NAME, BASE, params={"query": f'titles.title:"{q}"', "page[size]": n})
    hits = [c for c in map(to_candidate, (data or {}).get("data", [])) if c]
    if not hits:  # phrase match is strict; fall back to keyword match
        data = await get(NAME, BASE, params={"query": q, "page[size]": n})
        hits = [c for c in map(to_candidate, (data or {}).get("data", [])) if c]
    return hits


async def find(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    out = []
    if ref.doi and (hit := await by_doi(ref.doi)):
        out.append(hit)
    return out + [c for c in await search(ref, n) if not out or c.doi != out[0].doi]
