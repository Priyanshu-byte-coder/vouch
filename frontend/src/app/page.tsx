import Link from "next/link";
import { CheckForm } from "@/components/check-form";
import { Legend } from "@/components/legend";
import { RetractedStamp, Stamp } from "@/components/stamp";
import mock from "@/lib/mock-report.json";
import research from "@/lib/research.json";
import { SOURCE_LABEL, type Report } from "@/lib/types";

const pct = (x: number) => `${Math.round(x * 100)}%`;
const demo = mock as unknown as Report;

const CHECKS = [
  { n: "i", title: "Exists", body: "Six open indexes, several candidates each." },
  { n: "ii", title: "Accurate", body: "Title, authors, year, venue, DOI compared field by field." },
  { n: "iii", title: "Not retracted", body: "73,718 Retraction Watch notices." },
  { n: "iv", title: "Supports the claim", body: "Citing sentence vs the cited abstract, with the quote (arXiv papers)." },
  { n: "v", title: "No paper-mill language", body: "Tortured-phrase fingerprints.", soon: true },
];

function MiniBar({ base, ours, label }: { base: number; ours: number; label: (v: number) => string }) {
  return (
    <div className="mt-3 space-y-1">
      <div className="flex items-center gap-2 text-[0.65rem] text-ink-faint">
        <span className="h-1.5 rounded-full bg-unverified/50" style={{ width: `${base * 100}%` }} />
        <span className="font-mono">{label(base)} baseline</span>
      </div>
      <div className="flex items-center gap-2 text-[0.65rem] text-ink">
        <span className="h-1.5 rounded-full bg-ink" style={{ width: `${ours * 100}%` }} />
        <span className="font-mono font-semibold">{label(ours)} Vouch</span>
      </div>
    </div>
  );
}

function Pipeline() {
  const sources = Object.values(SOURCE_LABEL);
  const steps = [
    {
      k: "1 · read",
      title: "Get the references",
      body: (
        <ul className="space-y-0.5 text-[0.72rem] text-ink-soft">
          <li>arXiv ID → LaTeX source (.bib / .bbl)</li>
          <li>PDF → GROBID splits the list</li>
          <li>Pasted list → split by entry</li>
          <li className="text-ink-faint">fields parsed by a small LLM; identifiers only by regex</li>
        </ul>
      ),
    },
    {
      k: "2 · look up",
      title: "Ask six indexes in turn",
      body: (
        <ol className="flex flex-wrap gap-1">
          {sources.map((s, i) => (
            <li key={s} className="rounded-sm border border-rule bg-paper px-1.5 py-0.5 font-mono text-[0.62rem] text-ink-soft">
              {i + 1} {s}
            </li>
          ))}
          <li className="w-full pt-1 text-[0.68rem] text-ink-faint">stops at the first confident match</li>
        </ol>
      ),
    },
    {
      k: "3 · compare",
      title: "Score every field",
      body: (
        <div className="space-y-1">
          {[
            ["title", 100, "var(--verified)"],
            ["authors", 62, "var(--notfound)"],
            ["year", 100, "var(--verified)"],
            ["venue", 88, "var(--mismatch)"],
          ].map(([f, v, c]) => (
            <div key={f as string} className="grid grid-cols-[3.2rem_1fr_1.6rem] items-center gap-1.5 text-[0.65rem]">
              <span className="text-ink-soft">{f}</span>
              <span className="h-1.5 rounded-full bg-paper-deep">
                <span className="block h-full rounded-full" style={{ width: `${v}%`, background: c as string }} />
              </span>
              <span className="text-right font-mono text-ink-faint">{v}</span>
            </div>
          ))}
          <p className="pt-0.5 text-[0.68rem] text-ink-faint">a real DOI on the wrong title is caught first</p>
        </div>
      ),
    },
    {
      k: "4 · stamp",
      title: "One verdict, with evidence",
      body: (
        <div className="flex flex-wrap gap-1.5">
          <Stamp status="verified" size="sm" />
          <Stamp status="detail_mismatch" size="sm" />
          <Stamp status="not_found" size="sm" />
          <Stamp status="cant_verify" size="sm" />
          <p className="w-full pt-1 text-[0.68rem] text-ink-faint">best record, field scores and the issues shown for every row</p>
        </div>
      ),
    },
    {
      k: "5 · retractions",
      title: "Check Retraction Watch",
      body: (
        <div>
          <RetractedStamp nature="Retraction" />
          <p className="pt-1.5 text-[0.68rem] text-ink-faint">by DOI, notice DOI, PubMed ID or exact title</p>
        </div>
      ),
    },
  ];
  return (
    <ol className="grid gap-px overflow-hidden rounded-sm border border-ink/70 bg-ink/70 md:grid-cols-5">
      {steps.map((s, i) => (
        <li key={s.k} className="relative bg-card p-4">
          <p className="font-mono text-[0.62rem] tracking-[0.18em] text-ink-faint uppercase">{s.k}</p>
          <h3 className="mt-1 mb-3 font-display text-lg leading-snug">{s.title}</h3>
          {s.body}
          {i < steps.length - 1 && (
            <span className="absolute top-1/2 -right-2.5 z-10 hidden h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full border border-ink/70 bg-card font-display text-sm text-ink md:flex" aria-hidden="true">
              →
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

function ReportPreview() {
  const pick = [0, 16, 15, 18].map((i) => demo.references[i]).filter(Boolean);
  return (
    <div className="overflow-hidden rounded-sm border border-ink/70 bg-card">
      <div className="flex items-baseline justify-between gap-3 border-b border-rule px-4 py-2.5">
        <p className="font-mono text-[0.65rem] tracking-[0.18em] text-ink-faint uppercase">from the demo report</p>
        <Link href="/report/demo" className="text-xs text-link underline decoration-rule underline-offset-4 hover:decoration-link">
          open all {demo.references.length} rows →
        </Link>
      </div>
      <ol>
        {pick.map((r) => (
          <li key={r.idx} className="ledger-row grid grid-cols-[2.2rem_6.2rem_1fr] items-center gap-3 px-4 py-3">
            <span className="numerals-old text-right font-display text-lg text-ink-faint">{r.idx + 1}</span>
            <span className="flex flex-col items-start gap-1">
              <Stamp status={r.status} size="sm" />
              {r.retraction && <RetractedStamp nature={r.retraction.nature} />}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-display text-[0.98rem]">{r.parsed.title ?? r.raw}</span>
              <span className="block truncate text-xs text-ink-faint">
                {r.parsed.authors.slice(0, 3).join(", ")}
                {r.parsed.authors.length > 3 ? " et al." : ""}
                {r.parsed.year ? ` · ${r.parsed.year}` : ""}
                {r.retraction ? ` · ${r.retraction.nature.toLowerCase()} ${r.retraction.date ?? ""}` : r.status !== "verified" && r.issues[0] ? ` · ${r.issues[0].replace(/\s*\(closest:.*\)\s*$/, "")}` : ""}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function Home() {
  const ca = research.citeaudit300;
  const ne = research.neurips100;
  return (
    <div className="mx-auto max-w-6xl px-6">
      <section className="grid gap-12 pt-14 pb-12 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div className="rise">
          <p className="mb-5 font-mono text-[0.7rem] tracking-[0.2em] text-ink-faint uppercase">Vol. 1 · A research-integrity screener</p>
          <h1 className="font-display text-[3.4rem] leading-[0.98] font-medium tracking-tight sm:text-[4.4rem]">
            Every citation,
            <br />
            <span className="italic">vouched&nbsp;for.</span>
          </h1>
          <p className="mt-7 max-w-xl font-display text-xl leading-relaxed text-ink-soft">
            One paper in 277 now cites a reference that does not exist<sup className="text-link">1</sup>. Vouch checks every reference
            in a paper against six open indexes and shows the evidence for each verdict.
          </p>
          <p className="mt-8 max-w-md border-l-2 border-rule pl-3 text-xs leading-relaxed text-ink-faint">
            <sup>1</sup> up from 1 in 2,828 in 2023 (GESIS, arXiv:2607.22693). One in twenty NeurIPS and USENIX Security papers carries two
            or more likely hallucinated references (arXiv:2607.00738).
          </p>
        </div>
        <div className="rise" style={{ animationDelay: "120ms" }}>
          <CheckForm />
        </div>
      </section>

      <section className="rise" style={{ animationDelay: "200ms" }}>
        <h2 className="mb-3 font-mono text-[0.65rem] tracking-[0.2em] text-ink-faint uppercase">What the stamps mean</h2>
        <Legend />
      </section>

      <section className="rise mt-14 grid gap-px overflow-hidden rounded-sm border border-ink/70 bg-ink/70 sm:grid-cols-3" style={{ animationDelay: "260ms" }}>
        <div className="bg-card p-6">
          <p className="font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">Fake citations caught</p>
          <p className="mt-2 font-display text-5xl tracking-tight">{pct(ca.vouch.recall!)}</p>
          <MiniBar base={ca.baseline.recall!} ours={ca.vouch.recall!} label={pct} />
          <p className="mt-2 text-xs text-ink-soft">CiteAudit-300, vs the published Semantic Scholar-only checker</p>
        </div>
        <div className="bg-card p-6">
          <p className="font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">F1 on CiteAudit-300</p>
          <p className="mt-2 font-display text-5xl tracking-tight">{ca.vouch.f1!.toFixed(2)}</p>
          <MiniBar base={ca.baseline.f1!} ours={ca.vouch.f1!} label={(v) => v.toFixed(2)} />
          <p className="mt-2 text-xs text-ink-soft">paired on the same citations: 44 vs 8, p &lt; 0.001</p>
        </div>
        <div className="bg-card p-6">
          <p className="font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">NeurIPS 2025 fakes</p>
          <p className="mt-2 font-display text-5xl tracking-tight">{Math.round(ne.vouch.recall! * 100)}/100</p>
          <MiniBar base={ne.baseline.recall!} ours={ne.vouch.recall!} label={(v) => `${Math.round(v * 100)}`} />
          <p className="mt-2 text-xs text-ink-soft">confirmed hallucinated citations in accepted papers</p>
        </div>
      </section>
      <p className="mt-3 text-right text-xs text-ink-faint">
        Methods, intervals and every chart on the{" "}
        <Link href="/research" className="text-link underline decoration-rule underline-offset-4 hover:decoration-link">
          research page
        </Link>
        .
      </p>

      <section className="mt-16">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <h2 className="font-display text-3xl italic">How a reference is checked</h2>
          <p className="max-w-md text-xs leading-relaxed text-ink-soft">Labels describe evidence, never people. Anything Vouch cannot verify goes to a human with the closest records it found.</p>
        </div>
        <Pipeline />
      </section>

      <section className="mt-16 grid gap-10 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <h2 className="mb-4 font-display text-3xl italic">What a report looks like</h2>
          <ReportPreview />
        </div>
        <div>
          <h2 className="mb-4 font-display text-3xl italic">Five questions</h2>
          <ol className="divide-y divide-rule border-y border-rule">
            {CHECKS.map((c) => (
              <li key={c.n} className="grid grid-cols-[2rem_1fr] items-baseline gap-2 py-2.5">
                <span className="font-display text-xl text-ink-faint italic">{c.n}.</span>
                <div>
                  <h3 className="text-sm font-semibold">
                    {c.title}
                    {c.soon && <span className="ml-2 font-mono text-[0.58rem] tracking-widest text-mismatch uppercase">in progress</span>}
                  </h3>
                  <p className="text-xs text-ink-soft">{c.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <div className="h-16" />
    </div>
  );
}
