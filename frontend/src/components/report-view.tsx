"use client";

import { useMemo, useState } from "react";
import { EvidenceCard } from "@/components/evidence-card";
import { RetractedStamp, Stamp } from "@/components/stamp";
import { STATUS_META, type RefResult, type Report, type Status } from "@/lib/types";

const ORDER: Status[] = ["not_found", "detail_mismatch", "cant_verify", "verified"];
type Filter = "attention" | "all" | Status | "retracted";

function needsAttention(r: RefResult) {
  return r.status !== "verified" || !!r.retraction;
}

export function ReportView({ report, live = false, progress }: { report: Report; live?: boolean; progress?: { done: number; total: number | null } }) {
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
          {report.paper.title ?? "Untitled bibliography"}
        </h1>
        <p className="mt-3 text-sm text-ink-soft">
          {refs.length} references checked
          {m.seconds ? ` in ${m.seconds}s` : ""}
          {m.cost_usd ? ` · AI cost $${m.cost_usd.toFixed(3)}` : ""}
          {m.notes?.length ? ` · ${m.notes.join(" · ")}` : ""}
        </p>
      </div>

      {live && progress && (
        <div className="mt-6">
          <div className="h-1 overflow-hidden rounded-full bg-paper-deep">
            <div
              className="h-full bg-ink transition-[width] duration-500"
              style={{ width: progress.total ? `${(progress.done / progress.total) * 100}%` : "8%" }}
            />
          </div>
          <p className="mt-1.5 font-mono text-[0.7rem] text-ink-faint">
            checking… {progress.done}
            {progress.total ? ` / ${progress.total}` : ""}
          </p>
        </div>
      )}

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
          </button>
        ))}
        <button
          onClick={() => setFilter("retracted")}
          className={`col-span-2 flex flex-col items-start gap-3 p-4 text-left transition-colors sm:col-span-1 ${filter === "retracted" ? "bg-paper-deep" : "bg-card hover:bg-paper"}`}
        >
          <RetractedStamp nature="Retraction" />
          <span className="font-display text-4xl leading-none text-retracted">{retracted}</span>
        </button>
      </div>

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
      </div>

      {/* ledger */}
      <ol className="mt-4 overflow-hidden rounded-sm border border-ink/70 bg-card">
        {shown.map((r) => {
          const isOpen = open === r.idx;
          return (
            <li key={r.idx} className="ledger-row">
              <button
                onClick={() => setOpen(isOpen ? null : r.idx)}
                aria-expanded={isOpen}
                className="grid w-full grid-cols-[2.6rem_6.5rem_1fr_auto] items-center gap-3 px-4 py-3 text-left hover:bg-paper/60"
              >
                <span className="numerals-old text-right font-display text-xl text-ink-faint">{r.idx + 1}</span>
                <span className="flex flex-col items-start gap-1">
                  <Stamp status={r.status} size="sm" />
                  {r.retraction && <RetractedStamp nature={r.retraction.nature} />}
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-display text-[1.02rem]">{r.parsed.title ?? r.raw}</span>
                  <span className="block truncate text-xs text-ink-faint">
                    {r.parsed.authors.slice(0, 3).join(", ")}
                    {r.parsed.authors.length > 3 ? " et al." : ""}
                    {r.parsed.year ? ` · ${r.parsed.year}` : ""}
                    {r.status !== "verified" && r.issues[0] ? ` · ${r.issues[0]}` : ""}
                  </span>
                </span>
                <span className={`font-mono text-ink-faint transition-transform ${isOpen ? "rotate-90" : ""}`}>›</span>
              </button>
              {isOpen && <EvidenceCard r={r} />}
            </li>
          );
        })}
        {shown.length === 0 && <li className="px-4 py-8 text-center text-sm text-ink-faint italic">Nothing in this view.</li>}
      </ol>
    </div>
  );
}
