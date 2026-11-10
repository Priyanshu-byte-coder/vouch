"""OpenAlex: DOI lookup (free singleton) and title search ($0.001 each on the daily budget).

Several API keys rotate when one is rate-limited or out of daily budget.
"""

from ...config import get_settings
from ...models import Candidate, ParsedRef
from ...text import name_from_display, normalize_doi, reconstruct_abstract, title_query
from .base import get

NAME = "openalex"
BASE = "https://api.openalex.org"
SELECT = "id,doi,display_name,publication_year,authorships,primary_location,type,abstract_inverted_index"

_key_index = 0


def _auth() -> dict:
    keys = get_settings().openalex_keys
    return {"api_key": keys[_key_index]} if keys and _key_index < len(keys) else {}


def _rotate() -> dict | None:
    """Move to the next key; None when all keys are used up."""
    global _key_index
    if _key_index + 1 < len(get_settings().openalex_keys):
        _key_index += 1
        return _auth()
    return None


def to_candidate(w: dict) -> Candidate | None:
    title = (w.get("display_name") or w.get("title") or "").strip()
    if not title:
        return None
    authors = [name_from_display((a.get("author") or {}).get("display_name") or "") for a in w.get("authorships", [])]
    source = ((w.get("primary_location") or {}).get("source") or {})
    return Candidate(source=NAME, id=(w.get("id") or "").rsplit("/", 1)[-1] or None, title=title,
                     authors=[a for a in authors if a], year=w.get("publication_year"),
                     venue=source.get("display_name"), doi=normalize_doi(w.get("doi")),
                     url=w.get("id"), abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
                     type=w.get("type"))


async def by_doi(doi: str) -> Candidate | None:
    data = await get(NAME, f"{BASE}/works/doi:{normalize_doi(doi)}", params={"select": SELECT},
                     auth_params=_auth(), rotate=_rotate)
    return to_candidate(data) if data else None


async def search(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    q = title_query(ref)
    if not q:
        return []
    data = await get(NAME, f"{BASE}/works", params={"search": q, "per_page": n, "select": SELECT},
                     auth_params=_auth(), rotate=_rotate)
    return [c for c in map(to_candidate, (data or {}).get("results", [])) if c]


async def find(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    out = []
    if ref.doi and (hit := await by_doi(ref.doi)):
        out.append(hit)
    return out + [c for c in await search(ref, n) if not out or c.id != out[0].id]
