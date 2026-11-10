# Vouch — Ideation

> **Tagline:** *Every citation, vouched for.*
>
> **One line:** An open research-integrity screener. It checks every reference in a paper (does it exist, are the details right, was it retracted, does it support the claim) and flags paper-mill language. It uses open scholarly databases and gives evidence for each verdict.

- **Track:** DeepTech & Scientific Computing (fallback: Artificial Intelligence & Machine Learning)
- **Status:** Idea locked 10 Nov 2026. Renamed from "Vouch" to **Vouch** the same day.
- **Plan:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · **Experiment log:** [../EXPERIMENTS.md](../EXPERIMENTS.md)

---

## 1. Problem

AI writing tools make it easy to produce references that look real but aren't. Peer review is not catching them.

| Evidence | Source |
|---|---|
| Papers with fabricated references went from **1 in 2,828 (2023)** to **1 in 458 (2025)** to **1 in 277 (early 2026)** | GESIS position paper, [arXiv:2607.22693](https://arxiv.org/abs/2607.22693) |
| A conservative estimate of **146,932 hallucinated citations in 2025**, across 111M references in arXiv, bioRxiv, SSRN and PMC | [arXiv:2605.07723](https://arxiv.org/abs/2605.07723) |
| **1 in 20** NeurIPS and USENIX Security papers contains at least 2 likely hallucinated references, after expert review | [arXiv:2607.00738](https://arxiv.org/abs/2607.00738) |
| 100 confirmed fabricated citations in accepted NeurIPS 2025 papers | GPTZero audit, via the [AtomGPT detector](https://github.com/atomgptlab/hallucination_detector) data |
| The Problematic Paper Screener has flagged **14,000+** papers with "tortured phrases" (paper-mill paraphrasing) | [PPS](https://www.irit.fr/~Guillaume.Cabanac/problematic-paper-screener/), CASRAI 2026 |
| A citation can exist and still fail to support the claim. Measured unsupported-citation rates swing from **~3% to ~18%** depending only on how strict the verifier is | [arXiv:2607.20527](https://arxiv.org/html/2607.20527v1) |

**Who it hurts:**
- **Reviewers and editors.** Manual checking doesn't scale to 50+ references per paper.
- **Honest authors.** Their real references get falsely flagged, as Section 2 shows.
- **Readers, clinicians and policymakers** who rely on the literature.
- **AI systems** trained on it.

## 2. What exists and where it falls short

| Tool | What it checks | Where it looks references up | Published result | Limitation |
|---|---|---|---|---|
| **AtomGPT Hallucination Detector** ([code](https://github.com/atomgptlab/hallucination_detector), [arXiv:2607.09774](https://arxiv.org/abs/2607.09774)) | Existence, via title/author/venue similarity | **Semantic Scholar only** | CiteAudit-300: **P 0.80 · R 0.49 · F1 0.61 · FPR 0.12**; NeurIPS-100: recall 0.94 | Misses half the fakes. Most false positives are real books, reports and datasets that Semantic Scholar doesn't index |
| **CiteAudit** ([arXiv:2602.23452](https://arxiv.org/abs/2602.23452), [code](https://github.com/shiiiikw/CiteAudit)) | Existence + claim support (multi-agent) | URL probing, **Google Search, Google Scholar**, LLM judge | 9,442-citation benchmark | Relies on Google Search and Scholar: paid, rate-limited and not reproducible. No retraction or paper-mill checks |
| **HalluCiteChecker** ([arXiv:2604.26835](https://arxiv.org/abs/2604.26835)) | Existence | — | ≤35 s per paper | Existence only |
| CheckIfExist, RefChecker and others | Existence | Various | GESIS review: limited by **extraction errors, incomplete metadata, database coverage** | Fragile on messy references |
| **scite.ai** | Supporting/contrasting citation statements | Proprietary | Independent test: low accuracy | Closed. Doesn't detect fabrication |
| **Problematic Paper Screener** | Tortured phrases | 130M papers a week | 14K+ flagged | Runs after publication. Not combined with citation checks |
| **Retraction Watch DB** (Crossref, open) | Retractions | — | Updated daily | A dataset, not a checking tool. Not built into writing or review workflows |

**Gap we target:**
1. Existence checkers that rely on one database **wrongly flag real references** they can't find (books, reports, datasets, theses, government documents, regional journals) and still **miss fakes**.
2. The best-performing pipeline depends on **closed web search**.
3. **No tool combines** existence, retraction, claim support and paper-mill language in one report built for authors, reviewers and conference chairs.

## 3. Our solution

Upload a PDF, paste an arXiv ID, or paste a bibliography. You get a report with one row per reference and **evidence for every verdict**:

| Check | Question | How |
|---|---|---|
| **① Exists** | Is this a real work? | Look it up across several open databases in turn: Crossref → OpenAlex → Semantic Scholar → arXiv → DBLP → DataCite (datasets) → Open Library (books). Each step only runs if the previous one didn't find a match. Field-level matching on title, authors, year and venue. An AI model reviews only the borderline matches |
| **② Accurate** | Are the authors, year, venue and DOI right? Does the DOI point to the cited title? | Field-by-field comparison with the matched record. Catches **partial corruption** and **identifier hijacking** (a real DOI attached to the wrong paper) |
| **③ Retracted** | Was the cited work retracted, corrected or flagged? | Match DOIs and PubMed IDs against the **Retraction Watch** CSV (Crossref, updated daily) |
| **④ Supports the claim** | Does the cited source support the sentence that cites it? | Find the citing sentence, fetch the source's abstract or text, and get an AI verdict (supports / contradicts / not enough info) with an evidence quote and a confidence score. Says **"needs human review"** when confidence is low |
| **⑤ Paper-mill language** | Does the manuscript contain tortured phrases? | Match the text against the PPS tortured-phrase fingerprints, e.g. "counterfeit consciousness" for "artificial intelligence" |

**Design principles:**
- **Evidence, not accusation.** Labels are *Verified / Detail mismatch / Not found / Can't verify (needs review)*, never "fake".
- **Open sources only.** Results can be reproduced.
- **Cost and time per paper are measured and reported.**

## 4. Contributions (what we claim to the judges)

- **C1. Multi-database lookup cascade.** It beats the published single-database baseline on CiteAudit and NeurIPS-2025: higher recall at the same or lower false-positive rate.
- **C2. False-accusation study.** We measure how often real references get wrongly flagged, broken down by **reference type** and **region** (Indian and other Global South venues vs. others). We don't know of any prior published measurement of this.
- **C3. Integrated integrity report.** Existence + accuracy + retraction + claim support + paper-mill language in one tool, with its own ablation study.
- **C4. Real-paper audit** of recent papers, with **every flag hand-verified** by the team. That gives honest precision and prevalence numbers.

## 5. Research questions and hypotheses

| RQ | Question | Hypothesis | Data | Metric |
|---|---|---|---|---|
| **RQ1** | Does the multi-database cascade find fabricated references better than a Semantic Scholar-only checker? | H1: F1 > 0.61 and FPR ≤ 0.12 on CiteAudit-300 | CiteAudit-300, full CiteAudit, NeurIPS-2025-100 | Precision, recall, F1, FPR |
| **RQ2** | Do single-database checkers wrongly flag some kinds of real references more than others? | H2: FPR is much higher for books, reports, datasets and regional journals. Our cascade cuts that gap | Our **CoverageSet**: real references sampled by type and region (via OpenAlex), plus matched LLM-generated fakes | FPR by type and region |
| **RQ3** | What does each database and the AI reviewer add, and at what cost? | H3: OpenAlex and Crossref give most of the gain. The AI reviewer fixes borderline cases at low cost | Same as RQ1 | Ablation of F1 and FPR, ₹/$ and seconds per reference |
| **RQ4** | Can an open-weight model judge claim support reliably, and does a "not sure" option help? | H4: Abstaining on the least-confident 20% raises accuracy on the rest by ≥ 5 points | SciFact (expert-labelled claims vs. abstracts) | Macro-F1, accuracy vs. coverage, calibration (ECE) |
| **RQ5** | How common are these problems in recent real papers? | H5: A small but non-zero rate, with every flag hand-verified | ~200 recent arXiv papers (and a sample of Indian-affiliated papers) | Share of papers affected, precision of our flags |

**Honesty rule:** every number in the submission comes from a script in `eval/` and a committed results file. We report what failed too. The hackathon rules disqualify fabricated results, and for a project about fabricated citations that would be fatal.

## 6. Why this can win (mapped to the official criteria)

| Criterion | How we score |
|---|---|
| Innovation & originality | Multi-database open cascade + false-accusation study + integrated report. No existing tool does all of these |
| Technical implementation | Async pipeline, 7 data sources, field matching, AI review, calibrated abstention, live web app |
| Relevance & importance | Fabricated-reference prevalence is up ~10× in three years. It's the organiser's own domain (journals, ICSD conference, peer review) |
| Quality of solution | Evidence for every verdict, clear labels, PDF + arXiv + bibliography input, fast |
| Research, experimentation, data | 5 research questions, public benchmarks, a published baseline to beat, ablations, a field audit, a committed experiment log |
| Impact & scalability | Journals, conferences, universities and authors. Batch API for reviewer pipelines. Open sources keep it cheap |
| Final demo | Paste a real arXiv ID live → report with evidence in about a minute. Show a fabricated reference caught next to a real book the baseline would have wrongly flagged |

## 7. Impact and scale-up path
- **Authors:** check your references before you submit.
- **Reviewers and chairs:** batch-screen a conference's submissions. Pitch line: "Threws could run this on ICSD submissions."
- **Universities and journals:** an integrity screen alongside plagiarism checks.
- **Scale:** a stateless API plus cached lookups, with a free and polite-use profile for the open APIs. The cost per paper is small and we report it measured.

## 8. Ethics
- We never label a person or paper as fraudulent. The tool reports evidence and confidence, and leaves final judgment to humans.
- In the field audit we publish **aggregate** results only. We don't name individual papers unless they are already publicly confirmed, like the NeurIPS-2025 set.
- We respect API terms (polite-use headers, rate limits, caching) and dataset licences. Every dataset is acknowledged.

## 9. Risks and mitigations
| Risk | Mitigation |
|---|---|
| "Citation checkers already exist" | The comparison table above, plus beating a published baseline on its own benchmark |
| Pulling references out of PDFs is fragile | Prefer arXiv LaTeX source (`.bbl`/`.bib`). Fall back to GROBID, then to AI-based extraction |
| API rate limits | Free keys for Semantic Scholar and OpenAlex, Crossref's polite pool, an on-disk cache, concurrency limits |
| AI cost or latency | The AI model reviews only borderline cases. A cheap open-weight model handles parsing |
| Claim support is hard | Positioned as a "spot-check with abstention" and evaluated honestly on SciFact |
| Running out of time | MVP = ①②③ + UI + RQ1. ④⑤ and RQ2–RQ5 are added in priority order (see plan) |

## 10. 30-second pitch
> "Papers with fake references went from 1 in 2,800 to 1 in 277 in three years, and they're getting past peer review at top venues. Existing checkers look in one database. So they miss half the fakes, and they wrongly accuse real books and regional journals. Vouch checks every reference against seven open databases, plus retractions, whether it supports the claim, and paper-mill language. Every verdict comes with evidence. On the CiteAudit benchmark we beat the published baseline's F1 of 0.61 *(replace with our measured number)*, and we measured how often single-database checkers wrongly accuse references by type and region. Paste any arXiv paper and see in a minute."
