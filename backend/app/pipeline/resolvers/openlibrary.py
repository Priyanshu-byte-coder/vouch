"""Open Library search: books (by ISBN, or title + author)."""

import re

from ...models import Candidate, ParsedRef
from ...text import first_surname, name_from_display, title_query
from .base import get

NAME = "openlibrary"
BASE = "https://openlibrary.org/search.json"
FIELDS = "key,title,subtitle,author_name,first_publish_year,publisher,isbn"


def to_candidate(d: dict) -> Candidate | None:
    title = (d.get("title") or "").strip()
    if not title:
        return None
    if d.get("subtitle"):
        title = f"{title}: {d['subtitle']}"
    isbns = d.get("isbn") or []
    return Candidate(source=NAME, id=d.get("key"), title=title,
                     authors=[name_from_display(a) for a in d.get("author_name", []) or []],
                     year=d.get("first_publish_year"), venue=(d.get("publisher") or [None])[0],
                     url=f"https://openlibrary.org{d['key']}" if d.get("key") else None,
                     type="book" if not isbns else f"book (ISBN {isbns[0]})")


async def search(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    if ref.isbn:
        params = {"isbn": re.sub(r"[^0-9Xx]", "", ref.isbn)}
    else:
        q = title_query(ref)
        if not q:
            return []
        params = {"title": q}
        if surname := first_surname(ref):
            params["author"] = surname
    data = await get(NAME, BASE, params={**params, "limit": n, "fields": FIELDS})
    return [c for c in map(to_candidate, (data or {}).get("docs", [])) if c]


async def find(ref: ParsedRef, n: int = 5) -> list[Candidate]:
    return await search(ref, n)
