"""Check ④: does the cited work support the sentence that cites it? (step 6.1, evaluated in E4 / RQ4)

For a reference that exists, each citing sentence is compared with the cited work's abstract by an LLM, which
answers SUPPORTS / CONTRADICTS / NOT_ENOUGH_INFO with a confidence and a verbatim evidence quote. Two safeguards:

- quote grounding: a SUPPORTS / CONTRADICTS answer must quote the abstract; if the quote is not actually in the
  abstract, the answer is downgraded to NOT_ENOUGH_INFO (the model may not invent evidence);
- abstention: answers below a confidence threshold become ABSTAIN ("needs human review").

An abstract is short, so NOT_ENOUGH_INFO usually means "the abstract alone can't tell", never "unsupported".
"""

import asyncio
import re

from rapidfuzz import fuzz

from ..llm import LLMJSONError, chat_json
from ..models import Candidate, ClaimCheck, ClaimLabel
from ..text import normalize_doi
from .match import norm_title

SYSTEM = """You check whether a scientific source supports a statement that cites it.

You get a STATEMENT from a paper (the cited source is marked [CITATION] when the marker is present) and the ABSTRACT of the cited source.
Decide what the abstract says about the statement's claim:
- SUPPORTS: the abstract states or directly implies the claim.
- CONTRADICTS: the abstract states something incompatible with the claim.
- NOT_ENOUGH_INFO: the abstract does not settle it (the claim may still be in the full text).
Judge ONLY from the abstract, not from your own knowledge. Parts of the statement that are about other sources or the citing paper itself don't count.

Reply with ONLY a JSON object:
{"label": "SUPPORTS" | "CONTRADICTS" | "NOT_ENOUGH_INFO", "confidence": <0.0-1.0>, "quote": "<the single most relevant sentence copied verbatim from the abstract, or empty>"}"""

GROUND_MIN = 90        # partial-ratio needed for a quote to count as copied from the abstract
DEFAULT_TAU = 0.0      # abstention threshold; set from SciFact in E4 (see tuned.json "claims")
MAX_CONTEXTS = 2       # citing sentences checked per reference
MIN_ABSTRACT_WORDS = 25


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()


def grounded(quote: str | None, abstract: str) -> bool:
    """True if the quote really comes from the abstract (tolerates punctuation/spacing changes)."""
    if not quote or len(quote.split()) < 4:
        return False
    return fuzz.partial_ratio(_norm(quote), _norm(abstract)) >= GROUND_MIN


async def judge(statement: str, abstract: str, *, thinking: bool = False) -> dict:
    """Raw model answer: {"label", "confidence", "quote"} (label normalised; errors become NOT_ENOUGH_INFO, 0.0)."""
    prompt = f"STATEMENT:\n{statement.strip()}\n\nABSTRACT:\n{abstract.strip()}"
    try:
        out = await chat_json(prompt, system=SYSTEM, thinking=thinking, max_tokens=6000 if thinking else 600)
        label = str(out.get("label", "")).upper().replace(" ", "_")
        conf = max(0.0, min(1.0, float(out.get("confidence", 0) or 0)))
        quote = str(out.get("quote") or "").strip() or None
    except (LLMJSONError, TypeError, ValueError, AttributeError):
        return {"label": "NOT_ENOUGH_INFO", "confidence": 0.0, "quote": None}
    if label not in ("SUPPORTS", "CONTRADICTS", "NOT_ENOUGH_INFO"):
        label = "NOT_ENOUGH_INFO"
    return {"label": label, "confidence": conf, "quote": quote}


def apply_policy(raw: dict, abstract: str, *, grounding: bool = True, tau: float | None = None) -> tuple[str, float, str | None]:
    """The three E4 variants: direct (grounding=False, tau=None), + grounding, + grounding + abstention (tau)."""
    label, conf, quote = raw["label"], raw["confidence"], raw["quote"]
    if grounding and label in ("SUPPORTS", "CONTRADICTS") and not grounded(quote, abstract):
        label = "NOT_ENOUGH_INFO"
    if grounding and quote and not grounded(quote, abstract):
        quote = None  # never show a quote that is not in the source
    if tau is not None and conf < tau:
        label = "ABSTAIN"
    return label, conf, quote


def pick_abstract(best: Candidate | None, candidates: list[Candidate]) -> tuple[str | None, str | None]:
    """The matched record's abstract, else one from another record of the same work (same DOI or title)."""
    def ok(c: Candidate) -> bool:
        return bool(c.abstract) and len(c.abstract.split()) >= MIN_ABSTRACT_WORDS

    if best and ok(best):
        return best.abstract, best.source
    if best:
        doi, title = normalize_doi(best.doi), norm_title(best.title)
        for c in candidates:
            if ok(c) and ((doi and normalize_doi(c.doi) == doi) or norm_title(c.title) == title):
                return c.abstract, c.source
    return None, None


async def check_claims(contexts: list[str], best: Candidate | None, candidates: list[Candidate],
                       tau: float = DEFAULT_TAU) -> list[ClaimCheck]:
    abstract, source = pick_abstract(best, candidates)
    if not abstract or not contexts:
        return []
    ctxs = [c for c in contexts if len(c.split()) >= 5][:MAX_CONTEXTS]
    raws = await asyncio.gather(*(judge(c, abstract) for c in ctxs))
    out = []
    for ctx, raw in zip(ctxs, raws):
        label, conf, quote = apply_policy(raw, abstract, grounding=True, tau=tau)
        out.append(ClaimCheck(context=ctx, label=ClaimLabel(label), confidence=round(conf, 2),
                              evidence_quote=quote, evidence_source=f"abstract ({source})"))
    return out
