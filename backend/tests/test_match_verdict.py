"""Edge cases from the AtomGPT baseline's own 'Known limitations' list, plus the short-title
over-match we measured in S5. Each test names the weakness it covers."""

import pytest

from app.models import Candidate, ParsedRef, RefType, Status
from app.pipeline.match import author_score, best_match, norm_venue, score_candidate, title_score, venue_score
from app.pipeline.verdict import decide


def ref(**kw):
    return ParsedRef(idx=0, raw=kw.pop("raw", "x"), **kw)


def cand(**kw):
    return Candidate(source=kw.pop("source", "crossref"), **kw)


# --- titles -----------------------------------------------------------------------------------
def test_short_title_does_not_overmatch():  # S5: token_set_ratio gave 100 here
    assert title_score("Deep learning", "Deep Learning with Differential Privacy") < 70
    assert title_score("Deep learning", "PyTorch: An Imperative Style, High-Performance Deep Learning Library") < 50


def test_title_case_punctuation_latex_insensitive():
    assert title_score("Attention is all you need", "Attention Is All You Need.") == 100
    assert title_score(r"{BERT}: Pre-training of deep bidirectional transformers",
                       "BERT: Pre-training of Deep Bidirectional Transformers") == 100


def test_subtitle_omitted_or_truncated():
    full = "Tortured phrases: A dubious writing style emerging in science. Evidence of critical issues"
    assert title_score("Tortured phrases: A dubious writing style emerging in science", full) == 95


def test_fabricated_title_scores_low():
    assert title_score("Hierarchical contrastive attention networks for low-resource citation verification",
                       "Hierarchical Contrastive Graph Attention Network for Aspect-based Sentiment") < 75


# --- authors ----------------------------------------------------------------------------------
def test_diacritics():  # baseline limitation: 'Grazulis' vs 'Gražulis'
    assert author_score(["Grazulis, S."], ["Gražulis, Saulius"]) == 100


def test_et_al_not_penalised():  # baseline limitation: literal 'et al.' counted as unmatched
    record = ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki", "Uszkoreit, Jakob"]
    assert author_score(["Vaswani, A.", "Shazeer, N.", "et al."], record) == 100
    assert author_score(["Vaswani A, Shazeer N et al."], record) is not None


def test_hyphenated_surnames():  # baseline limitation: hyphenation must match exactly
    assert author_score(["Garcia-Lopez, M."], ["Garcia Lopez, Maria"]) == 100


@pytest.mark.parametrize("fmt", ["Smith, J.", "J. Smith", "Smith J", "John Smith"])
def test_name_formats(fmt):  # baseline limitation: 'Smith, J.' took the initial as surname
    assert author_score([fmt], ["Smith, John"]) == 100


def test_wrong_initial_and_wrong_people():
    assert author_score(["Smith, A."], ["Smith, John"]) == 0
    assert author_score(["Zhang, W.", "Kumar, R."], ["LeCun, Yann", "Bengio, Yoshua"]) == 0


# --- venue / year -----------------------------------------------------------------------------
def test_venue_abbreviations_and_aliases():  # baseline limitation: 'Phys. Rev. Lett.' = 66.7
    assert venue_score("Phys. Rev. Lett.", "Physical Review Letters") >= 95
    assert venue_score("Adv. Neural Inf. Process. Syst. 30 (NIPS 2017)", "Neural Information Processing Systems") >= 90
    assert venue_score("NeurIPS", "Advances in Neural Information Processing Systems") >= 90
    assert venue_score("arXiv preprint arXiv:1706.03762", "Nature") is None
    assert norm_venue("Proc. of the 2019 Conf. of NAACL") .startswith("proceedings conference north american")


# --- verdicts ---------------------------------------------------------------------------------
REAL = cand(title="Deep learning", authors=["LeCun, Yann", "Bengio, Yoshua", "Hinton, Geoffrey"], year=2015,
            venue="Nature", doi="10.1038/nature14539")


def test_verified():
    r = ref(title="Deep learning", authors=["LeCun, Y.", "Bengio, Y.", "Hinton, G."], year=2015, venue="Nature")
    assert decide(r, best_match(r, [REAL])).status is Status.verified


def test_real_title_with_wrong_authors_is_detail_mismatch():  # CiteAudit 'author error' fakes
    r = ref(title="Deep learning", authors=["Smith, J.", "Brown, K."], year=2015, venue="Nature")
    v = decide(r, best_match(r, [REAL]))
    assert v.status is Status.detail_mismatch and any("authors differ" in i for i in v.issues)


def test_wrong_year_is_detail_mismatch():
    r = ref(title="Deep learning", authors=["LeCun, Y."], year=2009, venue="Nature")
    assert decide(r, best_match(r, [REAL])).status is Status.detail_mismatch


def test_year_off_by_one_still_verified():  # preprint vs published year
    r = ref(title="Deep learning", authors=["LeCun, Y.", "Hinton, G."], year=2014)
    v = decide(r, best_match(r, [REAL]))
    assert v.status is Status.verified and any("off by one" in i for i in v.issues)


def test_identifier_hijack():  # real DOI attached to an invented title
    r = ref(title="Graph transformers for protein folding at scale", authors=["LeCun, Y."], doi="10.1038/nature14539")
    v = decide(r, best_match(r, [REAL]))
    assert v.status is Status.detail_mismatch and "different work" in v.issues[0]


def test_not_found_vs_cant_verify():
    fake = ref(title="Hierarchical contrastive attention networks for citation verification", authors=["Zhang, W."],
               type_guess=RefType.conference)
    other = cand(title="Analysis of citation networks", authors=["Valmarska, A."], year=2014)
    assert decide(fake, best_match(fake, [other])).status is Status.not_found
    web = ref(title="Company blog post on scaling", type_guess=RefType.web)
    assert decide(web, best_match(web, [])).status is Status.cant_verify
    assert decide(fake, None, all_sources_failed=True).status is Status.cant_verify


def test_best_match_prefers_right_year_copy():  # S5: Crossref's top hit was a 2025 copy
    r = ref(title="Attention is all you need", authors=["Vaswani, A.", "Shazeer, N."], year=2017)
    copy = cand(title="Attention Is All You Need", authors=["Vaswani, A.", "Shazeer, N."], year=2025,
                doi="10.65215/r5bs2d54")
    real = cand(source="openalex", title="Attention Is All You Need", authors=["Vaswani, Ashish", "Shazeer, Noam"],
                year=2017, doi="10.48550/arxiv.1706.03762")
    assert best_match(r, [copy, real]).candidate.year == 2017


def test_identifier_hijack_wins_over_unrelated_better_scoring_records():  # S7: ref 20 was 'not found'
    r = ref(title="Graph transformers for protein folding at scale", authors=["Brown, T."], year=2021,
            doi="10.1038/s41586-021-03819-2")
    alphafold = cand(title="Highly accurate protein structure prediction with AlphaFold", authors=["Jumper, John"],
                     year=2021, venue="Nature", doi="10.1038/s41586-021-03819-2")
    lookalike = cand(source="openalex", title="Graph transformers for protein structure at scale", authors=["Li, X."])
    v = decide(r, best_match(r, [alphafold, lookalike]))
    assert v.status is Status.detail_mismatch and "different work" in v.issues[0]


def test_wrong_doi_on_real_title_keeps_title_match():
    r = ref(title="Deep learning", authors=["LeCun, Y."], year=2015, doi="10.1038/s41586-021-03819-2")
    alphafold = cand(title="Highly accurate protein structure prediction with AlphaFold", doi="10.1038/s41586-021-03819-2")
    assert best_match(r, [alphafold, REAL]).candidate.title == "Deep learning"


def test_middle_name_used_as_first_name():  # S8: 'Ansari, Mohammad Samar' vs 'Ansari, Samar'
    assert author_score(["Ansari, Mohammad Samar"], ["Ansari, Samar"]) == 100
    assert author_score(["Ansari, M. S."], ["Ansari, Samar"]) == 100
    assert author_score(["Ansari, Mohammad"], ["Ansari, Tariq"]) == 0


def test_short_title_alone_is_not_same_work():  # S8: 'Delft' (GitHub software) vs unrelated 'Delft' (2023)
    r = ref(title="Delft", year=2018, venue="GitHub", type_guess=RefType.software)
    other = cand(source="openalex", title="Delft", authors=["Brown, A."], year=2023, venue="World Literature Today")
    assert decide(r, best_match(r, [other])).status is Status.cant_verify
    resnet = ref(title="Deep residual learning", authors=["Smith, J."], year=2016)
    real = cand(title="Deep Residual Learning", authors=["He, Kaiming"], year=2016)
    assert decide(resnet, best_match(resnet, [real])).status is Status.detail_mismatch  # 3+ words: still mismatch


def test_original_paper_preferred_over_notice():  # S9
    r = ref(title="Stimulus-triggered fate conversion of somatic cells into pluripotency", authors=["Obokata, H."], year=2014)
    note = cand(title="Retraction Note: Stimulus-triggered fate conversion of somatic cells into pluripotency",
                authors=["Obokata, Haruko"], year=2014, doi="10.1038/nature13598")
    orig = cand(source="openalex", title="Stimulus-triggered fate conversion of somatic cells into pluripotency",
                authors=["Obokata, Haruko"], year=2014, doi="10.1038/nature12968")
    assert best_match(r, [note, orig]).candidate.doi == "10.1038/nature12968"
    alone = best_match(r, [note])
    assert alone.scores.title == 100 and any("notice about the work" in i for i in alone.issues)


def test_titleless_physics_citation_verified_by_doi():  # E5 audit: APS style omits article titles
    r = ref(title=None, authors=["Hawking, S. W."], year=1975, doi="10.1007/BF02345020")
    rec = cand(title="Particle creation by black holes", authors=["Hawking, S. W."], year=1975,
               venue="Communications in Mathematical Physics", doi="10.1007/bf02345020")
    v = decide(r, best_match(r, [rec]))
    assert v.status is Status.verified


def test_titleless_citation_with_wrong_authors_is_mismatch_not_hijack():
    r = ref(title=None, authors=["Smith, J."], year=1975, doi="10.1007/BF02345020")
    rec = cand(title="Particle creation by black holes", authors=["Hawking, S. W."], year=1975, doi="10.1007/bf02345020")
    v = decide(r, best_match(r, [rec]))
    assert v.status is Status.detail_mismatch and not any("different work" in i for i in v.issues)
