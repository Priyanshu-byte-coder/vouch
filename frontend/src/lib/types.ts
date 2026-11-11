// Mirrors backend/app/models.py (the Report API contract).

export type Status = "verified" | "detail_mismatch" | "not_found" | "cant_verify";

export interface ParsedRef {
  idx: number;
  raw: string;
  title: string | null;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  arxiv_id: string | null;
  isbn: string | null;
  url: string | null;
  type_guess: string;
  key?: string | null;
  contexts?: string[];
}

export interface Candidate {
  source: string;
  id: string | null;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  abstract?: string | null;
  type: string | null;
}

export interface FieldScores {
  title: number | null;
  authors: number | null;
  year: number | null;
  venue: number | null;
  composite: number | null;
}

export interface RetractionInfo {
  nature: string;
  date: string | null;
  reasons: string[];
  notice_doi: string | null;
  url: string | null;
}

export interface ClaimCheck {
  context: string;
  label: "SUPPORTS" | "CONTRADICTS" | "NOT_ENOUGH_INFO" | "ABSTAIN";
  confidence: number;
  evidence_quote: string | null;
  evidence_source: string | null;
}

export interface RefResult {
  idx: number;
  raw: string;
  parsed: ParsedRef;
  status: Status;
  confidence: number;
  match: Candidate | null;
  field_scores: FieldScores | null;
  issues: string[];
  retraction: RetractionInfo | null;
  claims: ClaimCheck[];
  sources_tried: string[];
}

export interface Summary {
  verified: number;
  detail_mismatch: number;
  not_found: number;
  cant_verify: number;
  retracted: number;
  claims_checked: number;
  claims_unsupported: number;
  tortured_hits: number;
}

export interface Report {
  paper: { title: string | null; source: string; n_refs: number };
  summary: Summary;
  references: RefResult[];
  tortured: { phrase: string; expected: string; snippet: string }[];
  meta: {
    models: Record<string, string>;
    seconds: number;
    llm_calls: number;
    llm_tokens_in: number;
    llm_tokens_out: number;
    cost_usd: number;
    api_calls: Record<string, number>;
    cache_hits: number;
    notes?: string[];
  };
}

export const STATUS_META: Record<Status, { label: string; stamp: string; color: string; blurb: string }> = {
  verified: {
    label: "Verified",
    stamp: "Verified",
    color: "var(--verified)",
    blurb: "A matching record exists and its details agree.",
  },
  detail_mismatch: {
    label: "Detail mismatch",
    stamp: "Mismatch",
    color: "var(--mismatch)",
    blurb: "The work exists, but authors, year, venue or DOI disagree with the record.",
  },
  not_found: {
    label: "Not found",
    stamp: "Not found",
    color: "var(--notfound)",
    blurb: "No plausible record in any of the six scholarly indexes.",
  },
  cant_verify: {
    label: "Can't verify",
    stamp: "Unverified",
    color: "var(--unverified)",
    blurb: "Web pages, software, reports or partial matches. Needs a human look.",
  },
};

export const SOURCE_LABEL: Record<string, string> = {
  crossref: "Crossref",
  openalex: "OpenAlex",
  s2: "Semantic Scholar",
  arxiv: "arXiv",
  datacite: "DataCite",
  openlibrary: "Open Library",
};

export const CLAIM_META: Record<ClaimCheck["label"], { label: string; color: string; blurb: string }> = {
  SUPPORTS: { label: "Supported", color: "var(--verified)", blurb: "The abstract states or directly implies what the sentence cites it for." },
  CONTRADICTS: { label: "Contradicted", color: "var(--notfound)", blurb: "The abstract says something incompatible with the citing sentence. Worth a close look." },
  NOT_ENOUGH_INFO: { label: "Abstract can't tell", color: "var(--unverified)", blurb: "The abstract does not settle it; the claim may be in the full text. Not a sign of a problem." },
  ABSTAIN: { label: "Needs a human", color: "var(--mismatch)", blurb: "The model was not confident enough (below the threshold tuned on SciFact), so it does not give a verdict." },
};
