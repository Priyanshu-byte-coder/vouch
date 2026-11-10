"""Step 2.4 done-check (live): a 20-reference list with 3 planted fakes."""

import json
from pathlib import Path

import pytest

from app.models import Status
from app.pipeline.run import check_bibliography

pytestmark = pytest.mark.live
FIX = Path(__file__).parent / "fixtures"


async def test_bib20_flags_planted_fakes():
    answers = json.loads((FIX / "bib20_answers.json").read_text(encoding="utf-8"))
    report = await check_bibliography((FIX / "bib20.txt").read_text(encoding="utf-8"),
                                      sources=["crossref", "openalex", "arxiv", "datacite", "openlibrary", "s2"])
    assert len(report.references) == 20
    fakes = set(answers["fake_indices"])
    for r in report.references:
        if r.idx in fakes:
            assert r.status.value in answers["expected"][str(r.idx)], (r.idx, r.status, r.issues)
        elif r.idx == 14:  # AlexNet: known coverage gap under the tuned config (only the 2017 CACM reprint is indexed); S11
            assert r.status in (Status.verified, Status.detail_mismatch, Status.cant_verify)
        else:
            assert r.status is Status.verified, (r.idx, r.parsed.title, r.status, r.issues)
    hijack = report.references[19]
    assert hijack.match and "AlphaFold" in hijack.match.title
