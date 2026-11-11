import { Caption, ChartTitle, Confusion, PairBars, Slope, SplitStrip, Squares, Stacked, Steps, BASE, OURS } from "@/components/charts";
import { Stamp } from "@/components/stamp";
import research from "@/lib/research.json";
import { SOURCE_LABEL, STATUS_META } from "@/lib/types";

const ca = research.citeaudit300;
const ne = research.neurips100;
const S = research.story;
const AB = S.ablations.dev_1000;
const AM = AB.matching as Record<string, { f1: number; recall: number; fpr: number }>;
const AB_COST = AB.cost;
const SF = S.scifact;
const AUraw = S.audit as unknown as { references: number; papers_with_confirmed_problem: number; flag_precision_hand_labelled: number; hand_labels: Record<string, number>; flag_causes: Record<string, number> };
const AU = (() => {
  const h = AUraw.hand_labels;
  const correct = Object.entries(h).filter(([k]) => k.endsWith("|correct")).reduce((a, [, v]) => a + v, 0);
  const wrong = Object.entries(h).filter(([k]) => k.endsWith("|wrong")).reduce((a, [, v]) => a + v, 0);
  const causes = Object.entries(AUraw.flag_causes).filter(([k]) => !k.startsWith("fabricated") && !k.startsWith("real error") && k !== "unsure") as [string, number][];
  return { references: AUraw.references, papers_with_confirmed_problem: AUraw.papers_with_confirmed_problem, precision: AUraw.flag_precision_hand_labelled,
           correct, wrong, flags_total: Object.values(h).reduce((a, b) => a + b, 0), fabricated: AUraw.flag_causes["fabricated details (invented authors, title or venue)"] ?? 0, causes };
})();
const CV = S.coverage as unknown as { n: number; cells: Record<string, Record<string, { n: number; fpr: number; hard_rate: number }>> };
const n = (o: Record<string, number>, k: string) => o[k] ?? 0;
const pct = (v: number) => `${Math.round(v * 100)}%`;

const C = { verified: "var(--verified)", detail_mismatch: "var(--mismatch)", not_found: "var(--notfound)", cant_verify: "var(--unverified)" };
const SRC_COLOR: Record<string, string> = { crossref: "#1f3a5f", openalex: "#2e6a55", s2: "#a8640f", arxiv: "#9e2b25", datacite: "#5b6670", openlibrary: "#7a1d33" };

function fakeSegments(labels: Record<string, number>) {
  return [
    { label: "passed as verified (missed)", value: n(labels, "verified"), color: "var(--notfound)", muted: true },
    { label: "unverified", value: n(labels, "cant_verify"), color: C.cant_verify },
    { label: "detail mismatch", value: n(labels, "detail_mismatch"), color: C.detail_mismatch },
    { label: "not found", value: n(labels, "not_found"), color: C.not_found },
  ];
}
function realSegments(labels: Record<string, number>) {
  return [
    { label: "verified (correct)", value: n(labels, "verified"), color: C.verified },
    { label: "unverified (false alarm)", value: n(labels, "cant_verify"), color: C.cant_verify },
    { label: "mismatch (false alarm)", value: n(labels, "detail_mismatch"), color: C.detail_mismatch },
    { label: "not found (false alarm)", value: n(labels, "not_found"), color: C.not_found },
  ];
}
function baselineSegments(labels: Record<string, number>, truth: "real" | "fake") {
  const v = n(labels, "verified");
  return [
    truth === "fake"
      ? { label: "passed as verified (missed)", value: v, color: "var(--notfound)", muted: true }
      : { label: "verified (correct)", value: v, color: C.verified },
    { label: truth === "fake" ? "partial" : "partial (false alarm)", value: n(labels, "partial"), color: C.detail_mismatch },
    { label: truth === "fake" ? "likely hallucinated" : "likely hallucinated (false alarm)", value: n(labels, "likely hallucinated"), color: C.not_found },
  ];
}

function Big({ v, k, sub }: { v: string; k: string; sub: string }) {
  return (
    <div className="bg-card p-5">
      <p className="font-mono text-[0.62rem] tracking-widest text-ink-faint uppercase">{k}</p>
      <p className="mt-1.5 font-display text-4xl tracking-tight">{v}</p>
      <p className="mt-1 text-xs text-ink-soft">{sub}</p>
    </div>
  );
}

function Section({ kicker, title, lede, children }: { kicker: string; title: string; lede?: string; children: React.ReactNode }) {
  return (
    <section className="mt-16 border-t border-rule pt-8">
      <div className="mb-7 max-w-3xl">
        <p className="font-mono text-[0.65rem] tracking-[0.2em] text-ink-faint uppercase">{kicker}</p>
        <h2 className="mt-1.5 font-display text-3xl leading-tight">{title}</h2>
        {lede && <p className="mt-2 text-sm leading-relaxed text-ink-soft">{lede}</p>}
      </div>
      {children}
    </section>
  );
}

export default function ResearchPage() {
  const p = ca.paired;
  const d = S.data;
  const winTest = S.test.winning_source_real_verified as Record<string, number>;
  const winDev = S.dev.winning_source_real_verified as Record<string, number>;
  const kindTest = S.test.fake_mismatch_issue_kind as Record<string, number>;
  const kindDev = S.dev.fake_mismatch_issue_kind as Record<string, number>;
  const fakeTest = S.test.labels_by_truth.fake as Record<string, number>;
  const realTest = S.test.labels_by_truth.real as Record<string, number>;
  const baseFake = S.baseline_labels_by_truth.fake as Record<string, number>;
  const baseReal = S.baseline_labels_by_truth.real as Record<string, number>;
  const neLabels = S.neurips_labels as Record<string, number>;
  const gridSize = Object.values(S.grid.thresholds).reduce((a, v) => a * v.length, 1) * Object.values(S.grid.weights).reduce((a, v) => a * v.length, 1);
  const srcSeg = (w: Record<string, number>) =>
    Object.entries(w)
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) => ({ label: SOURCE_LABEL[k] ?? k, value: v, color: SRC_COLOR[k] ?? "var(--ink)" }));

  return (
    <div className="mx-auto max-w-6xl px-6 pt-14 pb-10">
      <header className="rise grid gap-8 lg:grid-cols-[1.2fr_1fr] lg:items-end">
        <div>
          <p className="font-mono text-[0.7rem] tracking-[0.2em] text-ink-faint uppercase">Research · RQ1 · fabricated references</p>
          <h1 className="mt-3 font-display text-5xl leading-[1.02] font-medium tracking-tight">
            Six open indexes beat <span className="italic">one</span>.
          </h1>
          <p className="mt-4 max-w-xl text-sm leading-relaxed text-ink-soft">
            Same benchmark as the published AtomGPT detector (Semantic Scholar only). Thresholds tuned on separate data, test set
            touched twice, both results shown. Every number traces to a script and a committed results file.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-sm border border-ink/70 bg-ink/70">
          <Big v={ca.vouch.f1!.toFixed(2)} k="F1" sub={`baseline ${ca.baseline.f1!.toFixed(2)}`} />
          <Big v={pct(ca.vouch.recall!)} k="fakes caught" sub={`baseline ${pct(ca.baseline.recall!)}`} />
          <Big v={`${p.only_ours_correct}:${p.only_baseline_correct}`} k="head to head" sub="citations only one got right" />
        </div>
      </header>

      {/* 1. data */}
      <Section kicker="1 · What we tested on" title="One public benchmark, split so the test set never taught us anything." lede="CiteAudit (9,442 citations, half invented by language models, half from real papers). The 300-item test set is the one the baseline published numbers on. Everything near it was removed from tuning data.">
        <div className="grid gap-8 lg:grid-cols-[1.6fr_1fr]">
          <div>
            <SplitStrip
              total={d.citeaudit_total}
              parts={[
                { label: "test · CiteAudit-300 (150 real / 150 fake), the baseline’s own set", n: d.test_citeaudit300, color: "var(--notfound)" },
                { label: "copies and near-copies of test items, removed", n: d.removed_exact + d.removed_near - d.test_citeaudit300, color: "var(--mismatch)" },
                { label: "dev · 1,000 sampled (500 / 500) for tuning", n: d.dev_1000, color: "var(--ink)" },
                { label: "rest of the pool, unused", n: d.dev_full - d.dev_1000, color: "var(--ink-faint)", muted: true },
              ]}
            />
            <Caption>Near-copies = same reference with different formatting (token-sort similarity ≥ 95). Without this step, test answers leak into tuning.</Caption>
          </div>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-rule bg-rule">
            <Big v="100" k="NeurIPS-100" sub="confirmed fabricated citations in accepted NeurIPS 2025 papers (2nd test set)" />
            <Big v={d.retraction_notices.toLocaleString()} k="Retraction Watch" sub="notices indexed for the retraction check" />
          </div>
        </div>
      </Section>

      {/* 2. tuning */}
      <Section kicker="2 · How we tuned" title="A grid search on dev with a false-alarm budget, cross-validated." lede={`${gridSize.toLocaleString()} weight–threshold combinations replayed offline on the 1,000 dev citations. Objective: best F1 with at most 10% of real references flagged. Ties go to fewer false alarms.`}>
        <div className="grid gap-10 lg:grid-cols-3">
          <div>
            <ChartTitle kicker="F1 on dev" title="Before, after, and the honest estimate" />
            <Steps
              items={[
                { label: "Shipped defaults", value: S.dev_default.f1, note: `recall ${pct(S.dev_default.recall)} · FPR ${pct(S.dev_default.fpr!)}` },
                { label: "Tuned, scored on the same data", value: S.dev_tuned_in_sample.f1, note: "optimistic: it saw these citations" },
                { label: "Tuned, 5-fold cross-validated", value: S.dev_cv5.f1, note: `recall ${pct(S.dev_cv5.recall)} · FPR ${pct(S.dev_cv5.fpr!)} · what we expected on test`, emphasis: true },
              ]}
            />
          </div>
          <div>
            <ChartTitle kicker="Trade-off" title="Recall at each false-alarm budget" />
            <Frontier />
            <Caption>Pure F1 would pick FPR 0.19: one real reference in five flagged. We capped it at 0.10 (dashed), below the baseline’s 0.12.</Caption>
          </div>
          <div>
            <ChartTitle kicker="Stability" title="What each fold chose" />
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left font-mono text-[0.62rem] tracking-wider text-ink-faint uppercase">
                  <th className="pb-1 font-normal">fold</th>
                  <th className="pb-1 font-normal">verified ≥</th>
                  <th className="pb-1 font-normal">title ≥</th>
                  <th className="pb-1 font-normal">authors ≥</th>
                  <th className="pb-1 font-normal">year ±</th>
                  <th className="pb-1 font-normal">w authors</th>
                </tr>
              </thead>
              <tbody className="font-mono">
                {S.fold_configs.map((f, i) => (
                  <tr key={i} className="border-t border-rule">
                    <td className="py-1 text-ink-faint">{i + 1}</td>
                    <td className={f.verified === S.frozen.thresholds.verified ? "font-semibold" : "text-ink-faint"}>{f.verified}</td>
                    <td className={f.title_min === S.frozen.thresholds.title_min ? "font-semibold" : "text-ink-faint"}>{f.title_min}</td>
                    <td className={f.author_min === S.frozen.thresholds.author_min ? "font-semibold" : "text-ink-faint"}>{f.author_min}</td>
                    <td className={f.year_tolerance === S.frozen.thresholds.year_tolerance ? "font-semibold" : "text-ink-faint"}>{f.year_tolerance}</td>
                    <td className={f.w_authors === S.frozen.weights.authors ? "font-semibold" : "text-ink-faint"}>{f.w_authors}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-ink">
                  <td className="py-1 text-ink-faint">frozen</td>
                  <td className="font-semibold">{S.frozen.thresholds.verified}</td>
                  <td className="font-semibold">{S.frozen.thresholds.title_min}</td>
                  <td className="font-semibold">{S.frozen.thresholds.author_min}</td>
                  <td className="font-semibold">{S.frozen.thresholds.year_tolerance}</td>
                  <td className="font-semibold">{S.frozen.weights.authors}</td>
                </tr>
              </tbody>
            </table>
            <Caption>Bold = agrees with the frozen configuration. Strict title (95) was chosen in every fold; the author bar moved between 60 and 100.</Caption>
          </div>
        </div>
      </Section>

      {/* 3. head to head */}
      <Section kicker="3 · Head to head on CiteAudit-300" title="Vouch versus the published baseline, on the same 300 citations." lede="Baseline: AtomGPT hallucination detector, its released per-citation outputs re-scored by us (numbers reproduce its README exactly). Vouch: frozen configuration, six sources. Ochre bars are 95% bootstrap intervals.">
        <div className="grid gap-10 lg:grid-cols-[1.35fr_1fr]">
          <div>
            <PairBars
              rows={[
                { label: "Recall", sub: "of 150 fakes caught · higher is better", base: ca.baseline.recall!, ours: ca.vouch.recall!, ci: ca.ci95.recall },
                { label: "F1", sub: "higher is better", base: ca.baseline.f1!, ours: ca.vouch.f1!, ci: ca.ci95.f1 },
                { label: "Precision", sub: "flags that were real fakes", base: ca.baseline.precision!, ours: ca.vouch.precision!, ci: ca.ci95.precision },
                { label: "False-alarm rate", sub: "of 150 real refs flagged · lower is better", base: ca.baseline.fpr!, ours: ca.vouch.fpr!, ci: ca.ci95.fpr },
              ]}
            />
            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              <Confusion title="Baseline (Semantic Scholar only)" tone="base" TP={ca.baseline.TP} FN={ca.baseline.FN} FP={ca.baseline.FP} TN={ca.baseline.TN} />
              <Confusion title="Vouch (six indexes)" tone="ours" TP={ca.vouch.TP} FN={ca.vouch.FN} FP={ca.vouch.FP} TN={ca.vouch.TN} />
            </div>
          </div>
          <div className="space-y-8">
            <div>
              <ChartTitle kicker={`Paired on ${p.n_common} shared citations`} title="When exactly one system was right" />
              <Squares groups={[{ n: p.only_ours_correct, color: OURS, label: "only Vouch correct" }, { n: p.only_baseline_correct, color: BASE, label: "only the baseline correct" }]} />
              <Caption>Exact McNemar test, p = {p.mcnemar_p.toExponential(0)}. The same 150 real citations produce 20 false alarms for Vouch and 18 for the baseline: a tie within noise.</Caption>
            </div>
            <div>
              <ChartTitle kicker="Where the 150 fakes went" title="Half of them walk past a single index" />
              <p className="mb-1 text-[0.68rem] text-ink-faint">baseline</p>
              <Stacked segments={baselineSegments(baseFake, "fake")} height={18} />
              <p className="mt-3 mb-1 text-[0.68rem] text-ink-faint">Vouch</p>
              <Stacked segments={fakeSegments(fakeTest)} height={18} />
            </div>
            <div>
              <ChartTitle kicker="Where the 150 real references went" title="Both pass about 130; the rest are false alarms" />
              <p className="mb-1 text-[0.68rem] text-ink-faint">baseline</p>
              <Stacked segments={baselineSegments(baseReal, "real")} height={18} />
              <p className="mt-3 mb-1 text-[0.68rem] text-ink-faint">Vouch</p>
              <Stacked segments={realSegments(realTest)} height={18} />
            </div>
          </div>
        </div>
      </Section>

      {/* 4. by type + NeurIPS */}
      <Section kicker="4 · Two kinds of fake, two test sets" title="Generated fakes, real-world fakes, and 100 that got through NeurIPS review.">
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <ChartTitle kicker="CiteAudit-300 by citation origin" title="Generated by an LLM (209) vs taken from real papers (91)" />
            <PairBars
              rows={[
                { label: "Recall · generated", sub: "higher is better", base: S.by_type.baseline.generated.recall, ours: S.by_type.vouch.generated.recall },
                { label: "Recall · real-world", sub: "higher is better", base: S.by_type.baseline.realworld.recall, ours: S.by_type.vouch.realworld.recall },
                { label: "False alarms · generated", sub: "lower is better", base: S.by_type.baseline.generated.fpr!, ours: S.by_type.vouch.generated.fpr! },
                { label: "False alarms · real-world", sub: "lower is better", base: S.by_type.baseline.realworld.fpr!, ours: S.by_type.vouch.realworld.fpr! },
              ]}
            />
            <Caption>Real-world references from real papers are where single-index checkers wrongly accuse: 1 in 4.5 flagged by the baseline. Vouch does not fix this yet (0.224): these are mostly very recent preprints no index holds.</Caption>
          </div>
          <div>
            <ChartTitle kicker="NeurIPS-100 · all fabricated" title={`Vouch flags ${Math.round(ne.vouch.recall! * 100)} of 100, the baseline ${Math.round(ne.baseline.recall! * 100)}`} />
            <div className="flex flex-wrap items-start gap-8">
              <NeuripsGrid />
              <div className="min-w-[14rem] flex-1">
                <p className="mb-1 text-[0.68rem] text-ink-faint">how Vouch caught them</p>
                <Stacked segments={fakeSegments(neLabels)} height={18} />
                <Caption>Outlined squares: caught only by Vouch. The single miss is a real paper cited with invented co-authors whose Semantic Scholar record lists no authors at all, so it passed on title + year.</Caption>
              </div>
            </div>
          </div>
        </div>
      </Section>

      {/* 5. test looks */}
      <Section kicker="5 · Every look at the test set" title="We touched the test set twice. Here is both, plus what changed in between." lede="Rule: tune on dev only, report every test run. The only change between the two looks was adding Semantic Scholar as a sixth source, decided on dev.">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr]">
          <div>
            <Slope
              stages={["defaults, 6 sources\n(replayed offline)", "frozen, 5 sources\nlook 1, as collected", "frozen, 5 sources\nlook 1, retried", "frozen, 6 sources\nlook 2 · final"]}
              series={[
                { name: "F1", color: OURS, values: [S.test_untuned_6src.f1, S.test_5src_as_collected.f1, S.test_5src_retried.f1, S.test_6src.f1] },
                { name: "false alarms", color: "var(--notfound)", values: [S.test_untuned_6src.fpr!, S.test_5src_as_collected.fpr!, S.test_5src_retried.fpr!, S.test_6src.fpr!] },
                { name: "baseline F1", color: BASE, values: [ca.baseline.f1!, ca.baseline.f1!, ca.baseline.f1!, ca.baseline.f1!], dashed: true },
                { name: "baseline FA", color: "#c98b8b", values: [ca.baseline.fpr!, ca.baseline.fpr!, ca.baseline.fpr!, ca.baseline.fpr!], dashed: true },
              ]}
            />
            <Caption>Look 1 had 123 arXiv time-outs; retrying them changed one verdict. The false alarms were a coverage problem, not a threshold problem (19 of 28 also fire under the untuned defaults).</Caption>
          </div>
          <div>
            <ChartTitle kicker="Adding Semantic Scholar · dev, frozen config" title="A sixth index cut false alarms by a fifth" />
            <PairBars
              baseLabel="5 sources"
              oursLabel="6 sources"
              rows={[
                { label: "False alarms", sub: "lower is better", base: S.s2_on_dev.five.fpr, ours: S.s2_on_dev.six.fpr },
                { label: "Recall", base: S.s2_on_dev.five.recall, ours: S.s2_on_dev.six.recall },
                { label: "F1", base: S.s2_on_dev.five.f1, ours: S.s2_on_dev.six.f1 },
              ]}
            />
            <Caption>8 real citations newly verified, 4 fakes newly let through. Kept.</Caption>
          </div>
        </div>
      </Section>

      {/* 6. inside the verdicts */}
      <Section kicker="6 · Inside the verdicts" title="Which index vouched, and how fakes gave themselves away.">
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <ChartTitle kicker="Record that verified each real reference" title="No single index is enough" />
            <p className="mb-1 text-[0.68rem] text-ink-faint">test · {Object.values(winTest).reduce((a, b) => a + b, 0)} verified real references</p>
            <Stacked segments={srcSeg(winTest)} />
            <p className="mt-4 mb-1 text-[0.68rem] text-ink-faint">dev · {Object.values(winDev).reduce((a, b) => a + b, 0)} verified real references</p>
            <Stacked segments={srcSeg(winDev)} />
            <Caption>Sources are asked in order and the cascade stops at the first confident match, so later indexes show only what earlier ones missed. Semantic Scholar has no record for the DOI of LeCun et al. “Deep learning” (Nature 2015); Crossref’s top hit for “Attention Is All You Need” is a 2025 copy.</Caption>
          </div>
          <div>
            <ChartTitle kicker="Fakes flagged as detail mismatch" title="The invented field is usually an author" />
            <p className="mb-1 text-[0.68rem] text-ink-faint">test · {Object.values(kindTest).reduce((a, b) => a + b, 0)} fakes</p>
            <Stacked segments={[{ label: "authors differ", value: n(kindTest, "authors"), color: C.detail_mismatch }, { label: "title or venue differs", value: n(kindTest, "other"), color: "var(--link)" }, { label: "year differs", value: n(kindTest, "year"), color: C.cant_verify }, { label: "DOI points elsewhere", value: n(kindTest, "doi"), color: C.not_found }].filter((s) => s.value > 0)} />
            <p className="mt-4 mb-1 text-[0.68rem] text-ink-faint">dev · {Object.values(kindDev).reduce((a, b) => a + b, 0)} fakes</p>
            <Stacked segments={[{ label: "authors differ", value: n(kindDev, "authors"), color: C.detail_mismatch }, { label: "title or venue differs", value: n(kindDev, "other"), color: "var(--link)" }, { label: "year differs", value: n(kindDev, "year"), color: C.cant_verify }, { label: "DOI points elsewhere", value: n(kindDev, "doi"), color: C.not_found }].filter((s) => s.value > 0)} />
            <Caption>Typical fake: a real paper with one or two invented names inside a long author list. The author check requires 90% of cited authors to appear in the record.</Caption>
          </div>
        </div>
      </Section>

      {/* RQ2 coverage */}
      <Section kicker="6b · Who gets wrongly accused (RQ2)" title="Real datasets, chapters and reports get accused; articles almost never." lede={`${CV.n} real works sampled from OpenAlex across 5 types × 3 author regions, written as plain citations without DOIs. Every one is real, so every flag is a false accusation. Because the sample comes from OpenAlex, the fair comparison is the baseline vs Vouch without OpenAlex; full Vouch is shown for completeness but benefits from that circularity.`}>
        <CoverageMatrix />
        <Caption>Bar length = share of real references flagged (any verdict other than verified). Grey: baseline re-created (Semantic Scholar only, AtomGPT v2 scoring). Ochre: Vouch without OpenAlex. Black: Vouch, six sources. The single-index baseline calls {Math.round(CV.cells["dataset|all"].baseline.hard_rate * 100)}% of real datasets “likely hallucinated”. Our hypothesis that Indian and Global South references are flagged more is <b>not</b> supported in this sample (India {Math.round(CV.cells["all|India"].baseline.fpr * 100)}%, Global North {Math.round(CV.cells["all|Global North"].baseline.fpr * 100)}% for the baseline). Without OpenAlex, Vouch is no better than the baseline overall: open-index coverage of non-article works is the bottleneck.</Caption>
      </Section>

      {/* RQ5 audit */}
      <Section kicker="6c · Real papers (RQ5)" title="30 recent arXiv papers: rare problems, real fabrications, honest precision." lede={`${AU.references.toLocaleString()} references from 20 recent cs.CL/LG/AI papers and 10 India-affiliated papers. Every one of the ${AU.flags_total} hard flags was checked against outside evidence (publisher pages, arXiv, ADS, PubMed).`}>
        <div className="grid gap-10 lg:grid-cols-[1fr_1.25fr]">
          <div>
            <ChartTitle kicker={`${AU.flags_total} hard flags`} title={`${AU.correct} confirmed problems in ${AU.papers_with_confirmed_problem} papers`} />
            <Squares size={14} groups={[{ n: AU.fabricated, color: "var(--notfound)", label: "fabricated details: e.g. real papers cited with 4 invented co-authors" }, { n: AU.correct - AU.fabricated, color: "var(--mismatch)", label: "other real errors: wrong venue, wrong title, garbled names" }, { n: AU.wrong, color: "var(--rule)", label: "false alarms on correct citations" }]} />
            <Caption>Precision {Math.round(AU.precision * 100)}%. Problems are rare in real papers (≈{(AU.correct / AU.references * 100).toFixed(1)}% of references), so even a small false-flag rate dominates: a flag means “look here”, never “fake”. Labels by an AI assistant with web evidence; team spot-check pending.</Caption>
          </div>
          <div>
            <ChartTitle kicker="why the false alarms happened" title="Mostly naming and coverage, not matching" />
            <div className="space-y-2">
              {AU.causes.map(([cause, n]) => (
                <div key={cause} className="grid grid-cols-[1fr_9rem_2rem] items-center gap-3 text-xs">
                  <span className="text-ink-soft">{cause}</span>
                  <span className="h-2.5 rounded-sm bg-rule"><span className="block h-full rounded-sm bg-unverified" style={{ width: `${(n / AU.causes[0][1]) * 100}%` }} /></span>
                  <span className="text-right font-mono">{n}</span>
                </div>
              ))}
            </div>
            <Caption>The largest cause, venue abbreviations (JHEP, JINST, PTEP…), is fixable with a fuller abbreviation table; we did not apply it because it would change the frozen configuration behind the RQ1 numbers.</Caption>
          </div>
        </div>
      </Section>

      {/* 7. ablations */}
      <Section kicker="7 · What each part adds (RQ3)" title="Sources cut false alarms; strict matching catches the fakes." lede="Offline replay of the collected records with the frozen configuration. The cascade always asks Crossref, then OpenAlex, then the type-routed indexes, then Semantic Scholar, so each prefix below is exactly what a shorter cascade would decide. Dev set, 1,000 citations.">
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <ChartTitle kicker="Adding indexes in cascade order" title="Real references wrongly flagged: 55% → 6%" />
            <Slope
              stages={["Crossref\nonly", "+ OpenAlex", "+ arXiv, DataCite,\nOpen Library", "+ Semantic\nScholar"]}
              series={[
                { name: "F1", color: OURS, values: Object.values(AB.cumulative).map((m) => m.f1) },
                { name: "recall", color: "var(--link)", values: Object.values(AB.cumulative).map((m) => m.recall) },
                { name: "false alarms", color: "var(--notfound)", values: Object.values(AB.cumulative).map((m) => m.fpr) },
              ]}
            />
            <Caption>With one index, every reference it does not hold looks fake: high recall, useless precision. Each added index mostly removes false alarms. Same pattern on the test set (63% → 14%).</Caption>
          </div>
          <div>
            <ChartTitle kicker="Same six indexes, different matching" title="Title-only matching is no better than the baseline" />
            <PairBars
              baseLabel="ablated"
              oursLabel="strict"
              rows={[
                { label: "Title only", sub: "no author / year / venue checks", base: AM["title only"].f1, ours: AM["frozen (strict fields)"].f1 },
                { label: "Lenient thresholds", sub: "verified ≥ 80, no author floor", base: AM["lenient (verified >= 80, no author floor)"].f1, ours: AM["frozen (strict fields)"].f1 },
                { label: "Untuned defaults", sub: "before the dev grid search", base: AM["untuned defaults"].f1, ours: AM["frozen (strict fields)"].f1 },
              ]}
            />
            <Caption>F1 on dev. Title-only matching on all six indexes scores {AM["title only"].f1.toFixed(2)}, about the published baseline&apos;s 0.61: the sources alone do not catch fakes, the author and field checks do. Median cold lookup {AB_COST.median_seconds_cold} s per reference, {AB_COST.mean_sources_queried} indexes asked on average.</Caption>
          </div>
        </div>
      </Section>

      {/* 8. claim support */}
      <Section kicker="8 · Claim support (RQ4)" title="Does the cited abstract support the sentence? Checked on SciFact." lede={`An open model compares a claim with the cited abstract and must quote its evidence. ${SF.config.dev_pairs} expert-labelled claim–abstract pairs (SciFact dev, used for nothing else); the abstention threshold τ = ${SF.config.tau} was set on ${SF.config.train_pairs} train pairs.`}>
        <div className="grid gap-10 lg:grid-cols-2">
          <div>
            <ChartTitle kicker="Accuracy when the least-confident answers are left to a human" title="Abstaining buys accuracy" />
            <CoverageCurve points={SF.dev_coverage_curve} />
            <Caption>Each point drops the least-confident share of answers. At 20% abstention accuracy rises from {SF.dev_coverage_curve[0].accuracy.toFixed(3)} to {SF.dev_coverage_curve[4].accuracy.toFixed(3)} (hypothesis H4: ≥ 5 points).</Caption>
          </div>
          <div>
            <ChartTitle kicker="Three variants on SciFact dev" title="Well calibrated, and better when it may say “not sure”" />
            <PairBars
              baseLabel="direct"
              oursLabel="+ abstention"
              rows={[
                { label: "Accuracy", sub: `answered: ${Math.round(SF.dev.abstention.coverage * 100)}% with abstention`, base: SF.dev.direct.accuracy, ours: SF.dev.abstention.accuracy },
                { label: "Macro-F1", sub: "3 classes", base: SF.dev.direct.macro_f1, ours: SF.dev.abstention.macro_f1 },
                { label: "Calibration error (ECE)", sub: "lower is better", base: SF.dev.direct.ece, ours: SF.dev.abstention.ece },
              ]}
            />
            <Caption>With the train-chosen τ the model answered {Math.round(SF.dev.abstention.coverage * 100)}% of pairs and gained {((SF.dev.abstention.accuracy - SF.dev.direct.accuracy) * 100).toFixed(1)} points: just short of H4 at that coverage. Quote grounding changed no answer on SciFact (every quote was real) and stays as a safety net. Total cost ${SF.cost.usd}. On real papers most citing sentences are long and cite several works, so most come back as “abstract can&apos;t tell”.</Caption>
          </div>
        </div>
      </Section>

      {/* 7. negative result */}
      <Section kicker="9 · What did not work" title="An LLM judge made things worse." lede="We let a language model re-examine every borderline flag (cited reference + top-3 records → same work or not). Dev only, 422 calls, $0.65.">
        <div className="grid gap-10 lg:grid-cols-[1fr_1.2fr]">
          <div>
            <ChartTitle kicker="Even at its strictest setting" title="What the judge un-flagged" />
            <Squares size={9} groups={[{ n: S.adjudicator.unflagged_fakes, color: "var(--notfound)", label: "fakes it accepted as real" }, { n: S.adjudicator.rescued_real, color: "var(--verified)", label: "real references it rescued" }]} />
          </div>
          <div>
            <PairBars
              baseLabel="with judge"
              oursLabel="without"
              rows={[
                { label: "Recall", base: S.adjudicator.best_adjudicated.recall, ours: S.adjudicator.frozen.recall },
                { label: "F1", base: S.adjudicator.best_adjudicated.f1, ours: S.adjudicator.frozen.f1 },
                { label: "False alarms", sub: "lower is better", base: S.adjudicator.best_adjudicated.fpr, ours: S.adjudicator.frozen.fpr },
              ]}
            />
            <Caption>Cross-validation switched the judge off in {S.adjudicator.cv_folds_off} of 5 folds. It forgives one or two garbled names in a long author list (“minor differences”), which is exactly how this benchmark’s fakes are built. Strict field matching wins; the judge is kept only to explain verdicts.</Caption>
          </div>
        </div>
      </Section>

      {/* 8. takeaways */}
      <section className="mt-16 grid gap-10 border-t border-rule pt-8 lg:grid-cols-3">
        <div>
          <h2 className="font-display text-2xl italic">Four findings</h2>
          <ol className="mt-4 space-y-3 text-sm leading-relaxed text-ink-soft">
            <li><b className="text-ink">No single index is enough.</b> Six open sources, each catching what the others miss.</li>
            <li><b className="text-ink">Lenient title matching hides fakes.</b> Strict, length-aware titles plus author checks give most of the +25 recall points.</li>
            <li><b className="text-ink">An LLM judge is too forgiving</b> of invented co-authors. Deterministic matching beat it 5 folds out of 5.</li>
            <li><b className="text-ink">Thresholds are a policy.</b> We publish the trade-off curve and chose a 10% false-alarm cap.</li>
          </ol>
        </div>
        <div>
          <h2 className="font-display text-2xl italic">Limitations</h2>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-ink-soft">
            <li>False-alarm rate (0.140) is not below the baseline’s (0.121); intervals overlap, 20 vs 18 on the same citations.</li>
            <li>Recent preprints and new book editions cause most false alarms: indexes lag arXiv.</li>
            <li>A record with no author list can verify a citation on title alone (the one NeurIPS miss). Fix known, not applied after the last test look.</li>
            <li>CiteAudit counts any invented field as a fake; a “detail mismatch” is a warning, not an accusation.</li>
          </ul>
        </div>
        <div>
          <h2 className="font-display text-2xl italic">Protocol</h2>
          <ul className="mt-4 space-y-3 text-sm leading-relaxed text-ink-soft">
            <li><span className="font-mono text-xs text-ink-faint">01</span> Reproduce the baseline from its released outputs (exact).</li>
            <li><span className="font-mono text-xs text-ink-faint">02</span> Remove every copy of a test item from tuning data.</li>
            <li><span className="font-mono text-xs text-ink-faint">03</span> Tune on dev with 5-fold cross-validation under a false-alarm cap; freeze.</li>
            <li><span className="font-mono text-xs text-ink-faint">04</span> Run test; log every run, including failures, in <code className="font-mono text-xs">EXPERIMENTS.md</code>.</li>
          </ul>
          <div className="mt-5 flex flex-wrap gap-2">
            {(["verified", "detail_mismatch", "not_found", "cant_verify"] as const).map((s) => (
              <span key={s} className="inline-flex items-center gap-1.5 text-[0.68rem] text-ink-soft">
                <Stamp status={s} size="sm" /> {STATUS_META[s].label}
              </span>
            ))}
          </div>
        </div>
      </section>
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
  const pts = research.dev.frontier.filter((q) => q.fpr_cap <= 0.12);
  const W = 300, H = 160;
  const x = (v: number) => 34 + ((v - 0.05) / (0.125 - 0.05)) * (W - 50);
  const y = (v: number) => H - 24 - ((v - 0.6) / 0.3) * (H - 40);
  const dd = pts.map((q, i) => `${i ? "L" : "M"}${x(q.fpr).toFixed(1)},${y(q.recall).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-sm" role="img" aria-label="Recall vs false-alarm rate on dev">
      <line x1={34} x2={W - 10} y1={H - 24} y2={H - 24} stroke="var(--ink-faint)" />
      <line x1={34} x2={34} y1={10} y2={H - 24} stroke="var(--ink-faint)" />
      <text x={W / 2} y={H - 4} textAnchor="middle" className="fill-ink-faint text-[9px]">false-alarm rate</text>
      <text x={10} y={H / 2} transform={`rotate(-90 10 ${H / 2})`} textAnchor="middle" className="fill-ink-faint text-[9px]">recall</text>
      <path d={dd} fill="none" stroke="var(--ink)" strokeWidth={1.6} />
      {pts.map((q) => (
        <g key={q.fpr_cap}>
          <circle cx={x(q.fpr)} cy={y(q.recall)} r={2.8} fill="var(--card)" stroke="var(--ink)" />
          <text x={x(q.fpr)} y={y(q.recall) - 6} textAnchor="middle" className="fill-ink-soft font-mono text-[8px]">{q.recall.toFixed(2)}</text>
        </g>
      ))}
      <line x1={x(0.1)} x2={x(0.1)} y1={10} y2={H - 24} stroke="var(--mismatch)" strokeDasharray="3 3" />
      <text x={x(0.1) + 3} y={18} className="fill-mismatch text-[9px]">our cap</text>
    </svg>
  );
}

function CoverageCurve({ points }: { points: { abstain_pct: number; accuracy: number }[] }) {
  const W = 360, H = 180, L = 36, B = 30, T = 12, R = 12;
  const lo = 0.8, hi = 1.0;
  const x = (v: number) => L + (v / 60) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const d = points.map((p, i) => `${i ? "L" : "M"}${x(p.abstain_pct)},${y(p.accuracy)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-md" role="img" aria-label="Accuracy vs share abstained">
      {[0.8, 0.85, 0.9, 0.95, 1].map((t) => (
        <g key={t}>
          <line x1={L} x2={W - R} y1={y(t)} y2={y(t)} stroke="var(--rule)" strokeDasharray="2 3" />
          <text x={L - 5} y={y(t) + 3} textAnchor="end" className="fill-ink-faint font-mono text-[8px]">{t.toFixed(2)}</text>
        </g>
      ))}
      {[0, 20, 40, 60].map((t) => (
        <text key={t} x={x(t)} y={H - B + 13} textAnchor="middle" className="fill-ink-faint font-mono text-[8px]">{t}%</text>
      ))}
      <text x={(W + L) / 2} y={H - 3} textAnchor="middle" className="fill-ink-faint text-[9px]">share of answers left to a human</text>
      <line x1={x(20)} x2={x(20)} y1={T} y2={H - B} stroke="var(--mismatch)" strokeDasharray="3 3" />
      <text x={x(20) + 3} y={T + 9} className="fill-mismatch text-[9px]">H4: 20%</text>
      <path d={d} fill="none" stroke="var(--ink)" strokeWidth={1.8} />
      {points.map((p) => (
        <circle key={p.abstain_pct} cx={x(p.abstain_pct)} cy={y(p.accuracy)} r={2.6} fill="var(--card)" stroke="var(--ink)" />
      ))}
    </svg>
  );
}

const CV_TYPES = ["article", "book-chapter", "book", "report", "dataset", "all"];
const CV_REGIONS = ["India", "Global South (other)", "Global North", "all"];
const CV_SYS: [string, string][] = [["baseline", "var(--unverified)"], ["vouch_no_openalex", "var(--mismatch)"], ["vouch", "var(--ink)"]];

function CoverageMatrix() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-xs">
        <thead>
          <tr>
            <th className="w-28" />
            {CV_REGIONS.map((r) => (
              <th key={r} className="pb-2 text-left font-mono text-[0.62rem] font-normal tracking-wider text-ink-faint uppercase">
                {r === "all" ? "all regions" : r}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {CV_TYPES.map((t) => (
            <tr key={t} className={`border-t ${t === "all" ? "border-ink" : "border-rule"}`}>
              <td className="py-2 pr-3 align-top font-medium">{t === "all" ? "all types" : t}</td>
              {CV_REGIONS.map((r) => {
                const cell = CV.cells[`${t}|${r}`];
                return (
                  <td key={r} className="py-2 pr-4 align-top">
                    {cell ? (
                      <div className="space-y-[3px]">
                        {CV_SYS.map(([k, color]) => (
                          <div key={k} className="flex items-center gap-1.5">
                            <span className="h-2 rounded-[1px]" style={{ width: `${cell[k].fpr * 7}rem`, minWidth: 2, background: color }} />
                            <span className="font-mono text-[0.6rem] text-ink-soft">{Math.round(cell[k].fpr * 100)}%</span>
                          </div>
                        ))}
                        <span className="font-mono text-[0.55rem] text-ink-faint">n={cell.vouch.n}</span>
                      </div>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
