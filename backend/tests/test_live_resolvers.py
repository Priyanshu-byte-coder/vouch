"""Step 2.2 done-check (live): each kind of reference is found by the sources that should know it,
and a fabricated reference has no close match anywhere."""

import pytest
from rapidfuzz import fuzz

from app.models import ParsedRef
from app.pipeline.resolvers import arxiv, crossref, datacite, openalex, openlibrary
from app.text import fold

pytestmark = pytest.mark.live


def _sim(a, b):
    return fuzz.token_sort_ratio(fold(a).lower(), fold(b).lower())


async def test_article_by_doi():
    ref = ParsedRef(idx=0, raw="x", title="Deep learning", doi="10.1038/nature14539", authors=["LeCun, Y."])
    for src in (crossref, openalex):
        top = (await src.find(ref))[0]
        assert top.doi == "10.1038/nature14539" and top.year == 2015


async def test_preprint_by_arxiv_id():
    top = await arxiv.by_id("1706.03762")
    assert top and top.title == "Attention Is All You Need"


async def test_book_in_openlibrary():
    ref = ParsedRef(idx=0, raw="x", title="Deep Learning", authors=["Goodfellow, I."], year=2016)
    assert any(c.year == 2016 and "Goodfellow, Ian" in c.authors for c in await openlibrary.find(ref))


async def test_dataset_in_datacite():
    hit = await datacite.by_doi("10.5281/zenodo.5031935")
    assert hit and hit.type == "dataset" and hit.title.startswith("Tortured phrases")


async def test_fake_has_no_close_match():
    title = "Hierarchical contrastive attention networks for low-resource citation verification"
    ref = ParsedRef(idx=0, raw="x", title=title, authors=["Zhang, W.", "Kumar, R."], year=2023)
    for src in (crossref, openalex, arxiv, datacite):
        assert all(_sim(title, c.title) < 80 for c in await src.find(ref))
