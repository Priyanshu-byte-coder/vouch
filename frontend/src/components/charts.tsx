/* Small, dependency-free charts for the research page. Server components; hand-drawn SVG in the paper/ink palette. */

export const BASE = "var(--unverified)";
export const OURS = "var(--ink)";

export function Caption({ children }: { children: React.ReactNode }) {
  return <p className="mt-2 text-xs leading-relaxed text-ink-faint">{children}</p>;
}

export function ChartTitle({ kicker, title }: { kicker?: string; title: string }) {
  return (
    <div className="mb-3">
      {kicker && <p className="font-mono text-[0.65rem] tracking-[0.18em] text-ink-faint uppercase">{kicker}</p>}
      <h3 className="font-display text-xl leading-snug italic">{title}</h3>
    </div>
  );
}

/* ---------- paired horizontal bars (baseline vs Vouch), with optional CI ---------- */
export type PairRow = { label: string; sub?: string; base: number; ours: number; ci?: number[]; fmt?: (v: number) => string };

export function PairBars({ rows, max = 1, baseLabel = "baseline", oursLabel = "Vouch" }: { rows: PairRow[]; max?: number; baseLabel?: string; oursLabel?: string }) {
  const W = 600, L = 190, rowH = 54;
  const x = (v: number) => L + (v / max) * (W - L - 70);
  const f = (r: PairRow, v: number) => (r.fmt ? r.fmt(v) : v.toFixed(3));
  return (
    <svg viewBox={`0 0 ${W} ${rows.length * rowH + 16}`} className="w-full" role="img">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={x(t * max)} x2={x(t * max)} y1={4} y2={rows.length * rowH + 2} stroke="var(--rule)" strokeDasharray="2 3" />
          <text x={x(t * max)} y={rows.length * rowH + 14} textAnchor="middle" className="fill-ink-faint font-mono text-[9px]">
            {max === 1 ? t.toFixed(2) : Math.round(t * max)}
          </text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = 10 + i * rowH;
        return (
          <g key={r.label}>
            <text x={0} y={y + 12} className="fill-ink text-[11px] font-medium">{r.label}</text>
            {r.sub && <text x={0} y={y + 25} className="fill-ink-faint text-[9px] italic">{r.sub}</text>}
            <rect x={x(0)} y={y} width={Math.max(0, x(r.base) - x(0))} height={12} fill={BASE} opacity={0.5} />
            <text x={x(r.base) + 5} y={y + 10} className="fill-ink-soft font-mono text-[9px]">{f(r, r.base)} {baseLabel}</text>
            <rect x={x(0)} y={y + 16} width={Math.max(0, x(r.ours) - x(0))} height={12} fill={OURS} />
            {r.ci && (
              <g stroke="var(--mismatch)" strokeWidth={1.5}>
                <line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={y + 22} y2={y + 22} />
                <line x1={x(r.ci[0])} x2={x(r.ci[0])} y1={y + 18} y2={y + 26} />
                <line x1={x(r.ci[1])} x2={x(r.ci[1])} y1={y + 18} y2={y + 26} />
              </g>
            )}
            <text x={x(Math.max(r.ours, r.ci?.[1] ?? 0)) + 6} y={y + 26} className="fill-ink font-mono text-[9px] font-semibold">{f(r, r.ours)} {oursLabel}</text>
          </g>
        );
      })}
    </svg>
  );
}

/* ---------- 2×2 confusion matrix ---------- */
export function Confusion({ title, TP, FN, FP, TN, tone }: { title: string; TP: number; FN: number; FP: number; TN: number; tone: "base" | "ours" }) {
  const n = TP + FN + FP + TN;
  const cell = (v: number, good: boolean, label: string) => (
    <div
      className="flex aspect-[1.6] flex-col justify-between p-2.5"
      style={{
        background: good ? (tone === "ours" ? "var(--ink)" : "var(--unverified)") : v === 0 ? "var(--card)" : "var(--notfound)",
        opacity: good ? 0.55 + 0.45 * (v / Math.max(TP, TN)) : v === 0 ? 1 : 0.35 + 0.65 * (v / Math.max(FN, FP, 1)),
        color: good && tone === "ours" ? "var(--card)" : "var(--ink)",
      }}
    >
      <span className="font-display text-2xl leading-none">{v}</span>
      <span className="text-[0.62rem] leading-tight">{label}</span>
    </div>
  );
  return (
    <div>
      <p className="mb-2 text-sm font-medium">{title}</p>
      <div className="grid grid-cols-[3.2rem_1fr_1fr] gap-px text-[0.62rem] text-ink-faint">
        <span />
        <span className="pb-1 text-center">said verified</span>
        <span className="pb-1 text-center">flagged</span>
        <span className="flex items-center justify-end pr-2 text-right">real</span>
        {cell(TN, true, "correctly passed")}
        {cell(FP, false, "false alarm")}
        <span className="flex items-center justify-end pr-2 text-right">fake</span>
        {cell(FN, false, "missed fake")}
        {cell(TP, true, "caught")}
      </div>
      <Caption>
        n = {n}. Errors in red: {FP} real references wrongly flagged, {FN} fakes passed.
      </Caption>
    </div>
  );
}

/* ---------- stacked horizontal bar ---------- */
export type Segment = { label: string; value: number; color: string; muted?: boolean };

export function Stacked({ segments, total, height = 22 }: { segments: Segment[]; total?: number; height?: number }) {
  const t = total ?? segments.reduce((a, s) => a + s.value, 0);
  return (
    <div>
      <div className="flex w-full overflow-hidden rounded-sm border border-ink/30" style={{ height }}>
        {segments.map((s) => (
          <span
            key={s.label}
            title={`${s.label}: ${s.value}`}
            className="flex items-center justify-center overflow-hidden font-mono text-[0.62rem] text-card"
            style={{ width: `${(s.value / t) * 100}%`, background: s.color, opacity: s.muted ? 0.45 : 1 }}
          >
            {s.value / t > 0.07 ? s.value : ""}
          </span>
        ))}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[0.68rem] text-ink-soft">
        {segments.map((s) => (
          <span key={s.label} className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-[1px]" style={{ background: s.color, opacity: s.muted ? 0.45 : 1 }} />
            {s.label} <span className="font-mono text-ink-faint">{s.value}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------- slope chart: a metric across stages ---------- */
export function Slope({ stages, series }: { stages: string[]; series: { name: string; color: string; values: number[]; dashed?: boolean }[] }) {
  const W = 520, H = 190, L = 40, R = 70, T = 16, B = 44;
  const all = series.flatMap((s) => s.values);
  const lo = Math.max(0, Math.floor((Math.min(...all) - 0.05) * 10) / 10), hi = Math.min(1, Math.ceil((Math.max(...all) + 0.05) * 10) / 10);
  const x = (i: number) => L + (i / (stages.length - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img">
      {stages.map((s, i) => (
        <g key={s}>
          <line x1={x(i)} x2={x(i)} y1={T} y2={H - B} stroke="var(--rule)" />
          {s.split("\n").map((line, k) => (
            <text key={k} x={x(i)} y={H - B + 14 + k * 11} textAnchor="middle" className="fill-ink-soft text-[9px]">{line}</text>
          ))}
        </g>
      ))}
      {series.map((s) => (
        <g key={s.name}>
          <path d={s.values.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join(" ")} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dashed ? "4 3" : undefined} />
          {s.values.map((v, i) => (
            <g key={i}>
              <circle cx={x(i)} cy={y(v)} r={s.dashed ? 2 : 3.2} fill="var(--card)" stroke={s.color} strokeWidth={s.dashed ? 1.2 : 2} />
              {!s.dashed && <text x={x(i)} y={y(v) - 7} textAnchor="middle" className="font-mono text-[9px]" style={{ fill: s.color }}>{v.toFixed(3)}</text>}
            </g>
          ))}
          <text x={x(stages.length - 1) + 8} y={y(s.values[s.values.length - 1]) + (s.dashed ? 10 : -2)} className="text-[9px] font-medium" style={{ fill: s.color }}>
            {s.name}{s.dashed ? ` ${s.values[s.values.length - 1].toFixed(3)}` : ""}
          </text>
        </g>
      ))}
    </svg>
  );
}

/* ---------- a field of small squares (one per item) ---------- */
export function Squares({ groups, size = 10 }: { groups: { n: number; color: string; label: string; outline?: boolean }[]; size?: number }) {
  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.label}>
          <div className="flex flex-wrap gap-[3px]">
            {Array.from({ length: g.n }).map((_, i) => (
              <span key={i} className="rounded-[1px]" style={{ width: size, height: size, background: g.outline ? "transparent" : g.color, outline: g.outline ? `1.5px solid ${g.color}` : "none", outlineOffset: -1 }} />
            ))}
          </div>
          <p className="mt-1.5 text-sm text-ink-soft">
            <span className="font-display text-2xl text-ink">{g.n}</span> {g.label}
          </p>
        </div>
      ))}
    </div>
  );
}

/* ---------- step line for the tuning story ---------- */
export function Steps({ items }: { items: { label: string; value: number; note?: string; emphasis?: boolean }[] }) {
  const max = 1;
  return (
    <ol className="space-y-2.5">
      {items.map((it, i) => (
        <li key={it.label} className="grid grid-cols-[1.4rem_1fr] items-start gap-2">
          <span className="font-display text-lg text-ink-faint italic">{i + 1}</span>
          <div>
            <div className="flex items-baseline justify-between gap-3">
              <span className={`text-sm ${it.emphasis ? "font-semibold" : ""}`}>{it.label}</span>
              <span className="font-mono text-xs">{it.value.toFixed(3)}</span>
            </div>
            <div className="mt-1 h-2 rounded-full bg-paper-deep">
              <div className="h-full rounded-full" style={{ width: `${(it.value / max) * 100}%`, background: it.emphasis ? "var(--ink)" : "var(--ink-faint)" }} />
            </div>
            {it.note && <p className="mt-0.5 text-[0.68rem] text-ink-faint">{it.note}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

/* ---------- proportional strip of a dataset split ---------- */
export function SplitStrip({ parts, total }: { parts: { label: string; n: number; color: string; muted?: boolean }[]; total: number }) {
  return (
    <div>
      <div className="flex h-7 w-full overflow-hidden rounded-sm border border-ink/40">
        {parts.map((p) => (
          <span key={p.label} className="h-full" style={{ width: `${(p.n / total) * 100}%`, background: p.color, opacity: p.muted ? 0.35 : 1 }} title={`${p.label}: ${p.n.toLocaleString()}`} />
        ))}
      </div>
      <div className="mt-2 grid gap-x-4 gap-y-1 text-xs text-ink-soft sm:grid-cols-2">
        {parts.map((p) => (
          <span key={p.label} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-[1px]" style={{ background: p.color, opacity: p.muted ? 0.35 : 1 }} />
            <span className="font-mono text-ink">{p.n.toLocaleString()}</span> {p.label}
          </span>
        ))}
      </div>
    </div>
  );
}
