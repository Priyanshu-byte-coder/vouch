"use client";

import Link from "next/link";
import { use } from "react";
import { ReportView } from "@/components/report-view";
import mock from "@/lib/mock-report.json";
import type { Report } from "@/lib/types";

/** Step 4.1: "demo" shows a real report captured from the backend. Step 4.2 streams live jobs from the API. */
export function ReportLoader({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  if (id === "demo") return <ReportView report={mock as unknown as Report} />;
  return (
    <p className="font-display text-xl italic text-ink-soft">
      Live reports are wired up in step 4.2. Try the <Link className="text-link underline" href="/report/demo">demo report</Link>.
    </p>
  );
}
