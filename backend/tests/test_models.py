from app.config import get_settings
from app.models import (Candidate, ClaimCheck, ClaimLabel, PaperInfo, ParsedRef, RefResult, Report,
                        RetractionInfo, Status, TorturedHit)


def _ref(i, status, **kw):
    return RefResult(idx=i, raw=f"ref {i}", parsed=ParsedRef(idx=i, raw=f"ref {i}"), status=status,
                     confidence=0.9, **kw)


def test_report_summary_counts():
    rep = Report(paper=PaperInfo(source="bibliography"), references=[
        _ref(0, Status.verified, match=Candidate(source="crossref", title="T")),
        _ref(1, Status.verified, retraction=RetractionInfo(nature="Retraction")),
        _ref(2, Status.not_found),
        _ref(3, Status.detail_mismatch, claims=[
            ClaimCheck(context="c", label=ClaimLabel.supports, confidence=0.9),
            ClaimCheck(context="c", label=ClaimLabel.contradicts, confidence=0.8)]),
        _ref(4, Status.cant_verify, retraction=RetractionInfo(nature="Correction")),
    ], tortured=[TorturedHit(phrase="counterfeit consciousness", expected="artificial intelligence", snippet="...")])
    s = rep.refresh_summary().summary
    assert (s.verified, s.detail_mismatch, s.not_found, s.cant_verify) == (2, 1, 1, 1)
    assert s.retracted == 1  # corrections are not retractions
    assert (s.claims_checked, s.claims_unsupported, s.tortured_hits) == (2, 1, 1)
    assert rep.paper.n_refs == 5


def test_report_json_roundtrip():
    rep = Report(paper=PaperInfo(source="arxiv:1706.03762"), references=[_ref(0, Status.verified)])
    assert Report.model_validate_json(rep.model_dump_json()).references[0].status is Status.verified


def test_settings_load_env():
    s = get_settings()
    assert s.llm_base_url.startswith("https://")
    assert len(s.openalex_keys) >= 1
    assert "Vouch/" in s.user_agent
