import { Suspense } from "react";
import { ReportLoader } from "@/components/report-loader";

export default function ReportPage({ params }: PageProps<"/report/[id]">) {
  return (
    <div className="mx-auto max-w-6xl px-6 pt-12">
      <Suspense fallback={<p className="font-mono text-sm text-ink-faint">Opening report…</p>}>
        <ReportLoader params={params} />
      </Suspense>
    </div>
  );
}
