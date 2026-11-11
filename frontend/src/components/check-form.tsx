"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Tab = "arxiv" | "pdf" | "bib";

const TABS: { id: Tab; label: string; hint: string }[] = [
  { id: "arxiv", label: "arXiv paper", hint: "ID or URL, e.g. 2602.23452" },
  { id: "pdf", label: "PDF upload", hint: "Any paper, up to 20 MB" },
  { id: "bib", label: "Bibliography", hint: "Paste a reference list" },
];

export const EXAMPLES = [
  { label: "CiteAudit (2026)", note: "a benchmark paper on fake citations", arxiv: "2602.23452" },
  { label: "HalluCiteChecker (2026)", note: "a citation-checking toolkit", arxiv: "2604.26835" },
  { label: "Demo mix", note: "3 planted fakes + 2 retracted papers", demo: true },
];

export function CheckForm() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("arxiv");
  const [arxiv, setArxiv] = useState("");
  const [bib, setBib] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const ready = (tab === "arxiv" && arxiv.trim()) || (tab === "bib" && bib.trim().length > 20) || (tab === "pdf" && file);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready) return;
    // Step 4.1: UI only. Step 4.2 sends this to the API and opens the live report.
    router.push("/report/demo");
  }

  return (
    <form onSubmit={submit} className="relative">
      {/* file-folder tabs */}
      <div className="flex gap-1 pl-3" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={`relative -mb-px rounded-t-md border border-b-0 px-3.5 py-1.5 text-sm transition-colors ${
              tab === t.id ? "z-10 border-ink/70 bg-card text-ink" : "border-rule bg-paper-deep text-ink-soft hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="relative rounded-md rounded-tl-none border border-ink/70 bg-card p-5 shadow-[6px_6px_0_-1px_var(--paper-deep),6px_6px_0_0_var(--rule)]">
        {/* index-card ruling */}
        <div className="pointer-events-none absolute inset-x-5 top-12 border-t border-[#c98b8b]/50" />
        <p className="mb-4 font-mono text-[0.7rem] tracking-wider text-ink-faint uppercase">
          {TABS.find((t) => t.id === tab)?.hint}
        </p>

        {tab === "arxiv" && (
          <input
            value={arxiv}
            onChange={(e) => setArxiv(e.target.value)}
            placeholder="2602.23452  or  https://arxiv.org/abs/…"
            className="w-full border-b-2 border-ink/80 bg-transparent py-2 font-mono text-lg outline-none placeholder:text-ink-faint/70 focus:border-link"
            aria-label="arXiv ID or URL"
          />
        )}
        {tab === "bib" && (
          <textarea
            value={bib}
            onChange={(e) => setBib(e.target.value)}
            rows={7}
            placeholder={"[1] LeCun Y, Bengio Y, Hinton G. Deep learning. Nature 2015;521:436–444.\n[2] …"}
            className="w-full resize-y rounded-sm border border-rule bg-paper/40 p-3 font-mono text-[0.8rem] leading-relaxed outline-none focus:border-link"
            aria-label="Reference list"
          />
        )}
        {tab === "pdf" && (
          <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-sm border-2 border-dashed border-rule py-9 text-center hover:border-ink-soft">
            <span className="font-display text-lg italic">{file ? file.name : "Drop a PDF or click to choose"}</span>
            <span className="text-xs text-ink-faint">References are extracted with GROBID, then checked one by one.</span>
            <input type="file" accept="application/pdf" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
        )}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className="max-w-xs text-xs leading-relaxed text-ink-faint">
            Six open indexes, the Retraction Watch database, and evidence for every verdict.
          </p>
          <button
            type="submit"
            disabled={!ready}
            className="rounded-sm border-2 border-ink bg-ink px-5 py-2 text-sm font-semibold tracking-wide text-card transition hover:bg-transparent hover:text-ink disabled:cursor-not-allowed disabled:opacity-35"
          >
            Check citations →
          </button>
        </div>
      </div>

      <div className="mt-6">
        <p className="mb-2 font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">Or try an example</p>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              onClick={() => router.push("/report/demo")}
              className="group rounded-sm border border-rule bg-card/60 px-3 py-1.5 text-left text-sm hover:border-ink-soft"
            >
              <span className="font-medium">{ex.label}</span>
              <span className="block text-[0.7rem] text-ink-faint group-hover:text-ink-soft">{ex.note}</span>
            </button>
          ))}
        </div>
      </div>
    </form>
  );
}
