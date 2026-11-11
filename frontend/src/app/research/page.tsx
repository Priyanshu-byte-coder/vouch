import research from "@/lib/research.json";

const ca = research.citeaudit300;
const ne = research.neurips100;

type Row = { label: string; better: "higher" | "lower"; base: number; ours: number; ci?: number[] };
const ROWS: Row[] = [
  { label: "Recall (fakes caught)", better: "higher", base: ca.baseline.recall!, ours: ca.vouch.recall!, ci: ca.ci95.recall },
  { label: "F1", better: "higher", base: ca.baseline.f1!, ours: ca.vouch.f1!, ci: ca.ci95.f1 },
  { label: "Precision", better: "higher", base: ca.baseline.precision!, ours: ca.vouch.precision!, ci: ca.ci95.precision },
  { label: "False-positive rate (real flagged)", better: "lower", base: ca.baseline.fpr!, ours: ca.vouch.fpr!, ci: ca.ci95.fpr },
];

function Bars() {
  const W = 560;
  const x = (v: number) => 150 + v * (W - 170);
  return (
    <svg viewBox={`0 0 ${W} ${ROWS.length * 58 + 20}`} className="w-full" role="img" aria-label="Baseline vs Vouch on CiteAudit-300">
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={6} y2={ROWS.length * 58 + 6} stroke="var(--rule)" strokeDasharray="2 3" />
          <text x={x(t)} y={ROWS.length * 58 + 18} textAnchor="middle" className="fill-ink-faint font-mono text-[9px]">
            {t.toFixed(2)}
          </text>
        </g>
      ))}
      {ROWS.map((r, i) => {
        const y = 14 + i * 58;
        return (
          <g key={r.label}>
            <text x={0} y={y + 12} className="fill-ink text-[11px]">
              {r.label}
            </text>
            <text x={0} y={y + 26} className="fill-ink-faint text-[9px] italic">
              {r.better} is better
            </text>
            <rect x={x(0)} y={y} width={x(r.base) - x(0)} height={13} fill="var(--unverified)" opacity={0.45} />
            <text x={x(r.base) + 5} y={y + 10} className="fill-ink-soft font-mono text-[9.5px]">
              {r.base.toFixed(3)} baseline
            </text>
            <rect x={x(0)} y={y + 17} width={x(r.ours) - x(0)} height={13} fill="var(--ink)" />
            {r.ci && (
              <g stroke="var(--mismatch)" strokeWidth={1.5}>
                <line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={y + 23.5} y2={y + 23.5} />
                <line x1={x(r.ci[0])} x2={x(r.ci[0])} y1={y + 19} y2={y + 28} />
                <line x1={x(r.ci[1])} x2={x(r.ci[1])} y1={y + 19} y2={y + 28} />
              </g>
            )}
            <text x={x(Math.max(r.ours, r.ci?.[1] ?? 0)) + 6} y={y + 27} className="fill-ink font-mono text-[9.5px] font-medium">
              {r.ours.toFixed(3)} Vouch
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Tally({ n, color, label }: { n: number; color: string; label: string }) {
  return (
    <div>
      <div className="flex flex-wrap gap-[3px]">
        {Array.from({ length: n }).map((_, i) => (
          <span key={i} className="h-3 w-3 rounded-[1px]" style={{ background: color }} />
        ))}
      </div>
      <p className="mt-2 text-sm text-ink-soft">
        <span className="font-display text-2xl text-ink">{n}</span> {label}
      </p>
    </div>
  );
}

function NeuripsGrid() {
  const caught = Math.round(ne.vouch.recall! * 100);
  const base = Math.round(ne.baseline.recall! * 100);
  return (
    <div className="grid w-fit grid-cols-10 gap-[3px]">
      {Array.from({ length: 100 }).map((_, i) => (
        <span
          key={i}
          className="h-3.5 w-3.5 rounded-[1px]"
          style={{ background: i < caught ? "var(--notfound)" : "var(--rule)", outline: i >= base && i < caught ? "1.5px solid var(--ink)" : "none", outlineOffset: 1 }}
          title={i < caught ? (i >= base ? "caught by Vouch, missed by the baseline" : "caught") : "missed"}
        />
      ))}
    </div>
  );
}

function Frontier() {
  const pts = research.dev.frontier.filter((p) => p.fpr_cap <= 0.12);
  const W = 300, H = 150;
  const x = (v: number) => 34 + ((v - 0.05) / (0.125 - 0.05)) * (W - 50);
  const y = (v: number) => H - 24 - ((v - 0.6) / 0.3) * (H - 40);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.fpr).toFixed(1)},${y(p.recall).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-sm" role="img" aria-label="Recall vs false-positive rate on dev">
      <line x1={34} x2={W - 10} y1={H - 24} y2={H - 24} stroke="var(--ink-faint)" />
      <line x1={34} x2={34} y1={10} y2={H - 24} stroke="var(--ink-faint)" />
      <text x={W / 2} y={H - 4} textAnchor="middle" className="fill-ink-faint text-[9px]">false-positive rate</text>
      <text x={10} y={H / 2} transform={`rotate(-90 10 ${H / 2})`} textAnchor="middle" className="fill-ink-faint text-[9px]">recall</text>
      <path d={d} fill="none" stroke="var(--ink)" strokeWidth={1.6} />
      {pts.map((p) => (
        <circle key={p.fpr_cap} cx={x(p.fpr)} cy={y(p.recall)} r={2.8} fill="var(--card)" stroke="var(--ink)" />
      ))}
      <line x1={x(0.1)} x2={x(0.1)} y1={10} y2={H - 24} stroke="var(--mismatch)" strokeDasharray="3 3" />
      <text x={x(0.1) + 3} y={18} className="fill-mismatch text-[9px]">our cap</text>
    </svg>
  );
}

const FINDINGS = [
  ["No single index is enough.", "Semantic Scholar has no record for the DOI of LeCun, Bengio & Hinton's “Deep learning” (Nature 2015), and Crossref's top hit for “Attention Is All You Need” is a 2025 copy. Adding Semantic Scholar as a sixth source cut false alarms on dev by 20%."],
  ["Lenient title matching hides fakes.", "The baseline's title similarity gives “Deep learning” a perfect score against “PyTorch: … Deep Learning Library”. Strict, length-aware matching plus author checks is where most of the +25 points of recall come from."],
  ["An LLM judge made things worse.", "Asked whether a record is the same work, the model accepted 89 fakes for every 4 real references it rescued, because it forgives one or two invented names in a long author list. Cross-validation switched it off in 5 of 5 folds."],
  ["Thresholds are a policy choice.", "Maximising F1 alone would flag one real reference in five. We tune for the best F1 with at most 10% of real references flagged, and show the trade-off."],
];

const LIMITS = [
  "On CiteAudit-300 the false-positive rate (0.140) is not lower than the baseline's (0.121); the difference is within the confidence interval (20 vs 18 false alarms on the same citations).",
  "Records without author lists can verify a citation on title alone (the one NeurIPS miss). The fix is known but was not applied after the last test run.",
  "Very recent preprints and books in new editions are the main sources of false alarms; scholarly indexes lag behind arXiv.",
  "CiteAudit counts any invented field as a hallucinated citation. Under a looser definition, the “detail mismatch” label would be read as a warning, not a fake.",
];

export default function ResearchPage() {
  const p = ca.paired;
  return (
    <div className="mx-auto max-w-6xl px-6 pt-14">
      <header className="rise max-w-3xl">
        <p className="font-mono text-[0.7rem] tracking-[0.2em] text-ink-faint uppercase">Research · RQ1 · detecting fabricated references</p>
        <h1 className="mt-3 font-display text-5xl leading-[1.02] font-medium tracking-tight">
          Does checking six open indexes beat a <span className="italic">single-index</span> checker?
        </h1>
        <p className="mt-5 font-display text-lg leading-relaxed text-ink-soft">
          Compared on the same benchmark the published baseline used, with thresholds tuned on separate data and the test set
          kept aside.
        </p>
      </header>

      <section className="mt-14 grid gap-12 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <h2 className="font-display text-2xl italic">CiteAudit-300 · 150 real, 150 fake citations</h2>
          <p className="mt-1 mb-5 text-sm text-ink-soft">
            Baseline: AtomGPT hallucination detector (Semantic Scholar only), its released per-citation outputs. Vouch: frozen
            configuration, 95% bootstrap intervals in ochre.
          </p>
          <Bars />
        </div>
        <div className="space-y-10">
          <div>
            <h3 className="font-display text-xl italic">Same {p.n_common} citations, head to head</h3>
            <p className="mt-1 mb-4 text-sm text-ink-soft">Cases where exactly one of the two systems was right.</p>
            <div className="space-y-4">
              <Tally n={p.only_ours_correct} color="var(--ink)" label="only Vouch correct" />
              <Tally n={p.only_baseline_correct} color="var(--unverified)" label="only the baseline correct" />
            </div>
            <p className="mt-3 font-mono text-xs text-ink-faint">exact McNemar test, p = {p.mcnemar_p.toExponential(0)}</p>
          </div>
          <div>
            <h3 className="font-display text-xl italic">100 hallucinated citations from accepted NeurIPS 2025 papers</h3>
            <p className="mt-1 mb-4 text-sm text-ink-soft">
              Vouch flags {Math.round(ne.vouch.recall! * 100)}; the baseline {Math.round(ne.baseline.recall! * 100)}. Outlined: caught only by Vouch.
            </p>
            <NeuripsGrid />
          </div>
        </div>
      </section>

      <section className="mt-20 grid gap-12 lg:grid-cols-[1fr_1.5fr]">
        <div>
          <h2 className="font-display text-2xl italic">The trade-off we chose</h2>
          <p className="mt-1 mb-4 text-sm text-ink-soft">Development set (1,000 citations), best recall achievable at each false-positive budget.</p>
          <Frontier />
          <p className="mt-3 text-xs text-ink-faint">
            Dev, 5-fold cross-validated: F1 {research.dev.cv5.f1!.toFixed(3)}, false-positive rate {research.dev.cv5.fpr!.toFixed(3)}.
          </p>
        </div>
        <div>
          <h2 className="font-display text-2xl italic">What we learned</h2>
          <ol className="mt-4 space-y-5">
            {FINDINGS.map(([t, b], i) => (
              <li key={t} className="grid grid-cols-[2rem_1fr] gap-2">
                <span className="font-display text-2xl text-ink-faint italic">{i + 1}</span>
                <p className="text-sm leading-relaxed text-ink-soft">
                  <span className="font-semibold text-ink">{t}</span> {b}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mt-20 grid gap-12 border-t border-rule pt-10 lg:grid-cols-2">
        <div>
          <h2 className="font-display text-2xl italic">Protocol</h2>
          <ul className="mt-4 space-y-2 text-sm leading-relaxed text-ink-soft">
            <li>Development: 1,000 CiteAudit citations, with exact and near-duplicates of test items removed.</li>
            <li>Weights and thresholds tuned on development only, 5-fold cross-validated, under a 10% false-positive cap.</li>
            <li>Test sets used twice, both runs reported: five sources (F1 0.781), then six sources (F1 0.792).</li>
            <li>Every number comes from a script in the repository and a committed results file.</li>
          </ul>
        </div>
        <div>
          <h2 className="font-display text-2xl italic">Limitations</h2>
          <ul className="mt-4 space-y-2 text-sm leading-relaxed text-ink-soft">
            {LIMITS.map((l) => (
              <li key={l} className="flex gap-2">
                <span className="text-mismatch">¶</span>
                <span>{l}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}
