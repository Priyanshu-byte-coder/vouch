"""Data models shared by the pipeline, the API and the evaluation scripts.

The Report shape is the API contract in docs/IMPLEMENTATION_PLAN.md §4.8.
"""

from enum import Enum

from pydantic import BaseModel, Field


class RefType(str, Enum):
    article = "article"
    conference = "conference"
    preprint = "preprint"
    book = "book"
    chapter = "chapter"
    report = "report"
    thesis = "thesis"
    dataset = "dataset"
    software = "software"
    web = "web"
    other = "other"


# Types that scholarly indexes usually do not cover; a miss is "can't verify", not "not found".
HARD_TO_INDEX = {RefType.web, RefType.software, RefType.report, RefType.other}


class ParsedRef(BaseModel):
    idx: int
    raw: str
    title: str | None = None
    authors: list[str] = Field(default_factory=list)  # "Surname, Initials"
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None
    url: str | None = None
    type_guess: RefType = RefType.other
    key: str | None = None  # citation key in the source (e.g. BibTeX key), when known
    contexts: list[str] = Field(default_factory=list)  # sentences in the paper that cite this reference


class Candidate(BaseModel):
    """A record returned by one scholarly source."""
    source: str  # crossref | openalex | s2 | arxiv | datacite | openlibrary
    id: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    type: str | None = None


class FieldScores(BaseModel):
    title: float | None = None    # 0-100
    authors: float | None = None  # 0-100
    year: float | None = None     # 0, 0.5 or 1
    venue: float | None = None    # 0-100
    composite: float | None = None


class Status(str, Enum):
    verified = "verified"
    detail_mismatch = "detail_mismatch"
    not_found = "not_found"
    cant_verify = "cant_verify"


class RetractionInfo(BaseModel):
    nature: str  # Retraction | Correction | Expression of concern | Reinstatement
    date: str | None = None
    reasons: list[str] = Field(default_factory=list)
    notice_doi: str | None = None
    url: str | None = None


class ClaimLabel(str, Enum):
    supports = "SUPPORTS"
    contradicts = "CONTRADICTS"
    not_enough_info = "NOT_ENOUGH_INFO"
    abstain = "ABSTAIN"


class ClaimCheck(BaseModel):
    context: str
    label: ClaimLabel
    confidence: float
    evidence_quote: str | None = None
    evidence_source: str | None = None  # abstract | fulltext


class RefResult(BaseModel):
    idx: int
    raw: str
    parsed: ParsedRef
    status: Status
    confidence: float
    match: Candidate | None = None
    field_scores: FieldScores | None = None
    issues: list[str] = Field(default_factory=list)
    retraction: RetractionInfo | None = None
    claims: list[ClaimCheck] = Field(default_factory=list)
    sources_tried: list[str] = Field(default_factory=list)


class TorturedHit(BaseModel):
    phrase: str
    expected: str
    snippet: str


class PaperInfo(BaseModel):
    title: str | None = None
    source: str  # e.g. "arxiv:2501.01234", "pdf:upload.pdf", "bibliography"
    n_refs: int = 0


class Summary(BaseModel):
    verified: int = 0
    detail_mismatch: int = 0
    not_found: int = 0
    cant_verify: int = 0
    retracted: int = 0
    claims_checked: int = 0
    claims_unsupported: int = 0
    tortured_hits: int = 0


class RunMeta(BaseModel):
    models: dict[str, str] = Field(default_factory=dict)
    seconds: float = 0.0
    llm_calls: int = 0
    llm_tokens_in: int = 0
    llm_tokens_out: int = 0
    cost_usd: float = 0.0
    api_calls: dict[str, int] = Field(default_factory=dict)
    cache_hits: int = 0
    notes: list[str] = Field(default_factory=list)


class Report(BaseModel):
    paper: PaperInfo
    summary: Summary = Field(default_factory=Summary)
    references: list[RefResult] = Field(default_factory=list)
    tortured: list[TorturedHit] = Field(default_factory=list)
    meta: RunMeta = Field(default_factory=RunMeta)

    def refresh_summary(self) -> "Report":
        s = Summary(tortured_hits=len(self.tortured))
        for r in self.references:
            setattr(s, r.status.value, getattr(s, r.status.value) + 1)
            if r.retraction and r.retraction.nature.lower() == "retraction":
                s.retracted += 1
            for c in r.claims:
                s.claims_checked += 1
                if c.label in (ClaimLabel.contradicts, ClaimLabel.not_enough_info):
                    s.claims_unsupported += 1
        self.summary = s
        self.paper.n_refs = len(self.references)
        return self
