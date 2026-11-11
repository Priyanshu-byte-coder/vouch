"use client";

import { useMemo, useState } from "react";
import { EvidenceCard } from "@/components/evidence-card";
import { RetractedStamp, Stamp } from "@/components/stamp";
import { downloadCsv, downloadJson } from "@/lib/export";
import { STATUS_META, type RefResult, type Report, type Status } from "@/lib/types";

const ORDER: Status[] = ["not_found", "detail_mismatch", "cant_verify", "verified"];
type Filter = "attention" | "all" | Status | "retracted";

/** "Authors et al. · year · first issue" for a ledger row; the raw closest-match detail stays in the evidence card. */
function byline(r: RefResult) {
  const a = r.parsed.authors;
  const authors = a.length ? a.slice(0, 3).join(", ") + (a.length > 3 ? " et al." : "") : null;
  const issue = r.status !== "verified" && r.issues[0] ? r.issues[0].replace(/\s*\(closest:.*\)\s*$/, "") : null;
  const contra = r.claims.some((c) => c.label === "CONTRADICTS") ? "abstract contradicts a citing sentence" : null;
  return [authors, r.parsed.year, issue, contra].filter(Boolean).join(" · ");
}

function needsAttention(r: RefResult) {
  return r.status !== "verified" || !!r.retraction;
}

export interface LiveState {
  phase: "connecting" | "queued" | "reading" | "checking";
  kind: "arxiv" | "bibliography" | "pdf" | null;
  done: number;
  total: number | null;
  elapsed: number;
}

const READING: Record<string, string> = {
  arxiv: "Downloading the paper's source from arXiv and reading its bibliography",
  pdf: "Extracting the reference list from the PDF with GROBID",
  bibliography: "Splitting and parsing the reference list",
};

function LivePanel({ live }: { live: LiveState }) {
  const step =
    live.phase === "connecting"
      ? "Connecting to the checker"
      : live.phase === "queued"
        ? "Waiting for a free slot (other checks are running)"
        : live.phase === "reading"
          ? READING[live.kind ?? "bibliography"]
          : `Checking each reference against six indexes and Retraction Watch`;
  const pct = live.total ? (live.done / live.total) * 100 : null;
  return (
    <div className="rise mt-6 rounded-sm border border-ink/70 bg-card px-4 py-3" role="status" aria-live="polite">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-ink">
          <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-mismatch align-middle" />
          {step}…
        </p>
        <p className="font-mono text-[0.7rem] text-ink-faint">
          {live.total ? `${live.done} / ${live.total} references · ` : ""}
          {live.elapsed}s
        </p>
      </div>
      <div className="mt-2.5 h-1 overflow-hidden rounded-full bg-paper-deep">
        {pct === null ? (
          <div className="indeterminate h-full w-1/4 bg-ink" />
        ) : (
          <div className="h-full bg-ink transition-[width] duration-500" style={{ width: `${Math.max(pct, 2)}%` }} />
        )}
      </div>
    </div>
  );
}

export function ReportView({ report, live }: { report: Report; live?: LiveState }) {
  const refs = report.references;
  const [filter, setFilter] = useState<Filter>(refs.some(needsAttention) ? "attention" : "all");
  const [open, setOpen] = useState<number | null>(null);

  const counts = useMemo(() => {
    const c: Record<Status, number> = { verified: 0, detail_mismatch: 0, not_found: 0, cant_verify: 0 };
    refs.forEach((r) => c[r.status]++);
    return c;
  }, [refs]);
  const retracted = refs.filter((r) => r.retraction?.nature === "Retraction").length;

  const shown = refs.filter((r) =>
    filter === "all" ? true : filter === "attention" ? needsAttention(r) : filter === "retracted" ? !!r.retraction : r.status === filter,
  );

  const total = refs.length || 1;
  const m = report.meta;

  return (
    <div>
      {/* masthead */}
      <div className="rise">
        <p className="font-mono text-[0.7rem] tracking-[0.2em] text-ink-faint uppercase">Citation report · {report.paper.source}</p>
        <h1 className="mt-3 max-w-4xl font-display text-3xl leading-tight font-medium sm:text-[2.6rem]">
          {report.paper.title ?? (report.paper.source.startsWith("pdf:") ? report.paper.source.slice(4) : "Pasted bibliography")}
        </h1>
        <p className="mt-3 text-sm text-ink-soft">
          {live ? `${refs.length} of ${report.paper.n_refs || "?"} references checked so far` : `${refs.length} references checked`}
          {m.seconds ? ` in ${m.seconds}s` : ""}
          {m.cost_usd ? ` · AI cost $${m.cost_usd.toFixed(3)}` : ""}
          {m.notes?.length ? ` · ${m.notes.join(" · ")}` : ""}
        </p>
      </div>

      {live && <LivePanel live={live} />}

      {/* summary stamps */}
      <div className="rise mt-8 grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-ink/70 bg-ink/70 sm:grid-cols-5" style={{ animationDelay: "80ms" }}>
        {(["verified", "detail_mismatch", "not_found", "cant_verify"] as Status[]).map((st) => (
          <button
            key={st}
            onClick={() => setFilter(st)}
            className={`flex flex-col items-start gap-3 p-4 text-left transition-colors ${filter === st ? "bg-paper-deep" : "bg-card hover:bg-paper"}`}
          >
            <Stamp status={st} size="sm" />
            <span className="font-display text-4xl leading-none">{counts[st]}</span>
            <span className="text-[0.68rem] leading-snug text-ink-soft">{STATUS_META[st].blurb}</span>
          </button>
        ))}
        <button
          onClick={() => setFilter("retracted")}
          className={`col-span-2 flex flex-col items-start gap-3 p-4 text-left transition-colors sm:col-span-1 ${filter === "retracted" ? "bg-paper-deep" : "bg-card hover:bg-paper"}`}
        >
          <RetractedStamp nature="Retraction" />
          <span className="font-display text-4xl leading-none text-retracted">{retracted}</span>
          <span className="text-[0.68rem] leading-snug text-ink-soft">Exists, but a retraction notice is on record in Retraction Watch.</span>
        </button>
      </div>

      {(() => {
        const cl = refs.flatMap((r) => r.claims);
        if (!cl.length) return null;
        const n = (l: string) => cl.filter((c) => c.label === l).length;
        return (
          <p className="mt-4 text-sm text-ink-soft">
            <span className="font-mono text-[0.65rem] tracking-widest text-ink-faint uppercase">claim support · </span>
            {cl.length} citing sentences compared with the cited abstracts: <b className="text-verified">{n("SUPPORTS")} supported</b>,{" "}
            <b className="text-notfound">{n("CONTRADICTS")} contradicted</b>, {n("NOT_ENOUGH_INFO")} where the abstract can&apos;t tell,{" "}
            {n("ABSTAIN")} left to a human. Open a row to see the quote.
          </p>
        );
      })()}

      {/* proportional ledger bar */}
      <div className="mt-3 flex h-2 overflow-hidden rounded-full" aria-hidden="true">
        {ORDER.slice()
          .reverse()
          .map((st) => (
            <span key={st} style={{ width: `${(counts[st] / total) * 100}%`, background: STATUS_META[st].color }} />
          ))}
      </div>

      {/* filters */}
      <div className="mt-10 flex flex-wrap items-center gap-2 text-sm">
        {(
          [
            ["attention", "Needs attention"],
            ["all", "All references"],
          ] as [Filter, string][]
        ).map(([f, label]) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full border px-3 py-1 ${filter === f ? "border-ink bg-ink text-card" : "border-rule text-ink-soft hover:border-ink-soft"}`}
          >
            {label}
          </button>
        ))}
        <span className="ml-auto font-mono text-[0.7rem] text-ink-faint">
          showing {shown.length} of {refs.length}
        </span>
        {!live && refs.length > 0 && (
          <span className="flex gap-1 font-mono text-[0.7rem]">
            <button onClick={() => downloadJson(report)} className="rounded-sm border border-rule px-2 py-0.5 text-ink-soft hover:border-ink-soft hover:text-ink">
              JSON ↓
            </button>
            <button onClick={() => downloadCsv(report)} className="rounded-sm border border-rule px-2 py-0.5 text-ink-soft hover:border-ink-soft hover:text-ink">
              CSV ↓
            </button>
          </span>
        )}
      </div>

      {/* ledger */}
      <ol className="mt-4 overflow-hidden rounded-sm border border-ink/70 bg-card">
        {shown.map((r) => {
          const isOpen = open === r.idx;
          return (
            <li key={r.idx} className={`ledger-row ${live ? "rise" : ""}`}>
              <button
                onClick={() => setOpen(isOpen ? null : r.idx)}
                aria-expanded={isOpen}
                className="grid w-full grid-cols-[2.6rem_6.5rem_1fr_auto] items-center gap-3 px-4 py-3 text-left hover:bg-paper/60"
              >
                <span className="numerals-old text-right font-display text-xl text-ink-faint">{r.idx + 1}</span>
                <span className="flex flex-col items-start gap-1">
                  <Stamp status={r.status} size="sm" animate={!!live} />
                  {r.retraction && <RetractedStamp nature={r.retraction.nature} />}
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-display text-[1.02rem]">{r.parsed.title ?? r.raw}</span>
                  <span className="block truncate text-xs text-ink-faint">{byline(r)}</span>
                </span>
                <span className={`font-mono text-ink-faint transition-transform ${isOpen ? "rotate-90" : ""}`}>›</span>
              </button>
              {isOpen && <EvidenceCard r={r} />}
            </li>
          );
        })}
        {live &&
          Array.from({ length: Math.min(4, Math.max(1, (live.total ?? 4) - live.done)) }).map((_, i) => (
            <li key={`pending-${i}`} className="ledger-row grid grid-cols-[2.6rem_6.5rem_1fr] items-center gap-3 px-4 py-3.5" aria-hidden="true">
              <span />
              <span className="shimmer h-3.5 w-16 rounded-sm" />
              <span className="space-y-1.5">
                <span className="shimmer block h-3.5 rounded-sm" style={{ width: `${70 - i * 12}%` }} />
                <span className="shimmer block h-2.5 w-1/3 rounded-sm" />
              </span>
            </li>
          ))}
        {!live && shown.length === 0 && <li className="px-4 py-8 text-center text-sm text-ink-faint italic">Nothing in this view.</li>}
      </ol>
    </div>
  );
}
