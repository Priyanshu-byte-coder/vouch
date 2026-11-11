import Link from "next/link";
import { CheckForm } from "@/components/check-form";
import { Stamp } from "@/components/stamp";
import research from "@/lib/research.json";

const CHECKS = [
  { n: "i", title: "Exists", body: "Looked up across Crossref, OpenAlex, Semantic Scholar, arXiv, DataCite and Open Library, with several candidates per source." },
  { n: "ii", title: "Accurate", body: "Title, authors, year, venue and DOI compared field by field. A real DOI attached to the wrong title is caught." },
  { n: "iii", title: "Not retracted", body: "Every identified work is checked against 73,718 notices in the Retraction Watch database." },
  { n: "iv", title: "Supports the claim", body: "The citing sentence against the cited abstract, with a quoted passage as evidence.", soon: true },
  { n: "v", title: "No paper-mill language", body: "Tortured phrases such as “counterfeit consciousness” for “artificial intelligence”.", soon: true },
];

function pct(x: number) {
  return `${Math.round(x * 100)}%`;
}

export default function Home() {
  const ca = research.citeaudit300;
  const ne = research.neurips100;
  return (
    <div className="mx-auto max-w-6xl px-6">
      <section className="grid gap-12 pt-14 pb-16 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div className="rise">
          <p className="mb-5 font-mono text-[0.7rem] tracking-[0.2em] text-ink-faint uppercase">
            Vol. 1 · A research-integrity screener
          </p>
          <h1 className="font-display text-[3.4rem] leading-[0.98] font-medium tracking-tight sm:text-[4.4rem]">
            Every citation,
            <br />
            <span className="italic">vouched&nbsp;for.</span>
          </h1>
          <p className="mt-7 max-w-xl font-display text-xl leading-relaxed text-ink-soft">
            Papers citing references that do not exist rose from one in 2,828 in 2023 to one in 277 in early 2026
            <sup className="text-link">1</sup>. Vouch checks every reference in a paper and shows the evidence for each
            verdict.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Stamp status="verified" />
            <Stamp status="detail_mismatch" />
            <Stamp status="not_found" />
            <Stamp status="cant_verify" />
          </div>
          <p className="mt-10 max-w-md border-l-2 border-rule pl-3 text-xs leading-relaxed text-ink-faint">
            <sup>1</sup> GESIS, arXiv:2607.22693. One in twenty NeurIPS and USENIX Security papers carries two or more likely
            hallucinated references (arXiv:2607.00738).
          </p>
        </div>
        <div className="rise" style={{ animationDelay: "120ms" }}>
          <CheckForm />
        </div>
      </section>

      <section className="rise grid gap-px overflow-hidden rounded-sm border border-ink/70 bg-ink/70 sm:grid-cols-3" style={{ animationDelay: "220ms" }}>
        {[
          { k: "Fake citations caught", v: pct(ca.vouch.recall!), sub: `vs ${pct(ca.baseline.recall!)} for a Semantic Scholar-only checker (CiteAudit-300)` },
          { k: "F1 on CiteAudit-300", v: ca.vouch.f1!.toFixed(2), sub: `vs ${ca.baseline.f1!.toFixed(2)} published baseline · paired p < 0.001` },
          { k: "NeurIPS 2025 fakes", v: `${Math.round(ne.vouch.recall! * 100)}/100`, sub: `confirmed hallucinated citations in accepted papers; baseline ${Math.round(ne.baseline.recall! * 100)}/100` },
        ].map((s) => (
          <div key={s.k} className="bg-card p-6">
            <p className="font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">{s.k}</p>
            <p className="mt-2 font-display text-5xl tracking-tight">{s.v}</p>
            <p className="mt-2 text-xs leading-relaxed text-ink-soft">{s.sub}</p>
          </div>
        ))}
      </section>
      <p className="mt-3 text-right text-xs text-ink-faint">
        Methods, confidence intervals and limitations on the{" "}
        <Link href="/research" className="text-link underline decoration-rule underline-offset-4 hover:decoration-link">
          research page
        </Link>
        .
      </p>

      <section className="mt-20 grid gap-10 lg:grid-cols-[0.8fr_2fr]">
        <div>
          <h2 className="font-display text-3xl italic">Five questions per reference</h2>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">
            Labels describe evidence, never people. A reference Vouch cannot verify is sent to a human with the closest records
            it found.
          </p>
        </div>
        <ol className="grid gap-x-10 gap-y-7 sm:grid-cols-2">
          {CHECKS.map((c) => (
            <li key={c.n} className="flex gap-4">
              <span className="w-8 shrink-0 text-right font-display text-2xl text-ink-faint italic">{c.n}.</span>
              <div>
                <h3 className="font-semibold">
                  {c.title}
                  {c.soon && <span className="ml-2 font-mono text-[0.6rem] tracking-widest text-mismatch uppercase">in progress</span>}
                </h3>
                <p className="mt-1 text-sm leading-relaxed text-ink-soft">{c.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
