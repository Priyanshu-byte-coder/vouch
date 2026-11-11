import type { Report } from "@/lib/types";

function save(name: string, type: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

function slug(report: Report) {
  return (report.paper.source || "bibliography").replace(/[^\w.-]+/g, "_").slice(0, 60) || "report";
}

export function downloadJson(report: Report) {
  save(`vouch-${slug(report)}.json`, "application/json", JSON.stringify(report, null, 2));
}

const cell = (v: unknown) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function downloadCsv(report: Report) {
  const head = ["n", "status", "retraction", "cited_title", "cited_authors", "cited_year", "cited_doi", "matched_title", "matched_source", "matched_doi", "issues", "raw"];
  const rows = report.references.map((r) => [
    r.idx + 1,
    r.status,
    r.retraction?.nature ?? "",
    r.parsed.title,
    r.parsed.authors.join("; "),
    r.parsed.year,
    r.parsed.doi,
    r.match?.title,
    r.match?.source,
    r.match?.doi,
    r.issues.join(" | "),
    r.raw,
  ]);
  save(`vouch-${slug(report)}.csv`, "text/csv", [head, ...rows].map((row) => row.map(cell).join(",")).join("\n"));
}
