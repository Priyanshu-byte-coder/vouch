from app.pipeline.retraction import RetractionIndex, describe

H = {"Title": "", "RetractionNature": "", "RetractionDate": "", "Reason": "", "RetractionDOI": "", "URLS": "",
     "OriginalPaperDOI": "", "OriginalPaperPubMedID": "0"}


def row(**kw):
    return {**H, **kw}


IX = RetractionIndex([
    # Correction first, retraction later: the retraction is what matters now
    row(Title="Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children",
        RetractionNature="Correction", RetractionDate="3/6/2004 0:00", Reason="Error in Results;Updated to Retraction;",
        OriginalPaperDOI="10.1016/S0140-6736(97)11096-0", OriginalPaperPubMedID="9500320"),
    row(Title="Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children",
        RetractionNature="Retraction", RetractionDate="2/6/2010 0:00", Reason="+Falsification/Fabrication of Data;",
        RetractionDOI="10.1016/S0140-6736(10)60175-4", OriginalPaperDOI="10.1016/S0140-6736(97)11096-0",
        OriginalPaperPubMedID="9500320"),
    # Retracted then reinstated
    row(Title="A reinstated paper with a sufficiently long title here", RetractionNature="Retraction",
        RetractionDate="1/1/2020 0:00", OriginalPaperDOI="10.1/reinst"),
    row(Title="A reinstated paper with a sufficiently long title here", RetractionNature="Reinstatement",
        RetractionDate="1/1/2022 0:00", OriginalPaperDOI="10.1/reinst"),
    row(Title="Some paper", RetractionNature="Expression of concern", RetractionDate="5/5/2025 0:00",
        OriginalPaperDOI="10.1/eoc", URLS="https://retractionwatch.com/x;https://other"),
])


def test_most_serious_notice_wins_and_meta_reasons_dropped():
    info = IX.lookup(dois=["https://doi.org/10.1016/s0140-6736(97)11096-0"])
    assert info.nature == "Retraction" and info.date == "2010-02-06"
    assert info.reasons == ["Falsification/Fabrication of Data"]
    assert info.url == "https://doi.org/10.1016/s0140-6736(10)60175-4"
    assert "RETRACTED (2010-02-06)" in describe(info)


def test_reinstatement_after_retraction():
    assert IX.lookup(dois=["10.1/reinst"]).nature == "Reinstatement"


def test_other_lookups():
    eoc = IX.lookup(dois=[None, "10.1/EOC"])
    assert eoc.nature == "Expression of concern" and eoc.url == "https://retractionwatch.com/x"
    assert IX.lookup(pmid="9500320").nature == "Retraction"
    assert IX.lookup(title="Ileal-lymphoid-nodular Hyperplasia, Non-specific Colitis, and Pervasive Developmental "
                           "Disorder in Children").nature == "Retraction"
    assert IX.lookup(title="Some paper") is None  # short titles never match on title alone
    assert IX.lookup(dois=["10.1038/nature14539"]) is None


def test_matched_record_is_the_notice():  # S9: Crossref returned 'Retraction Note: ...' (notice DOI)
    assert IX.lookup(dois=["10.1016/S0140-6736(10)60175-4"]).nature == "Retraction"
    assert IX.lookup(title="Retraction Note: Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and "
                           "pervasive developmental disorder in children").nature == "Retraction"


def test_title_fallback_when_doi_unknown():
    t = "Ileal-lymphoid-nodular hyperplasia, non-specific colitis, and pervasive developmental disorder in children"
    assert IX.lookup(dois=["10.9999/not-in-database"], title=t).nature == "Retraction"
