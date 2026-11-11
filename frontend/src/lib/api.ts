// Client for the Vouch API (backend/app/main.py).

import type { RefResult, Report } from "@/lib/types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export type JobKind = "arxiv" | "bibliography" | "pdf";

export interface JobSummary {
  id: string;
  kind: JobKind;
  label: string;
  status: "queued" | "running" | "done" | "error";
  error: string | null;
  created: number;
  n_refs: number | null;
  done_refs: number;
  report: Report | null;
  partial: RefResult[] | null;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function readError(res: Response): Promise<ApiError> {
  let msg = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") msg = body.detail;
    // FastAPI validation errors: [{msg: "Value error, send exactly one of ..."}]
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) msg = String(body.detail[0].msg).replace(/^Value error, /, "");
  } catch {
    /* not JSON */
  }
  return new ApiError(msg, res.status);
}

async function post(path: string, init: RequestInit): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", ...init });
  } catch {
    throw new ApiError("Can't reach the Vouch API. Is the backend running?", 0);
  }
  if (!res.ok) throw await readError(res);
  return (await res.json()).job_id as string;
}

export function startArxiv(arxivId: string) {
  return post("/api/check", { headers: { "content-type": "application/json" }, body: JSON.stringify({ arxiv_id: arxivId.trim() }) });
}

export function startBibliography(text: string) {
  return post("/api/check", { headers: { "content-type": "application/json" }, body: JSON.stringify({ bibliography: text }) });
}

export function startPdf(file: File) {
  const form = new FormData();
  form.append("file", file);
  return post("/api/check/pdf", { body: form });
}

export async function getJob(id: string): Promise<JobSummary> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
  } catch {
    throw new ApiError("Can't reach the Vouch API. Is the backend running?", 0);
  }
  if (!res.ok) throw await readError(res);
  return res.json();
}

export function eventsUrl(id: string) {
  return `${API_URL}/api/jobs/${encodeURIComponent(id)}/events`;
}
