import { RetractedStamp, Stamp } from "@/components/stamp";
import { STATUS_META, type Status } from "@/lib/types";

const ORDER: Status[] = ["verified", "detail_mismatch", "not_found", "cant_verify"];

/** What each stamp means, in one line. Used on the home page and above every report. */
export function Legend({ compact = false }: { compact?: boolean }) {
  return (
    <dl className={`grid gap-px overflow-hidden rounded-sm border border-rule bg-rule ${compact ? "sm:grid-cols-5" : "sm:grid-cols-2 lg:grid-cols-5"}`}>
      {ORDER.map((st) => (
        <div key={st} className="bg-card px-3.5 py-3">
          <dt>
            <Stamp status={st} size="sm" />
          </dt>
          <dd className={`mt-2 leading-snug text-ink-soft ${compact ? "text-[0.72rem]" : "text-xs"}`}>{STATUS_META[st].blurb}</dd>
        </div>
      ))}
      <div className="bg-card px-3.5 py-3">
        <dt>
          <RetractedStamp nature="Retraction" />
        </dt>
        <dd className={`mt-2 leading-snug text-ink-soft ${compact ? "text-[0.72rem]" : "text-xs"}`}>
          The work exists but has a retraction, concern or correction notice in Retraction Watch. Shown on top of any stamp.
        </dd>
      </div>
    </dl>
  );
}
