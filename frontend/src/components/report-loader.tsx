"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { ReportView } from "@/components/report-view";
import { ApiError, eventsUrl, getJob, type JobKind } from "@/lib/api";
import mock from "@/lib/mock-report.json";
import type { RefResult, Report } from "@/lib/types";

/** "demo" shows a real report captured from the backend; any other id is a live job streamed from the API. */
export function ReportLoader({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  if (id === "demo") return <ReportView report={mock as unknown as Report} />;
  return <LiveReport key={id} id={id} />;
}

interface Live {
  phase: "connecting" | "queued" | "reading" | "checking" | "done" | "error";
  kind: JobKind | null;
  label: string;
  title: string | null;
  notes: string[];
  nRefs: number | null;
  refs: Record<number, RefResult>;
  report: Report | null;
  error: string | null;
  expired: boolean;
  started: number;
}

const SOURCE_PREFIX: Record<JobKind, string> = { arxiv: "arxiv:", pdf: "pdf:", bibliography: "" };

function LiveReport({ id }: { id: string }) {
  const [s, setS] = useState<Live>({
    phase: "connecting",
    kind: null,
    label: "",
    title: null,
    notes: [],
    nRefs: null,
    refs: {},
    report: null,
    error: null,
    expired: false,
    started: 0,
  });
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;
    const patch = (p: Partial<Live> | ((prev: Live) => Partial<Live>)) =>
      setS((prev) => ({ ...prev, ...(typeof p === "function" ? p(prev) : p) }));

    getJob(id)
      .then((job) => {
        if (closed) return;
        const base = { kind: job.kind, label: job.label, nRefs: job.n_refs, started: job.created * 1000 };
        if (job.report) return patch({ ...base, phase: "done", report: job.report });
        if (job.status === "error") return patch({ ...base, phase: "error", error: job.error });
        patch({ ...base, phase: job.status === "queued" ? "queued" : "reading" });

        // The stream replays every event from the start, so a reload rebuilds the same state.
        es = new EventSource(eventsUrl(id));
        es.addEventListener("status", () => patch({ phase: "reading" }));
        es.addEventListener("parsed", (e) => {
          const d = JSON.parse((e as MessageEvent).data);
          patch({ phase: "checking", nRefs: d.n_refs, title: d.title ?? null, notes: d.notes ?? [] });
        });
        es.addEventListener("ref_done", (e) => {
          const r: RefResult = JSON.parse((e as MessageEvent).data);
          patch((prev) => ({ phase: "checking", refs: { ...prev.refs, [r.idx]: r } }));
        });
        es.addEventListener("report", (e) => {
          patch({ phase: "done", report: JSON.parse((e as MessageEvent).data) });
          es?.close();
        });
        es.addEventListener("error", (e) => {
          const data = (e as MessageEvent).data;
          if (data) {
            // the pipeline failed: an "error" event sent by the server
            patch({ phase: "error", error: JSON.parse(data).error });
            es?.close();
          } else if (es?.readyState === EventSource.CLOSED) {
            // the connection failed and the browser gave up (server down or job gone)
            patch({ phase: "error", error: "Lost the connection to the Vouch API." });
          }
          // otherwise the browser is reconnecting and replays from the last event id
        });
      })
      .catch((err) => {
        if (closed) return;
        const expired = err instanceof ApiError && err.status === 404;
        patch({ phase: "error", expired, error: err instanceof Error ? err.message : String(err) });
      });

    return () => {
      closed = true;
      es?.close();
    };
  }, [id]);

  const running = s.phase !== "done" && s.phase !== "error";
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [running]);

  if (s.phase === "error") return <Failed expired={s.expired} message={s.error} />;
  // remount when finished so the view opens on "Needs attention" if anything was flagged
  if (s.report) return <ReportView key="final" report={s.report} />;

  const refs = Object.values(s.refs).sort((a, b) => a.idx - b.idx);
  const elapsed = s.started ? Math.max(0, Math.round((now - s.started) / 1000)) : 0;
  const partial: Report = {
    paper: {
      title: s.title ?? (s.kind === "bibliography" ? null : s.label || null),
      source: s.kind ? `${SOURCE_PREFIX[s.kind]}${s.label}` : "…",
      n_refs: s.nRefs ?? refs.length,
    },
    summary: { verified: 0, detail_mismatch: 0, not_found: 0, cant_verify: 0, retracted: 0, claims_checked: 0, claims_unsupported: 0, tortured_hits: 0 },
    references: refs,
    tortured: [],
    meta: { models: {}, seconds: 0, llm_calls: 0, llm_tokens_in: 0, llm_tokens_out: 0, cost_usd: 0, api_calls: {}, cache_hits: 0, notes: s.notes },
  };
  return <ReportView key="live" report={partial} live={{ phase: s.phase === "done" ? "checking" : s.phase, kind: s.kind, done: refs.length, total: s.nRefs, elapsed }} />;
}

function Failed({ expired, message }: { expired: boolean; message: string | null }) {
  return (
    <div className="rise max-w-2xl">
      <span className="stamp inline-block -rotate-3 rounded-[3px] border-2 border-notfound px-3 py-1 text-sm font-bold tracking-[0.2em] text-notfound uppercase">
        {expired ? "Expired" : "Check failed"}
      </span>
      <h1 className="mt-6 font-display text-3xl leading-tight font-medium">
        {expired ? "This report is no longer on the server." : "The check could not finish."}
      </h1>
      <p className="mt-3 text-ink-soft">
        {expired
          ? "Reports are kept in memory for a while and then dropped. Run the check again; papers checked before come back from the cache in seconds."
          : message}
      </p>
      <div className="mt-6 flex gap-3 text-sm">
        <Link href="/" className="rounded-sm border-2 border-ink bg-ink px-4 py-1.5 font-semibold text-card hover:bg-transparent hover:text-ink">
          New check
        </Link>
        <Link href="/report/demo" className="rounded-sm border border-rule px-4 py-1.5 text-ink-soft hover:border-ink-soft">
          See the demo report
        </Link>
      </div>
    </div>
  );
}
