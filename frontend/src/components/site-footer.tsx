export function SiteFooter() {
  return (
    <footer className="mx-auto mt-24 w-full max-w-6xl px-6 pb-10 text-xs text-ink-faint">
      <div className="rule-double mb-5" />
      <div className="grid gap-6 sm:grid-cols-3">
        <p className="font-display text-base text-ink-soft italic">
          Evidence for human review, not an accusation.
        </p>
        <p className="leading-relaxed">
          Metadata from Crossref, OpenAlex, Semantic Scholar (Kinney et al., <i>The Semantic Scholar Open Data Platform</i>,
          2023), arXiv, DataCite and Open Library. Retractions from the Retraction Watch database (Crossref).
        </p>
        <p className="leading-relaxed sm:text-right">
          Vouch · Team Beyonders · Threws Odyssey 2026
          <br />
          Benchmarks: CiteAudit, NeurIPS-2025 hallucinated citations, SciFact.
        </p>
      </div>
    </footer>
  );
}
