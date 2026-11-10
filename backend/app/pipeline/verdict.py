"""Turn the best match into one of four labels, with reasons.

Starting thresholds; tuned on the dev split only in step 3.1 (frozen in eval/configs/rq1.yaml).
"""

from dataclasses import dataclass

from ..models import HARD_TO_INDEX, ParsedRef, RefType, Status
from .match import Scored


@dataclass(frozen=True)
class Thresholds:
    verified: float = 85.0       # composite needed to verify
    title_min: float = 85.0      # title must also clear this to verify
    author_min: float = 60.0     # share of cited authors found
    same_work_title: float = 90.0  # title this close = same work, so other disagreements are "detail mismatch"
    found: float = 60.0          # below this composite, nothing plausible was found
    year_tolerance: int = 1      # years apart that still count as the same work (preprint vs published)
    book_year_any: bool = False  # books are reprinted in new editions: ignore the year for books


DEFAULT = Thresholds()


@dataclass
class Verdict:
    status: Status
    confidence: float
    issues: list[str]


def _year_ok(ref: ParsedRef, best: Scored, t: Thresholds) -> bool:
    if not ref.year or not best.candidate.year:
        return True
    if t.book_year_any and ref.type_guess in (RefType.book, RefType.chapter):
        return True
    return abs(ref.year - best.candidate.year) <= t.year_tolerance


def decide(ref: ParsedRef, best: Scored | None, *, all_sources_failed: bool = False,
           t: Thresholds = DEFAULT) -> Verdict:
    # A real DOI attached to a different title is a mismatch however low the overall score is.
    if best is not None and best.doi_match and (best.scores.title or 0) < 85:
        return Verdict(Status.detail_mismatch, 0.9, best.issues)
    if best is None or (best.scores.composite or 0) < t.found:
        if all_sources_failed:
            return Verdict(Status.cant_verify, 0.0, ["every source failed to respond; try again later"])
        closest = f" (closest: '{best.candidate.title}', score {best.scores.composite})" if best else ""
        if ref.type_guess in HARD_TO_INDEX:
            return Verdict(Status.cant_verify, 0.5,
                           [f"no match in scholarly indexes, which rarely cover this kind of source ({ref.type_guess.value})"
                            + closest])
        conf = 1.0 - (best.scores.composite or 0) / 100 if best else 0.95
        return Verdict(Status.not_found, round(conf, 2), ["no matching record in any source" + closest])

    s = best.scores
    composite, title = s.composite or 0, s.title or 0
    authors_ok = s.authors is None or s.authors >= t.author_min
    year_ok = _year_ok(ref, best, t)
    venue_ok = s.venue is None or s.venue >= 50
    if composite >= t.verified and title >= t.title_min and authors_ok and year_ok:
        info = [i for i in best.issues if i.startswith(("year", "DOI cited"))]
        return Verdict(Status.verified, round(composite / 100, 2), info)
    if title >= t.same_work_title and not (authors_ok and year_ok and venue_ok):
        # A very short title ("Delft", "Grobid") matches unrelated records; without agreeing authors or DOI
        # there is no evidence it is the same work, so it goes to human review instead.
        short = len(best.candidate.title.split()) <= 2 or len((ref.title or "").split()) <= 2
        same_year_venue = s.year == 1.0 and s.venue is not None and s.venue >= 80
        if short and not best.doi_match and not same_year_venue and not (s.authors is not None and s.authors >= t.author_min):
            return Verdict(Status.cant_verify, 0.5,
                           [f"only a very short title matches ('{best.candidate.title}'); not enough evidence it is the same work",
                            *best.issues])
        return Verdict(Status.detail_mismatch, round(title / 100, 2), best.issues)
    return Verdict(Status.cant_verify, round(composite / 100, 2),
                   [f"partial match only (score {composite}): '{best.candidate.title}'", *best.issues])
