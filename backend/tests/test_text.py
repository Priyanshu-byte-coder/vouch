import pytest

from app.models import ParsedRef
from app.text import (bibliographic_query, clean_for_query, fold, name_from_display, normalize_doi,
                      reconstruct_abstract, strip_ref_number, strip_tags, surname_first)


@pytest.mark.parametrize("raw, expected", [
    ("https://doi.org/10.1038/NATURE14539", "10.1038/nature14539"),
    ("doi:10.1145/2976749.2978318.", "10.1145/2976749.2978318"),
    ("http://dx.doi.org/10.5281/zenodo.5031935", "10.5281/zenodo.5031935"),
    ("", None), (None, None),
])
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected


@pytest.mark.parametrize("display, expected", [
    ("Ashish Vaswani", "Vaswani, Ashish"),
    ("Ludwig van Beethoven", "van Beethoven, Ludwig"),
    ("Martin Luther King Jr.", "King, Martin Luther"),
    ("Vaswani, A.", "Vaswani, A."),
    ("Plato", "Plato"),
])
def test_name_from_display(display, expected):
    assert name_from_display(display) == expected


def test_surname_first_and_fold():
    assert surname_first("LeCun", "Yann") == "LeCun, Yann"
    assert surname_first(None, None, "ATLAS Collaboration") == "ATLAS Collaboration"  # organisations kept
    assert surname_first(None, None, "Cabanac, Guillaume") == "Cabanac, Guillaume"
    assert fold("Gražulis Labbé") == "Grazulis Labbe"


def test_strip_and_clean():
    assert strip_tags("<jats:p>Deep &amp; wide</jats:p>") == "Deep & wide"
    assert clean_for_query(r"On {BERT}: \textit{pre-training} $O(n)$!") == "On BERT pre-training O n"
    assert strip_ref_number("[12] Vaswani A.") == "Vaswani A."


def test_reconstruct_abstract():
    assert reconstruct_abstract({"is": [1], "Attention": [0], "all": [2]}) == "Attention is all"


def test_bibliographic_query():
    ref = ParsedRef(idx=0, raw="x", title="Deep learning", authors=["LeCun, Y."], year=2015)
    assert bibliographic_query(ref) == "Deep learning LeCun 2015"
    assert bibliographic_query(ParsedRef(idx=1, raw="[3] Some raw text")) == "Some raw text"
