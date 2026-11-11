import { RetractedStamp } from "@/components/stamp";
import { CLAIM_META, SOURCE_LABEL, type RefResult } from "@/lib/types";

function ScoreBar({ label, value, max = 100 }: { label: string; value: number | null; max?: number }) {
  const v = value == null ? null : Math.round((value / max) * 100);
  const color = v == null ? "var(--rule)" : v >= 90 ? "var(--verified)" : v >= 60 ? "var(--mismatch)" : "var(--notfound)";
  return (
    <div className="grid grid-cols-[4.5rem_1fr_2.5rem] items-center gap-2 text-xs">
      <span className="text-ink-soft">{label}</span>
      <span className="relative h-1.5 rounded-full bg-paper-deep">
        {v != null && <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${v}%`, background: color }} />}
      </span>
      <span className="text-right font-mono text-ink-soft">{v == null ? "n/a" : v}</span>
    </div>
  );
}

function highlightCitation(text: string) {
  const parts = text.split("[CITATION]");
  return parts.map((p, i) => (
    <span key={i}>
      {p}
      {i < parts.length - 1 && <mark className="rounded-sm bg-[#e8d9b0] px-1 font-mono text-[0.7rem] text-ink">cite</mark>}
    </span>
  ));
}

export function EvidenceCard({ r }: { r: RefResult }) {
  const m = r.match;
  const s = r.field_scores;
  const contexts = r.parsed.contexts ?? [];
  return (
    <div className="grid gap-6 border-t border-rule bg-card/70 px-5 py-5 md:grid-cols-2">
      {r.retraction && (
        <div className="flex flex-wrap items-start gap-3 rounded-sm border border-retracted/50 bg-retracted/5 p-3 md:col-span-2">
          <RetractedStamp nature={r.retraction.nature} />
          <div className="text-sm">
            <p className="font-semibold text-retracted">
              {r.retraction.nature} notice{r.retraction.date ? ` · ${r.retraction.date}` : ""}
            </p>
            {r.retraction.reasons.length > 0 && <p className="mt-0.5 text-ink-soft">{r.retraction.reasons.slice(0, 5).join(" · ")}</p>}
            {r.retraction.url && (
              <a href={r.retraction.url} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-link underline underline-offset-2">
                Read the notice
              </a>
            )}
          </div>
        </div>
      )}

      <div>
        <h4 className="mb-2 font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">As cited</h4>
        <p className="font-display text-[0.95rem] leading-relaxed">{r.raw}</p>
        {contexts.length > 0 && (
          <>
            <h4 className="mt-4 mb-2 font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">Where the paper cites it</h4>
            <ul className="space-y-2">
              {contexts.slice(0, 2).map((c, i) => (
                <li key={i} className="border-l-2 border-rule pl-3 text-sm leading-relaxed text-ink-soft italic">
                  “{highlightCitation(c)}”
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {r.claims.length > 0 && (
        <div className="md:col-span-2">
          <h4 className="mb-2 font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">Does the cited abstract support the citing sentence?</h4>
          <ul className="space-y-3">
            {r.claims.map((c, i) => {
              const meta = CLAIM_META[c.label];
              return (
                <li key={i} className="grid gap-2 rounded-sm border border-rule bg-paper/40 p-3 md:grid-cols-[9rem_1fr]">
                  <div>
                    <span className="inline-block rounded-sm px-1.5 py-0.5 font-mono text-[0.62rem] tracking-wider text-card uppercase" style={{ background: meta.color }}>
                      {meta.label}
                    </span>
                    <p className="mt-1 font-mono text-[0.62rem] text-ink-faint">confidence {Math.round(c.confidence * 100)}%</p>
                  </div>
                  <div className="space-y-1.5 text-sm leading-relaxed">
                    <p className="text-ink-soft italic">“{highlightCitation(c.context)}”</p>
                    {c.evidence_quote && (
                      <p className="border-l-2 pl-2.5 text-ink" style={{ borderColor: meta.color }}>
                        <span className="mr-1 font-mono text-[0.6rem] tracking-wider text-ink-faint uppercase">abstract says</span>
                        {c.evidence_quote}
                      </p>
                    )}
                    <p className="text-[0.7rem] text-ink-faint">{meta.blurb}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div>
        <h4 className="mb-2 font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">Best record found</h4>
        {m ? (
          <div className="rounded-sm border border-rule bg-paper/50 p-3">
            <p className="font-display text-[0.95rem] leading-snug">{m.title}</p>
            <p className="mt-1 text-xs text-ink-soft">
              {m.authors.slice(0, 6).join("; ")}
              {m.authors.length > 6 ? " et al." : ""}
              {m.year ? ` · ${m.year}` : ""}
              {m.venue ? ` · ${m.venue}` : ""}
            </p>
            <p className="mt-2 flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-sm bg-ink px-1.5 py-0.5 font-mono text-[0.6rem] tracking-wider text-card uppercase">
                {SOURCE_LABEL[m.source] ?? m.source}
              </span>
              {m.doi && (
                <a href={`https://doi.org/${m.doi}`} target="_blank" rel="noreferrer" className="font-mono text-link underline decoration-rule underline-offset-2">
                  doi:{m.doi}
                </a>
              )}
              {!m.doi && m.url && (
                <a href={m.url} target="_blank" rel="noreferrer" className="text-link underline decoration-rule underline-offset-2">
                  open record
                </a>
              )}
            </p>
          </div>
        ) : (
          <p className="text-sm text-ink-soft italic">No plausible record in any source.</p>
        )}

        {s && (
          <div className="mt-4 space-y-1.5">
            <ScoreBar label="Title" value={s.title} />
            <ScoreBar label="Authors" value={s.authors} />
            <ScoreBar label="Venue" value={s.venue} />
            <ScoreBar label="Year" value={s.year} max={1} />
          </div>
        )}

        {r.issues.length > 0 && (
          <ul className="mt-4 space-y-1.5">
            {r.issues.map((i, k) => (
              <li key={k} className="flex gap-2 text-sm leading-snug">
                <span className="mt-[0.15rem] font-display text-mismatch italic">¶</span>
                <span className="text-ink-soft">{i}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 font-mono text-[0.65rem] text-ink-faint">
          searched: {r.sources_tried.map((x) => SOURCE_LABEL[x.split(" ")[0]] ?? x).join(" → ") || "—"}
        </p>
      </div>
    </div>
  );
}
