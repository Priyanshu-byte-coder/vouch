"""Scholarly sources. Each module exposes NAME and `async find(ref, n) -> list[Candidate]`
(identifier lookup first when the reference has a DOI/arXiv ID/ISBN, then search)."""

from . import arxiv, crossref, datacite, openalex, openlibrary, s2
from .base import SourceError, api_calls

# Default cascade order (see docs/IMPLEMENTATION_PLAN.md §4.2)
SOURCES = {m.NAME: m for m in (crossref, openalex, s2, arxiv, datacite, openlibrary)}

__all__ = ["SOURCES", "SourceError", "api_calls"]
