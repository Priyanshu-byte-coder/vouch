from app.models import RefType
from app.pipeline.parse_refs import _coerce, identifiers, split_bibliography
from app.pipeline.run import cascade_order
from app.models import ParsedRef


def test_split_numbered_and_blank_lines():
    assert len(split_bibliography("[1] A first reference here.\n[2] A second reference,\ncontinued.")) == 2
    assert split_bibliography("1. Alpha et al. Something long.\n2. Beta et al. Another one.")[1].startswith("2.")
    assert len(split_bibliography("Ref one is long enough.\n\nRef two is also long.")) == 2


def test_identifiers_only_from_raw_text():
    ids = identifiers("Jumper J et al. AlphaFold. Nature 2021. https://doi.org/10.1038/s41586-021-03819-2.")
    assert ids["doi"] == "10.1038/s41586-021-03819-2"
    assert identifiers("Kingma, Ba. Adam. arXiv preprint arXiv:1412.6980v9")["arxiv_id"] == "1412.6980"
    assert identifiers("See https://arxiv.org/abs/1706.03762")["arxiv_id"] == "1706.03762"
    assert identifiers("Book. ISBN 978-0-262-03561-3.")["isbn"] == "9780262035613"
    assert identifiers("No identifiers here at all.") == {"doi": None, "arxiv_id": None, "isbn": None, "url": None}


def test_coerce_ignores_llm_invented_doi():
    r = _coerce(0, "Smith J. A paper title. 2019.", {"title": "A paper title", "doi": "10.9999/invented",
                                                     "year": "2019", "authors": ["Smith, J.", "et al."]})
    assert r.doi is None and r.year == 2019 and r.authors == ["Smith, J."]


def test_coerce_fallbacks():
    r = _coerce(3, "Some text arXiv:2107.06751 (2021)", None)
    assert r.arxiv_id == "2107.06751" and r.type_guess is RefType.preprint and r.year == 2021


def test_cascade_routing():
    all_sources = ["crossref", "openalex", "s2", "arxiv", "datacite", "openlibrary"]
    book = ParsedRef(idx=0, raw="x", type_guess=RefType.book)
    assert cascade_order(book, all_sources)[:3] == ["crossref", "openalex", "openlibrary"]
    assert cascade_order(ParsedRef(idx=0, raw="x", arxiv_id="1706.03762"), all_sources)[2] == "arxiv"
    assert cascade_order(ParsedRef(idx=0, raw="x"), all_sources)[-1] == "s2"
