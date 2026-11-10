"""Offline tests: map each source's response format to Candidate."""

from app.pipeline.resolvers import arxiv, crossref, datacite, openalex, openlibrary, s2

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <published>2017-06-12T17:57:34Z</published>
    <title>Attention Is All
      You Need</title>
    <summary>The dominant sequence transduction models...</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
  </entry>
</feed>"""


def test_arxiv_parse_feed():
    [c] = arxiv.parse_feed(ARXIV_XML)
    assert (c.id, c.title, c.year) == ("1706.03762", "Attention Is All You Need", 2017)
    assert c.authors == ["Vaswani, Ashish", "Shazeer, Noam"]
    assert c.doi == "10.48550/arxiv.1706.03762" and c.type == "preprint"


def test_crossref_candidate():
    c = crossref.to_candidate({
        "DOI": "10.1038/NATURE14539", "title": ["Deep learning"], "container-title": ["Nature"],
        "author": [{"family": "LeCun", "given": "Yann"}, {"name": "Consortium X"}],
        "issued": {"date-parts": [[2015, 5, 27]]}, "abstract": "<jats:p>Deep learning allows...</jats:p>",
        "type": "journal-article"})
    assert (c.title, c.year, c.venue, c.doi) == ("Deep learning", 2015, "Nature", "10.1038/nature14539")
    assert c.authors == ["LeCun, Yann", "Consortium X"] and c.abstract == "Deep learning allows..."
    assert crossref.to_candidate({"title": []}) is None


def test_openalex_candidate():
    c = openalex.to_candidate({
        "id": "https://openalex.org/W2919115771", "doi": "https://doi.org/10.1038/nature14539",
        "display_name": "Deep learning", "publication_year": 2015, "type": "article",
        "authorships": [{"author": {"display_name": "Yann LeCun"}}],
        "primary_location": {"source": {"display_name": "Nature"}},
        "abstract_inverted_index": {"Deep": [0], "learning": [1]}})
    assert (c.id, c.doi, c.venue, c.abstract) == ("W2919115771", "10.1038/nature14539", "Nature", "Deep learning")
    assert c.authors == ["LeCun, Yann"]


def test_s2_candidate():
    c = s2.to_candidate({"paperId": "204e30", "title": "Attention is All you Need", "year": 2017, "venue": "",
                         "publicationVenue": {"name": "Neural Information Processing Systems"},
                         "externalIds": {"DOI": "10.48550/arXiv.1706.03762"},
                         "authors": [{"name": "Ashish Vaswani"}], "publicationTypes": ["JournalArticle"]})
    assert c.venue == "Neural Information Processing Systems" and c.doi == "10.48550/arxiv.1706.03762"
    assert c.authors == ["Vaswani, Ashish"] and c.type == "JournalArticle"


def test_datacite_and_openlibrary_candidates():
    d = datacite.to_candidate({"attributes": {
        "doi": "10.5281/ZENODO.5031935", "titles": [{"title": "Tortured phrases"}], "publicationYear": 2021,
        "publisher": "Zenodo", "creators": [{"familyName": "Cabanac", "givenName": "Guillaume"}],
        "types": {"resourceTypeGeneral": "Dataset"},
        "descriptions": [{"description": "<p>Supplementary</p>", "descriptionType": "Abstract"}]}})
    assert (d.doi, d.venue, d.type, d.abstract) == ("10.5281/zenodo.5031935", "Zenodo", "dataset", "Supplementary")
    b = openlibrary.to_candidate({"key": "/works/OL1", "title": "Deep Learning", "author_name": ["Ian Goodfellow"],
                                  "first_publish_year": 2016, "publisher": ["MIT Press"], "isbn": ["9780262035613"]})
    assert b.authors == ["Goodfellow, Ian"] and b.year == 2016 and b.type == "book (ISBN 9780262035613)"
