"""LLM adjudicator for borderline matches (step 3.3).

Runs only when the rule-based verdict did not verify a reference but a plausible candidate exists.
The model sees the cited reference and the top candidate records and says which record (if any) is
the same work. It judges only from the records shown (not from its own memory of the literature), so
decisions are reproducible and evidence-based. It can only *verify* a reference; it never flags one.
"""

from ..llm import LLMJSONError, chat_json
from ..models import ParsedRef
from .match import Scored

SYSTEM = """You check citations. Decide whether a cited reference and one of several bibliographic records describe the SAME work.

The same work may appear as a different version: preprint vs published paper, conference vs journal version, a later edition or a reprint.
- Titles may differ in capitalisation, punctuation, a subtitle added or removed, truncation, or light rewording between versions.
- Authors must be the same people. Allow initials vs full names, accents, missing middle names, "et al.", small typos and minor reordering. If the cited first author is not among the record's authors, or several cited authors are absent from the record, it is NOT the same work.
- The year may differ by a few years for versions or editions. The venue may differ.
- Judge ONLY from the records shown. Do not use your own memory of the literature. If no record is clearly the same work, answer 0.

Reply with ONLY a JSON object: {"match": <record number, or 0 for none>, "confidence": <0.0-1.0>, "reason": "<at most 25 words>"}"""


def _fmt_record(n: int, s: Scored) -> str:
    c = s.candidate
    authors = "; ".join(c.authors[:10]) + (" ..." if len(c.authors) > 10 else "") if c.authors else "(no authors listed)"
    return (f"Record {n} [{c.source}]\n  title: {c.title}\n  authors: {authors}\n  year: {c.year}\n"
            f"  venue: {c.venue}\n  type: {c.type}\n  doi: {c.doi}")


def top_candidates(scored: list[Scored], k: int = 3) -> list[Scored]:
    """Up to k candidates with distinct titles, best composite first."""
    out, seen = [], set()
    for s in sorted(scored, key=lambda x: x.scores.composite or 0, reverse=True):
        key = s.candidate.title.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) == k:
            break
    return out


async def adjudicate(ref: ParsedRef, scored: list[Scored]) -> dict:
    """Return {"match": Scored | None, "confidence": float, "reason": str, "raw": dict}."""
    cands = top_candidates(scored)
    if not cands:
        return {"match": None, "confidence": 0.0, "reason": "no candidates", "raw": {}}
    cited = (f"Cited reference (as written): {ref.raw}\n"
             f"Parsed: title={ref.title!r}; authors={'; '.join(ref.authors[:10]) or '(none)'}; year={ref.year}; venue={ref.venue}")
    prompt = cited + "\n\n" + "\n\n".join(_fmt_record(i + 1, s) for i, s in enumerate(cands))
    try:
        out = await chat_json(prompt, system=SYSTEM, thinking=True)
    except LLMJSONError as e:
        return {"match": None, "confidence": 0.0, "reason": f"AI review failed: {e}", "raw": {}}
    try:
        n = int(out.get("match", 0) or 0)
        conf = float(out.get("confidence", 0) or 0)
    except (TypeError, ValueError, AttributeError):
        return {"match": None, "confidence": 0.0, "reason": "AI review returned an unreadable answer", "raw": out}
    reason = str(out.get("reason", ""))[:300]
    if 1 <= n <= len(cands):
        return {"match": cands[n - 1], "confidence": max(0.0, min(1.0, conf)), "reason": reason, "raw": out}
    return {"match": None, "confidence": max(0.0, min(1.0, conf)), "reason": reason, "raw": out}
