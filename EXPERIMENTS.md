# Experiment Log — Vouch

Every run that produces a number goes here: what we tried, what happened and why, **including failures**. Judges will ask about experimentation in Round 2. Every number we report must trace back to an entry here and to a committed file in `eval/results/`.

**Rules**
- One entry per run. Newest at the bottom.
- Record: date/time (IST), who, git commit, dataset + split, config (models, thresholds, sources), command, results file, numbers, notes.
- Tune on **dev**, report on **test**. Never tune on CiteAudit-300 or NeurIPS-100.
- Headline numbers get bootstrap 95% CIs.

---

## Planned experiments

| ID | RQ | Description | Owner | Status |
|---|---|---|---|---|
| E0 | — | Published baseline (AtomGPT detector) on CiteAudit-300 + NeurIPS-100, with our LLM. Re-score their released outputs | B | ✅ E0a done · E0b replaced by the E3 'S2-only, AtomGPT scoring' ablation (decision 10 Nov) |
| E1 | RQ1 | Our cascade on CiteAudit-300 + NeurIPS-100 (thresholds tuned on the CiteAudit dev split) | B | ✅ |
| E2 | RQ2 | CoverageSet: false-positive rate by reference type × region, baseline vs. ours | B | ✅ E2 (step 7.1) |
| E3 | RQ3 | Ablations: each source, the adjudicator, title-only matching. Cost and latency per reference | B | ✅ E3 (step 7.2), E3a, E3b |
| E4 | RQ4 | SciFact claim support: direct vs. + quote grounding vs. + abstention | B | ✅ E4 (step 6.2) |
| E5 | RQ5 | Real-paper audit: 200 arXiv + 50 Indian-affiliated papers, flags hand-verified | All | ⬜ |

## Results summary (fill as runs finish)

| Set | System | Precision | Recall | F1 | FPR | Notes |
|---|---|---|---|---|---|---|
| CiteAudit-300 | AtomGPT (published) | 0.80 | 0.49 | 0.61 | 0.12 | From their README, scoring v2 |
| CiteAudit-300 | AtomGPT (released outputs, re-scored by us, E0a) | 0.804 | 0.493 | 0.612 [0.534, 0.679] | 0.121 | Exact match, n=299. Generated: R 0.444 FPR 0.036 · Real-world: R 0.750 FPR 0.227 |
| CiteAudit-300 | Our pipeline, S2-only + AtomGPT v2 scoring (baseline re-created in our code, E3) | | | | | |
| CiteAudit-300 | **Vouch, 6 sources** (frozen config, 2nd disclosed test look) | 0.842 | 0.747 | 0.792 | 0.140 | 44 vs 8 paired, McNemar p = 4e-07 |
| CiteAudit-300 | Vouch, 5 sources (frozen config, 1st test look, after retries) | 0.803 | 0.760 | 0.781 | 0.187 | Paired McNemar p = 9e-05 vs baseline |
| NeurIPS-100 | AtomGPT (published) | n/a | 0.94 | n/a | n/a | Scoring v1, all fake |
| NeurIPS-100 | **Vouch, 6 sources** (2nd look) | 1.000 | 0.990 | 0.995 | n/a | 1 miss: S2 record with no authors |
| NeurIPS-100 | Vouch, 5 sources (1st look) | 1.000 | 1.000 | 1.000 | n/a | 6 fakes the baseline missed; p = 0.031 |

---

## Log

### Entry template
```
### E? — <short title>
- When / who: 2026-11-__ __:__ IST · <name>
- Commit: <sha>
- Data: <set + split + n>
- Config: parse=<model> judge=<model> sources=<...> thresholds=<...> seed=<...>
- Command: `...`
- Output: eval/results/<file>.json
- Results: P= R= F1= FPR= (95% CI ...) · cost=$ · time=
- What we learned / what failed / next:
```

### S0 — LLM endpoint and model selection (setup)
- When / who: 2026-11-10 13:14 IST (commit time) · Priyanshu
- Endpoint: Vultr Serverless Inference (OpenAI-compatible), subscription `citesentinel` (Vultr label)
- Test: parse one messy reference ("[12] Vaswani A., ... arXiv:1706.03762") into JSON, temperature 0
- Results:
  | Model | Thinking on (max_tokens 400) | Thinking on (2000) | Thinking off | Latency (off) | Output tokens (off) |
  |---|---|---|---|---|---|
  | deepseek-v4.1-flash-1017 | JSON cut off | ok | ok | 1.5 s | 90 |
  | qwen3.8-flash-next | JSON cut off | ok | ok | 1.4 s | 122 |
  | glm-5.3-flash | JSON cut off | ok (wrapped in ```json) | switch ignored | 2.8 s | 717 |
  | minimax-m3.1-flash | JSON cut off | ok | switch ignored | 2.1 s | 642 |
  | mimo-v2.6-flash | ok | — | — | 1.4 s (default) | ~110 |
- Decision: **parse = deepseek-v4.1-flash-1017 with thinking off** (`chat_template_kwargs.enable_thinking=false`, `reasoning_effort=none`). Fallback: qwen3.8-flash-next.
  **Judge = deepseek-v4.1-flash-1017 with thinking on** for now. Compare against glm-5.3 / qwen3.8-27b on the dev split in steps 3.3 and 6.2.
- Learned: reasoning models spend the token budget on hidden thinking, so the JSON gets cut off. Always set max_tokens ≥ 2000 when thinking is on, and strip ``` code fences when parsing output.

### S1 — Source smoke test (step 0.3)
- When / who: 2026-11-10 13:38 IST (commit time) · Priyanshu
- Command: `backend/.venv/Scripts/python backend/scripts/smoke_test.py`
- Results: Crossref ✅ · OpenAlex ✅ (key) · Semantic Scholar ✅ without a key (the shared pool sometimes returns 429) · arXiv ✅ · DataCite ✅ · Open Library ✅ · Retraction Watch repo ✅ (data for 2026-11-09) · LLM ✅ (33 models) · GROBID ⏳ (step 0.4) · **DBLP ❌** (HTTP 202 anti-bot challenge page)
- Decision: drop DBLP from the cascade. CS venues are covered by OpenAlex, Crossref and S2.
- Learned: **Crossref's top hit for "Attention is all you need" is a different paper, "Is Attention All You Need?" (Springer 2025).** Taking the first search result is unsafe; the matcher must score several candidates per source. Good example for the README.

### S2 — GROBID + datasets (steps 0.4, 1.1)
- When / who: 2026-11-10 13:51 IST (commit time) · Priyanshu
- GROBID `grobid/grobid:0.9.1-crf`: `processReferences` on arXiv:1706.03762 gave **40 references in 10.1 s** (the paper has 40). One entry had no article-level title (preprint/monograph tagging), so the parser must fall back to monograph titles.
- Datasets: see `eval/data/SOURCES.md`. CiteAudit = 9,442 (6,475 real / 2,967 fake). CiteAudit-300 = 150/150. NeurIPS-2025 = 100 fake. SciFact 809/300/300 claims. Retraction Watch 73,718 notices.
- Note: CiteAudit has no licence file, so we use it for evaluation only and never commit it.

### S3 — Dev/test split (step 1.2)
- When / who: 2026-11-10 13:56 IST (commit time) · Priyanshu
- Command: `backend/.venv/Scripts/python eval/data/make_splits.py` (seed 20261110)
- Provenance check: all **300/300** CiteAudit-300 items appear verbatim in full CiteAudit. **0/100** NeurIPS-2025 items appear in CiteAudit.
- Leakage removal: dev excludes **303 exact** duplicates (CiteAudit contains some test items more than once) and **144 near-duplicates** (token_sort_ratio ≥ 95 after normalisation) of any test item. Verified afterwards: overlap exact = 0, near = 0.
- Splits (indices + hashes only, in `eval/data/splits/`):
  | Split | n | Real / fake | Generated / real-world | Use |
  |---|---|---|---|---|
  | test_citeaudit300 | 300 | 150 / 150 | 209 / 91 | RQ1 test (baseline's published set) |
  | test_neurips100 | 100 | 0 / 100 | — | RQ1 test (real-world fakes) |
  | dev_full | 8,995 | 6,252 / 2,743 | 5,737 / 3,258 | Tuning pool |
  | dev_1000 | 1,000 | 500 / 500 | 694 / 306 | Threshold tuning within API budget |
- Note: near-duplicate removal matters. The same reference with different formatting would otherwise leak test answers into tuning.

### S4 — Semantic Scholar API key
- When / who: 2026-11-10 14:00 IST (commit time) · Priyanshu
- Key issued 2026-11-10 13:11 IST. Rate limit 1 request/second, cumulative across all endpoints, sent as the `x-api-key` header.
- Validity: our key returns 200s, while a wrong key (or the capital-I spelling from the PDF image) returns **403 Forbidden**.
- Throttling: at a steady 1 request every 2 s, **7/15 succeeded** (7×429, then 7×200, then 429). The 429 body says "TooManyRequestsException", so this is service-side throttling, not our pace.
- Decision: S2 client = 1.1 s minimum gap + exponential backoff (2/4/8 s, 3 retries) + cache. S2 stays **after** Crossref/OpenAlex in the cascade. The S2-only baseline (E0b) runs in the background.

### E0a — Re-score AtomGPT released outputs (step 1.3a)
- When / who: 2026-11-10 14:16 IST (commit time) · Priyanshu
- Command: `backend/.venv/Scripts/python eval/baselines/rescore_atomgpt.py` → `eval/results/e0a_atomgpt_released_rescored.json`
- Results (fake = positive, flagged = not "verified"):
  | Set | P | R | F1 [95% CI] | FPR | Matches published? |
  |---|---|---|---|---|---|
  | CiteAudit-300 (v2, n=299) | 0.804 | 0.493 | 0.612 [0.534, 0.679] | 0.121 | ✅ exact (0.8043 / 0.4933 / 0.6115 / 0.1208) |
  | NeurIPS-100 (v1) | 1.000 | 0.940 [0.89, 0.98] | 0.969 | n/a | ✅ exact |
- **Breakdown by source type, CiteAudit-300:**
  | Subset | n | Recall | FPR |
  |---|---|---|---|
  | Generated citations | 209 | 0.444 | **0.036** |
  | Real-world citations | 90 | 0.750 | **0.227** (15 of 66 real references wrongly flagged) |
- Learned: (1) Our metric code reproduces the published numbers exactly. (2) **Early evidence for H2:** the single-source baseline wrongly flags real references from real papers **6× more often** than real generated-set references. (3) It misses 56% of generated fakes, so recall is the main thing to improve.

### Decision — baseline protocol (step 1.3b)
- When / who: 2026-11-10 14:39 IST (commit time) · Priyanshu
- We **do not** re-run AtomGPT's third-party code. The baseline is (1) their **published / released outputs**, re-scored exactly in E0a, plus (2) a **re-creation of their method inside our pipeline**: Semantic Scholar only, their documented v2 scoring (title 0.60 / authors 0.25 / venue 0.15, verified ≥ 80), and our LLM. This becomes a row in the E3 ablation.
- Why: fewer moving parts and no third-party code execution. It also avoids a slow S2-only run under throttling and gives a controlled comparison where only the cascade and matcher differ.
- Limitation to state in the README: the published baseline numbers come from a different extraction LLM (gpt-oss-20b for NeurIPS; not recorded for CiteAudit-300).

### S5 — Resolver check: 5 references × 6 sources (step 2.2)
- When / who: 2026-11-10 14:47 IST (commit time) · Priyanshu
- Command: `cd backend && .venv/Scripts/python scripts/resolver_check.py` · live asserts in `tests/test_live_resolvers.py`
- Result (best candidate per source, ranked by title + authors + DOI):
  | Reference | Found correctly by | Not found / wrong |
  |---|---|---|
  | Article: LeCun et al., *Deep learning*, Nature 2015 (DOI) | Crossref, OpenAlex (exact DOI) | **S2: 404 for this DOI**; S2 search returns other "deep learning" papers |
  | Preprint: *Attention Is All You Need* (arXiv ID) | OpenAlex, S2, arXiv | **Crossref's top hit is a 2025 copy** with DOI 10.65215/r5bs2d54 (year mismatch) |
  | Book: Goodfellow et al., *Deep Learning*, MIT Press 2016 | OpenAlex, Open Library | Crossref, S2, arXiv return other papers with "deep learning" in the title |
  | Dataset: Zenodo 10.5281/zenodo.5031935 | DataCite (exact DOI); OpenAlex/S2/arXiv find the arXiv version | Crossref |
  | **Fake**: "Hierarchical contrastive attention networks for low-resource citation verification" | — (best strict title similarity ≤ 64 anywhere) | ✅ correct |
- **Key finding for the matcher (and for the pitch):** the baseline's title measure (`token_set_ratio`) scores **100** for "Deep learning" against "PyTorch: …Deep Learning", "Deep Learning with Differential Privacy", "Towards Deep Learning Models Resistant…", because short titles are a subset of many others. A strict measure (`token_sort_ratio`) gives 35–50 for those. **Short titles need strict title similarity plus author/year evidence.**
- Other notes: S2 still throttles (two lookups gave up after 6 retries / ~100 s), so S2 runs last with a time budget. Crossref ~7 s per query (polite pool). A cached re-run takes 4.4 s.
- Bug found by the tests: Crossref organisation authors ("Consortium X") were reformatted as persons ("X, Consortium"). Fixed: the bare `name` field is kept as-is.

### S6 — Matcher + verdict v1 (step 2.3)
- When / who: 2026-11-10 17:06 IST (commit time) · Priyanshu
- Code: `backend/app/pipeline/match.py`, `verdict.py` · tests: `backend/tests/test_match_verdict.py` (20 edge cases, each tied to a documented baseline weakness or an S5 finding)
- Design vs the AtomGPT baseline:
  | Weakness (their README / our S5) | Our handling | Test |
  |---|---|---|
  | `token_set_ratio` over-matches short titles ("Deep learning" = 100 vs longer titles) | `token_sort_ratio`; set-ratio only when lengths are similar; clean-prefix rule for omitted subtitles | `test_short_title_does_not_overmatch` (<70 / <50) |
  | Diacritics (Grazulis ≠ Gražulis) | Unicode folding | `test_diacritics` |
  | Literal "et al." counted as an unmatched author | Ignored; only listed authors are scored | `test_et_al_not_penalised` |
  | Hyphenated surnames must match exactly | Letters-only surname keys | `test_hyphenated_surnames` |
  | "Smith, J." took the initial as the surname | Parses 4 formats | `test_name_formats` |
  | Venue abbreviations (Phys. Rev. Lett. = 66.7) | Abbreviation + alias table (NIPS/NeurIPS, ICML, ACL...) | ≥95 / ≥90 |
  | Year not scored | Exact = 1, ±1 = 0.5 (preprint vs published), else a mismatch | `test_wrong_year...`, `test_year_off_by_one...` |
  | Real DOI on a fabricated title (identifier hijacking) | Checked first, before any threshold | `test_identifier_hijack` |
  | Every miss counted as a hallucination | Hard-to-index types (web, report, software) → "can't verify", not "not found" | `test_not_found_vs_cant_verify` |
- Starting thresholds (to be tuned on dev only in step 3.1): verified composite ≥ 85 and title ≥ 85 and authors ≥ 60; same-work title ≥ 90; found ≥ 60. Weights: title 0.55, authors 0.30, venue 0.10, year 0.05.
- Preview on the S5 references (5 sources, S2 excluded): article / preprint / book / dataset → **verified** (the preprint matched the genuine 2017 OpenAlex record, not Crossref's 2025 copy); fake → **not found** (closest composite 56.6).
- Tests: 62 pass (56 offline + 6 live).

### S7 — End-to-end on a 20-reference list with 3 planted fakes (step 2.4)
- When / who: 2026-11-10 17:12 IST (commit time) · Priyanshu
- Command: `cd backend && .venv/Scripts/python -m app.cli check --bib tests/fixtures/bib20.txt --out ../eval/results/s7_bib20_report.json`
- Fixture: `backend/tests/fixtures/bib20.txt` with answer key `bib20_answers.json`. 17 real references (journal articles, conference papers, arXiv preprints, 2 books) + 3 fakes: #18 fully invented, #19 real title (ResNet) with invented authors, #20 real DOI (AlphaFold's) on an invented title.
- First run: **17/17 real verified · 3/3 fakes flagged** · 44.4 s cold · 3 LLM calls (batched parsing, 8 refs per call), **$0.0046** · API calls: crossref 17, openalex 11, datacite 7, s2 9, arxiv 4, openlibrary 4.
- Bug found: #20 was labelled "not found" instead of "DOI belongs to a different work". The DOI-resolved record lost to unrelated records with higher composites. Fix: when the cited DOI resolves, that record wins unless another record matches the title at ≥ 90. Re-run: #18 not found · #19 detail mismatch (authors differ) · #20 detail mismatch (DOI → AlphaFold), with the AlphaFold record kept as evidence. Cached re-run 0.1 s.
- Design note: identifiers (DOI, arXiv, ISBN, URL) are taken **only from the raw text by regex**, never from the LLM. A test confirms an LLM-invented DOI is ignored.
- Tests: 70 pass (incl. live `test_live_pipeline.py`).
- Caveat: this is a hand-made sanity set, **not** an evaluation result. RQ1 numbers come from CiteAudit/NeurIPS in step 3.

### S8 — arXiv path on 3 real papers (step 2.5)
- When / who: 2026-11-10 17:21 IST (commit time) · Priyanshu
- Command: `cd backend && .venv/Scripts/python -m app.cli check --arxiv <id> --out ../eval/results/s8_arxiv_<id>.json`
- Pipeline: e-print → `.bib` entries for cited keys (structured, **no LLM**) → `.bbl` entries for the rest (LLM-parsed) → `\cite` contexts from `.tex` → GROBID if the source is PDF-only.
- Papers (all about hallucinated-citation detection): CiteAudit 2602.23452 (`.bib`), AtomGPT detector 2607.09774 (`.bib`), HalluCiteChecker 2604.26835 (`.bbl`, 3 LLM calls, $0.006).
- **First run** found 2 false alarms on real references:
  1. "Ansari, Mohammad Samar" vs record "Ansari, Samar" → *authors differ* (only first initials were compared). Fix: initials agree if one person's first initial is among the other's given-name initials.
  2. "Delft" (DeLFT, GitHub 2018) matched an unrelated 2023 article titled "Delft" → *detail mismatch*. Fix: titles of ≤ 2 words count as the same work only with agreeing authors, the DOI, or the same year + venue. Otherwise *can't verify*.
  Also: arXiv answered bursts of e-print downloads with 429 / dropped connections, so downloads now retry with Retry-After and alternate hosts.
- **After the fixes:**
  | Paper | Refs | Verified | Can't verify | Detail mismatch | Not found | Contexts captured |
  |---|---|---|---|---|---|---|
  | CiteAudit | 33 | 24 | 9 | 0 | 0 | 33/33 |
  | AtomGPT detector | 28 | 25 | 3 | 0 | 0 | 28/28 |
  | HalluCiteChecker | 18 | 16 | 2 | 0 | 0 | — (bbl) |
  "Can't verify" items are software, web pages, news and tools (GPTZero, Citely, SwanRef, Playwright, Grobid, Crossref REST API...) plus one real paper cited with a **shortened title** ("Literary runaway…", composite 86.7, title < 85). That last one is a target for threshold tuning (3.1) and the LLM adjudicator (3.3).
- **0 false "not found" / "detail mismatch" on 79 real references.** Unlabelled sanity set, not an evaluation result.
- Tests: 78 pass.

### S9 — Retraction check (step 2.6)
- When / who: 2026-11-10 17:26 IST (commit time) · Priyanshu
- Data: Retraction Watch CSV (Crossref), 73,718 notices → index of **64,700 DOIs, 32,630 PMIDs, 69,639 long titles**, loaded in 3.6 s. 2,540 papers have several notices.
- Rule: report the notice that applies **now**. A reinstatement dated after the last retraction wins; otherwise the most severe notice (Retraction > Expression of concern > Correction), latest if tied. Book-keeping reasons ("Updated to Retraction", "Upgrade/Update of Prior Notice(s)") are dropped.
- Lookup order: cited DOI → matched record's DOI → **retraction-notice DOI → original** → PMID → exact title (≥ 6 words, notice prefixes stripped).
- Check: `backend/tests/fixtures/bib_retracted.txt` (4 refs, **no DOIs in the text**): Wakefield 1998 (Lancet MMR), Obokata 2014 (Nature STAP cells), LeCun 2015, Jumper 2021.
  - First run: Wakefield 🚫 caught; **Obokata missed**. Crossref's best match was the *Retraction Note* itself ("Retraction Note: Stimulus-triggered…", DOI 10.1038/nature13598), whose DOI is the notice DOI, not the paper's.
  - Fixes: (1) map notice DOI → original; (2) matcher recognises notice records ("Retraction Note:", "RETRACTED:", "Correction to:", "Erratum:"...), scores them on the stripped title and ranks them 10 points below the original; (3) title fallback also runs when the DOI isn't in the database.
  - Re-run: **2/2 retracted caught** (Wakefield 2010-02-06 falsification of data; Obokata 2014-07-02 unreliable images), 2/2 clean. Regression: bib20 + 3 arXiv papers unchanged, 0 retracted among 99 refs.
- Tests: 84 pass.

### S10 — HTTP API + PDF path (step 2.7) · 🚩 Checkpoint 1
- When / who: 2026-11-10 17:34 IST (commit time) · Priyanshu
- Server: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000`. Endpoints: `POST /api/check` (arXiv ID or bibliography), `POST /api/check/pdf`, `GET /api/jobs/{id}`, `GET /api/jobs/{id}/events` (SSE), `GET /api/health`.
- Built in: background jobs (max 3 concurrent), an SSE event log clients can replay (`Last-Event-ID`), finished-report cache (versioned), per-IP rate limit (12 / 10 min, only accepted jobs count), input limits (100k chars, 20 MB PDF), retraction index warmed at startup.
- Live check:
  - arXiv 2604.26835 (URL form) → events `status → parsed → 18 × ref_done → done → report`; 16 verified / 2 can't verify. A repeat request came from the report cache instantly.
  - **PDF upload** (Attention Is All You Need, 40 references): first version **38/40** verified. GROBID's own field parsing **dropped the title** of "Layer normalization" and **shifted author names** in the GNMT reference ("Quoc, V", "Le, Mohammad"…). Fix: GROBID now only splits the bibliography and keeps the raw strings; fields come from the same LLM parser as bibliographies. Re-run: **40/40 verified**, 18.6 s, 5 LLM calls, **$0.0097**.
- Tests: 88 pass (incl. 4 offline API tests with a fake pipeline: lifecycle, report cache, SSE replay, validation/rate limit, health).
- **🚩 Checkpoint 1 met:** an arXiv ID, a bibliography or a PDF gives a real report through the API. The baseline is reproduced (E0a).

### E1-dev / S11 — Tuning on dev_1000 (step 3.1) — candidate config, awaiting approval
- When / who: 2026-11-10 17:41–19:30 IST · Priyanshu
- Collection: `eval/collect.py dev_1000` — 1,000 citations in 47.9 min, 125 LLM calls (**$0.275**), API: crossref 1022, openalex 737, datacite 761, arxiv 772, openlibrary 454. S2 excluded (throttled; ablation in E3).
- arXiv: 222 title searches timed out (19 on real citations) because arXiv allows 1 request / 3 s and later took ~45 s per answer. The retry pass (`eval/patch_failed.py`) ran at ~2 items/min, so it was **stopped**. **Measured effect of removing arXiv candidates entirely: 2/1000 verdicts change (FPR +0.004)**, because OpenAlex already indexes arXiv. Data used as collected.
- Tuner: `eval/tune_rq1.py dev_1000 --fpr-cap=0.10` (offline replay, 5-fold CV with the full search inside each fold).
- **Three flaws found and fixed in the tuner along the way** (all logged so the result can be trusted):
  1. Grid edges: early runs picked values at the boundary, so the grids were widened.
  2. **Tie-breaking**: ties went to the last grid entry (largest values). `found` / `same_work_title` don't affect flagged-vs-verified at all, so they were set to arbitrary maxima, which collapsed labels (only 15 "detail mismatch"). Fix: those two stay at defaults; ties now go to lower FPR, then closeness to defaults.
  3. **Objective**: pure F1 on a balanced benchmark chose FPR **0.19**, i.e. it wrongly flags 1 in 5 real references. Fix: **maximise F1 subject to FPR ≤ cap** (policy; cap 0.10 < baseline 0.12). A trade-off curve is saved in the results file.
- Data-driven matcher changes made during this step: **year tolerance** and **ignore-year-for-books** settings (editions, preprint vs journal), plus a year tie-break in candidate selection. Before these, most real-world false positives had perfect title + authors with a different year.
- **Results (fake = positive):**
  | Config | P | R | F1 [95% CI] | FPR |
  |---|---|---|---|---|
  | Default (pre-tuning) | 0.896 | 0.656 | 0.758 | 0.076 |
  | Tuned, in-sample | 0.914 | 0.830 | 0.870 | 0.078 |
  | **Tuned, 5-fold CV (honest dev estimate)** | **0.898** | **0.826** | **0.860** [0.836, 0.883] | **0.094** |
  | CV, generated citations | 0.949 | 0.797 | 0.866 | 0.065 |
  | CV, real-world citations | 0.731 | 0.975 | 0.836 | 0.129 |
- Candidate config (`eval/configs/rq1_candidate.json`): weights {'title': 0.55, 'authors': 0.4, 'venue': 0.1, 'year': 0.05}; thresholds {'verified': 95, 'title_min': 95, 'author_min': 90, 'same_work_title': 90.0, 'found': 60.0, 'year_tolerance': 2, 'book_year_any': True}. Labels on dev: {'verified': 546, 'cant_verify': 210, 'detail_mismatch': 175, 'not_found': 69}.
- **Outside check (not CiteAudit) with the candidate config:** 100 real references (3 arXiv papers + bib20 + retracted list), **1 wrongly called a mismatch**: AlexNet (NIPS 2012). The indexes only hold the 2017 *Communications of the ACM* reprint with full metadata, and OpenAlex's NIPS 2012 record has broken authors. A coverage gap, and a target for the LLM adjudicator (3.3). All 3 planted fakes flagged.
- Regression found and fixed: with the stricter verified bar, Obokata 2014 became "can't verify" and lost its retraction flag (the lookup used the matched DOI only for verified refs). The lookup now runs whenever the work is clearly identified (title ≥ 95). Both retractions are caught again.
- Not yet frozen. Test sets untouched.

### Decision — config frozen (end of step 3.1)
- When / who: 2026-11-10 ~19:40 IST · Priyanshu approved the candidate config with FPR cap 0.10.
- Frozen in `eval/configs/rq1.json` (record) and `backend/app/pipeline/tuned.json` (used by the app; `app/pipeline/tuned.py`). The API report cache version was bumped to v3.
- **No changes to matcher, verdict or config until test results are logged.**

### E1-test — Frozen config on the test sets (step 3.2), AS COLLECTED
- When / who: 2026-11-10 23:30 IST · Priyanshu · config `eval/configs/rq1.json` (frozen, unchanged)
- Collection: `eval/collect.py test_citeaudit300` (17.6 min, $0.086) and `test_neurips100` (8.0 min, $0.025). Same 5 sources as dev (no S2).
- Command: `backend/.venv/Scripts/python eval/run_rq1_detection.py` → `eval/results/e1_test_results_as_collected.json`
- **CiteAudit-300 (n=300):** P 0.797 · R 0.760 · **F1 0.778** [0.723, 0.828] · **FPR 0.193** [0.135, 0.257]
  - generated: R 0.730, FPR 0.096 · real-world: R 0.917, **FPR 0.313**
  - Paired vs AtomGPT on 299 shared citations: baseline F1 0.612 / FPR 0.121; Vouch F1 0.781 / FPR 0.188. Only Vouch correct **45**, only baseline correct **15**, exact McNemar **p = 0.0001**.
- **NeurIPS-100 (all fake):** recall **1.000** vs baseline 0.940. Paired: only Vouch correct 6, only baseline correct 0, McNemar p = 0.031.
- **H1 verdict: partially met.** F1 > 0.61 ✅ (0.778, CI excludes 0.61), recall +27 pts ✅. **FPR ≤ 0.12 ❌** (0.193; real-world subset 0.313). Dev CV FPR was 0.094, so the test FPR is much higher.
- **Error analysis (29 real citations flagged):** **22 had an arXiv lookup that timed out** during collection (123 arXiv timeouts on this split). CiteAudit-300's real-world citations are mostly recent arXiv preprints (2025–26), which only arXiv (or a just-ingested OpenAlex record) knows. Rest: titles that changed between preprint and published versions (e.g. "Baitsao: …"), old-style arXiv IDs not extracted when written "arXiv preprint math/0503081", a book edition year (Sutton & Barto), and records not in any index.
- **Correction of an earlier claim:** on dev, removing arXiv changed 2/1000 verdicts, so I called it negligible (S11). That does **not** hold for this test split, whose real-world references are recent preprints. The dev sample under-represents them.
- Next (disclosed protocol): keep this result on record; retry **only failed network calls** (no config/method change) once arXiv stops rate-limiting us; report both numbers. Method improvements (LLM adjudicator, arXiv robustness, ID extraction) are decided on dev only and tested once more, disclosed as a second test look.

### E1-test — after retrying failed network calls (step 3.2, disclosed)
- When / who: 2026-11-10 23:38–23:55 IST · Priyanshu · same frozen config, same method. Only failed (citation, source) lookups were re-sent (`eval/patch_failed.py`) once arXiv stopped returning 429.
- Retries: CiteAudit-300 119/125 fixed (6 still failing) · NeurIPS-100 36/36. → `eval/results/e1_test_results_retried.json` (as-collected kept in `e1_test_results_as_collected.json`).
- **CiteAudit-300:** P 0.803 · R 0.760 · **F1 0.781** [0.727, 0.830] · **FPR 0.187** [0.130, 0.247]. Paired vs AtomGPT (n=299): only Vouch correct 46, only baseline correct 15, McNemar p = 9e-05.
- **NeurIPS-100:** recall 1.000 (unchanged).
- **Correction of my E1 hypothesis:** arXiv timeouts were **not** the main cause of the false positives. With arXiv answering, FPR only moved 0.193 → 0.187 (one fewer FP).
- **Error analysis (28 real citations flagged, complete data):** 13 · right record not found in any of the 5 sources (mostly recent preprints) · 7 · title changed between versions or truncated (80–95) · 4 · title ok, authors partly match · 4 · year/venue (editions, reprints). **19/28 are also flagged under the untuned default config**: the false positives come mainly from **source coverage**, not threshold strictness. The tuned config catches 26 more fakes (of 150) for 9 more false positives.
- Implication: S2 (excluded from tuning only for rate-limit reasons) is the baseline's only source and it has fewer FPs on these citations, so it likely covers recent preprints we miss. → Step 3.3: add S2 to the cascade + LLM adjudicator for borderline matches, validate on **dev** (CV), then **one disclosed second test run**.

### E3a / S12 — LLM adjudicator for borderline matches (step 3.3): negative result, kept OFF
- When / who: 2026-11-11 00:05 IST · Priyanshu · matcher config frozen (step 3.1); dev only.
- Design: `backend/app/pipeline/adjudicate.py`. The judge model (deepseek-v4.1-flash, thinking on) sees the cited reference and the top-3 records and answers {match, confidence, reason}. It judges only from the shown records and can only verify, never flag. Sanity cases all correct: AlexNet vs its 2017 CACM reprint → same (0.95); ResNet title with invented authors → none (0.98); retitled preprint (Baitsao) → same (0.95).
- Run: `eval/adjudicate_eval.py dev_1000.no_s2` → 421 borderline references (flagged, best title ≥ 50), 422 LLM calls, **$0.651**, 4 min. Answers: 239 "same", 182 "none".
- **Result: it hurts.** Frozen: R 0.830 / F1 0.870 / FPR 0.078. Best adjudicated setting: R 0.646 / F1 0.756 / FPR 0.062. Even restricted to records whose title already matches at ≥ 98 with confidence ≥ 0.95, it un-flags **89 fakes for 4 real references**. With "off" in the grid, **5-fold CV picked off in 5/5 folds**.
- Why (inspected): 86 of those 89 fakes have **one or two invented or garbled author names inside a long, otherwise real author list** (e.g. AlphaCode cited with "Rémi Dadashi", "Viorica Fidjeland"; Gopher with "Tom Noland, GOR Young"). The LLM calls these "minor differences". The deterministic author matcher (≥ 90% of cited authors must be found) catches them. A first prompt allowed "light rewording between versions", which also matches CiteAudit's title-substitution fakes.
- **Finding for the write-up:** on this benchmark's definition of a hallucinated citation (any invented field counts), strict field-level matching beats an LLM judge. LLM judges are too forgiving of corrupted author lists. Adjudicator stays **off** (`eval/configs/rq1_adjudicator.json`). The code is kept for ablations and could later be used only to *explain* verdicts.

### E3b — Adding Semantic Scholar as a 6th source (step 3.3), dev, frozen config
- When / who: 2026-11-11 01:30 IST · Priyanshu
- `eval/add_source.py dev_1000 --source s2`: queried only the 453 citations that were not already a near-certain match (as the live cascade does). 440 ok, 13 failed, **90.3 min** (S2 throttled to ~1 answer / 16 s despite the key).
- Frozen config, dev (n=1000):
  | Sources | P | R | F1 [95% CI] | FPR [95% CI] | FPR real-world |
  |---|---|---|---|---|---|
  | 5 (no S2) | 0.914 | 0.830 | 0.870 [0.847, 0.892] | 0.078 [0.055, 0.102] | 0.111 |
  | **6 (+ S2)** | **0.930** | 0.822 | **0.873** [0.849, 0.894] | **0.062** [0.041, 0.084] | **0.093** |
- Changed verdicts: 8 real citations newly verified (fewer false alarms), 4 fakes newly verified (S2 holds records close enough to pass).
- **Decision: keep S2** (the designed 6-source cascade). FPR −20% relative at −0.008 recall. Next: add S2 to both test sets and run the **disclosed second test evaluation** with the frozen config + 6 sources (adjudicator off).

### E1-test (2nd, disclosed) — frozen config + 6 sources, adjudicator off (end of step 3.3)
- When / who: 2026-11-11 02:08 IST · Priyanshu. This is the **second and last look at the test sets**. The only change since the first look is adding S2 as a sixth source (decided on dev, E3b). Weights and thresholds are frozen; the adjudicator is off (E3a).
- S2 added to test sets with `eval/add_source.py` (CiteAudit-300: 140 queried, 137 ok, 20.3 min · NeurIPS-100: 100 queried, 97 ok, 18.4 min). → `eval/results/e1_test_results_6sources.json`
- **CiteAudit-300:** P 0.842 · R 0.747 [0.675, 0.812] · **F1 0.792** [0.736, 0.839] · **FPR 0.140** [0.090, 0.195]
  - Paired vs AtomGPT (n=299): baseline F1 0.612 / FPR 0.121 (18 FP); Vouch F1 0.794 / FPR 0.134 (20 FP). Only Vouch correct **44**, only baseline correct **8**, exact McNemar **p = 4e-07**.
- **NeurIPS-100:** recall **0.990** [0.97, 1.00] vs baseline 0.940. Paired: 5 vs 0, p = 0.06.
- **The one NeurIPS miss:** "The impact of neural network overparameterization on gradient confusion and SGD" (ICML 2020) cited with invented co-authors. S2's record of the real paper **lists no authors**, so it verified on title + year alone. **Known limitation / next fix:** a record without authors should not verify a citation that names authors unless another source with authors agrees. Not applied: it would be a third test look.
- **H1 final:** F1 > 0.61 ✅ (0.792, CI [0.736, 0.839]). FPR ≤ 0.12: not met on the point estimate (0.140), but the CI [0.09, 0.195] contains the baseline's 0.121 and the paired FP count is 20 vs 18. Recall +25 pts (0.747 vs 0.493).
- Summary of all test looks (CiteAudit-300): untuned 5-src F1 0.685 / FPR 0.140 → frozen 5-src F1 0.781 / FPR 0.187 → **frozen 6-src F1 0.792 / FPR 0.140**.

### S13 — Example papers + retraction lookup by cited title (step 4.3)
- When / who: 2026-11-11 ~12:30 IST · Priyanshu
- Examples (`frontend/src/lib/examples.json`, pre-run by `backend/scripts/warm_examples.py`): **NeurIPS 2025 fakes** (6 confirmed fakes from NeurIPS-100 + 4 real; demo only, not an evaluation), **Retracted papers** (Wakefield 1998, Obokata 2014, Mehra/Surgisphere 2020 + 2 sound), **CiteAudit** arXiv 2602.23452 (clean).
- Results: NeurIPS example 6/6 fakes flagged (2 mismatch, 4 not found), 4/4 real verified · CiteAudit 24 verified / 9 can't verify / 0 flagged.
- **Bug found: Surgisphere (Lancet 2020) retraction missed.** Its best record was a figshare data deposit ("Data from Mehra et al. …", title < 95), so the work counted as not identified and the retraction lookup was skipped, although Retraction Watch has the exact title.
- Fix: the cited title is now always looked up (exact normalised match, ≥ 6 words, as before); matched-DOI lookup still needs the work identified. This changes only the retraction flag, never verified/flagged status, so RQ1 numbers are unaffected. Check: **0 title hits** across all 1,400 eval citations (dev_1000, CiteAudit-300, NeurIPS-100), so no new false retraction flags there. Re-run: **3/3 retractions caught**. Report cache version v3 → v4.
- Cached example replay: POST → final report event **0.02 s**. (Over `localhost` on Windows each new connection first tries IPv6 and costs ~2 s in Python clients; the frontend's local default is now `127.0.0.1`.)

### E4 — Claim support on SciFact (steps 6.1–6.2)
- When / who: 2026-11-11 15:05 IST · Priyanshu
- Code: `backend/app/pipeline/claims.py` (statement + cited abstract → SUPPORTS / CONTRADICTS / NOT_ENOUGH_INFO, confidence, verbatim quote; quote grounding by fuzzy partial match ≥ 90; abstention below τ). Model deepseek-v4.1-flash, thinking off, temperature 0.
- Data: SciFact claim–abstract pairs. Gold = rationale label, or NOT_ENOUGH_INFO for a cited abstract without rationale. **Train sample 200 pairs (seed 20261111) only to set τ; dev 340 pairs (138 S / 71 C / 131 NEI) as test** (SciFact test labels are hidden). Command: `eval/claims_eval.py` → `eval/results/e4_scifact.json`. Cost **$0.094**, 219 calls on the final run.
- τ = 0.85: confidence below which the lowest 20% of grounded train answers fall (fixed before looking at dev).
- **Dev results:**
  | Variant | Answered | Accuracy | Macro-F1 | ECE |
  |---|---|---|---|---|
  | direct | 100% | 0.850 | 0.843 | 0.038 |
  | + quote grounding | 100% | 0.850 | 0.843 | 0.038 |
  | + grounding + abstention (τ 0.85) | 85% | **0.899** | **0.893** | 0.021 |
- Accuracy vs abstention (dev): 0% 0.850 · 10% 0.886 · **20% 0.908** · 30% 0.924 · 40% 0.931.
- **H4:** "abstaining on the least-confident 20% raises accuracy by ≥ 5 points": met on the curve (+5.8 at 20%). With the train-chosen τ, dev abstained on only 15% (confidences are coarse: 0.6/0.7/0.8/0.85/0.9/0.95), gain **+4.9**: just short. Both reported.
- **Quote grounding never fired** (0 SUPPORTS/CONTRADICTS answers with a quote not in the abstract). On clean SciFact abstracts the model quoted faithfully; grounding stays as a safety net, with no measured effect here.
- Caveats: SciFact abstracts are likely in the model's training data; SciFact claims are short single claims, while real citing sentences are long and cite several works. On CiteAudit's own paper (16 citing sentences): 1 supported, 8 "abstract can't tell", 7 abstained, 0 contradicted.
- Engineering: the inference endpoint answered 8 parallel calls with HTTP 429. Added a global cap of 4 concurrent LLM calls and longer back-off (7 tries, up to 60 s) in `app/llm.py`.
- Product: claim checks run for references whose work is identified (title ≥ 95) and that have citing sentences (arXiv LaTeX path); τ from `tuned.json` → `claims.tau`. Report cache v4 → v5.

### E3 — Ablations (step 7.2), offline replay, frozen config
- When / who: 2026-11-11 15:20 IST · Priyanshu · `eval/ablations.py` → `eval/results/e3_ablations.json`. No new API calls, no tuning.
- **Cumulative cascade (exact replay: the cascade order is fixed, Crossref → OpenAlex → arXiv/DataCite/Open Library → S2):**
  | Sources | dev P | dev R | dev F1 | dev FPR | test F1 | test FPR |
  |---|---|---|---|---|---|---|
  | Crossref only | 0.631 | 0.944 | 0.756 | **0.552** | 0.721 | 0.633 |
  | + OpenAlex | 0.874 | 0.848 | 0.861 | 0.122 | 0.771 | 0.233 |
  | + arXiv, DataCite, Open Library | 0.914 | 0.830 | 0.870 | 0.078 | 0.781 | 0.187 |
  | + Semantic Scholar (all six) | 0.930 | 0.822 | **0.873** | **0.062** | 0.792 | 0.140 |
  Sanity check: the 5- and 6-source rows reproduce E3b and both disclosed test looks exactly.
- **Leave-one-out** (exact for S2; approximate for earlier sources, whose removal leaves later sources un-queried in our data, so an upper bound on harm): without Crossref F1 0.724 / FPR 0.506 · without OpenAlex 0.763 / 0.484 · without DataCite 0.867 / 0.098 · without arXiv 0.870 / 0.068 · without Open Library 0.872 / 0.064 · without S2 0.870 / 0.078 (dev).
- **Matching, six sources (dev F1):** strict frozen **0.873** · untuned defaults 0.740 · lenient (verified ≥ 80, no author floor) 0.643 · **title only 0.607**. Test: 0.792 / 0.677 / 0.601 / 0.536.
- **Finding:** sources and matching do different jobs. More indexes remove false alarms (55% → 6% of real references flagged); strict field matching is what catches fakes: with title-only matching even six indexes score about the baseline's 0.61.
- Cost / latency per reference (cold, collection logs): median 5.9 s (dev) / 8.5 s (test), p90 ~36 s (S2 throttling), 3.4–3.7 indexes asked. LLM parsing ≈ $0.0003 per reference (S11: $0.275 / 1,000). Test-set rows are analysis only; no choices were made from them.

### S14 — Citing sentences from PDFs (step 6.3)
- When / who: 2026-11-11 ~16:00 IST · Priyanshu
- PDF path now uses GROBID `processFulltextDocument` (sentence segmentation on): in-text citations (`<ref type="bibr" target="#bN">`) are linked to bibliography entries, giving up to 3 citing sentences per reference (markers → `[CITATION]`), plus the paper title from the TEI header (PDF reports used to show the file name). Raw reference strings are still parsed by the LLM (S10). Falls back to `processReferences` if full text fails. The arXiv PDF-only fallback uses the same path.
- HalluCiteChecker PDF: title extracted, **14 of 16** references got citing sentences, 7 claim checks run; 16 refs / 15 verified as before. $0.0024.

### S15 — Tortured-phrase scanner (step 8.1)
- When / who: 2026-11-11 ~16:20 IST · Priyanshu
- `backend/app/pipeline/tortured.py` + `backend/app/data/tortured_phrases.csv`: **86 fingerprints** = 45 documented computing/medical examples from Cabanac, Labbé & Magazinov 2021 (arXiv:2107.06751) + 41 social-science fingerprints (Zenodo 14753785, CC-BY-4.0). Whole-word, case-insensitive, line breaks allowed. "web of things" removed (a real research term).
- Scans the full text of arXiv (LaTeX, after removing comments/equations/figures) and PDF (GROBID abstract + body) inputs; pasted bibliographies have no full text.
- Checks: test PDF `test-inputs/07-tortured-phrases.pdf` → **8 hits** (counterfeit consciousness ×2, profound learning, profound neural organization, colossal information, irregular woodland, flag to commotion, backing vector machine), its 3 references verified. **0 hits** on CiteAudit (arXiv LaTeX) and HalluCiteChecker (PDF). Unit tests: 3 (incl. a clean paragraph using the correct terms → 0 hits).
- Not evaluated on a labelled corpus; the fingerprints are a curated subset of what the Problematic Paper Screener uses. Report cache v5 → v6.

### E2 — CoverageSet: false accusations by type × region (step 7.1)
- When / who: 2026-11-11 15:15–15:38 IST · Priyanshu · `eval/coverage_rq2.py` (build / run / report) → set `eval/data/coverageset.jsonl` (committed; OpenAlex metadata is CC0), runs `eval/data/raw/coverage_runs.jsonl`, results `eval/results/e2_coverage.json`.
- Set: **225 real works** sampled from OpenAlex (seed 20261111, published 2012–2024), 15 per cell: 5 types (article, book chapter, book, report, dataset) × 3 author-institution regions (India; other Global South: BR NG ID PK BD KE ZA EG VN PH MX CO; Global North: US GB DE FR CA AU NL JP). Formatted as plain APA-like citations **without DOIs**. All real, so every flag is a false accusation.
- Systems on the same LLM-parsed references: **baseline re-created** (Semantic Scholar only, AtomGPT v2 scoring from its released config: title token_set 0.60 / authors 0.25 / journal 0.15, renormalised over available fields, verified ≥ 80, partial ≥ 60, top-5); **Vouch without OpenAlex**; **Vouch** (six sources). 7 items dropped where the baseline's S2 lookup failed → n = 218. ~15 min.
- **Flagged share (any non-verified verdict) / hard accusations (baseline "likely hallucinated"; Vouch not found or mismatch):**
  | Type | Baseline | Vouch − OpenAlex | Vouch |
  |---|---|---|---|
  | article (n=43) | 0.05 / 0.02 | 0.07 / 0.05 | 0.00 / 0.00 |
  | book (45) | 0.18 / 0.04 | 0.13 / 0.13 | 0.02 / 0.02 |
  | report (42) | 0.26 / 0.21 | 0.31 / 0.14 | 0.10 / 0.02 |
  | book chapter (44) | 0.36 / 0.23 | 0.41 / 0.39 | 0.02 / 0.00 |
  | **dataset (44)** | **0.70 / 0.68** | 0.57 / 0.57 | 0.09 / 0.09 |
  | **all (218)** | 0.31 / 0.24 | 0.30 / 0.26 | 0.05 / 0.03 |
  By region (baseline): India 0.22, other Global South 0.35, Global North 0.36. (Vouch − OpenAlex: 0.24 / 0.28 / 0.38.)
- **H2 verdict: half supported.** Type: yes, strongly. A single-index checker calls 68% of real datasets "likely hallucinated" and flags 36% of book chapters vs 5% of articles. **Region: not supported** in this sample; Indian references were flagged *less* than Global North ones (the Global North dataset cell, 93%, drives it). An interim look at the first 61 rows suggested the opposite; it did not hold.
- **Vouch without OpenAlex is no better than the baseline overall (0.30 vs 0.31)**; it helps only on Global South datasets (0.33 vs 0.80). Full Vouch's 0.05 is partly circular (the set was sampled from OpenAlex), so we do not claim it as a coverage result. Honest reading: open-index coverage of non-article works is the bottleneck, and OpenAlex is the index that covers them.
- Limitations: 15 per cell (wide intervals); region = any author institution in that region; citations generated from metadata are cleaner than real ones.

### S16 — Physics (APS/RevTeX) bibliographies, found by the audit (step 8.2)
- When / who: 2026-11-11 ~16:40 IST · Priyanshu
- Audit paper 25 (a physics paper) gave 78 "detail mismatch" out of 129 references. Cause: APS style cites journal articles **without titles**; with no cited title, a resolving DOI looked like "a real DOI attached to a different work". Also RevTeX `ibinfo {author} {…}` macros (with spaces) leaked "author author / journal journal" into the reference text.
- Fixes: (1) no cited title + resolving DOI → judged on authors and year (verified if they agree, otherwise mismatch without the hijack message); (2) RevTeX macros stripped. Tests added (89 pass). Report cache v6 → v7.
- **Disclosure:** replaying the frozen test collections with this fix changes **one** CiteAudit-300 verdict: a real Nature news item whose title the LLM parser failed to extract (it was a false alarm, now verified): FPR 0.140 → 0.133, F1 0.792 → 0.794. The fix was motivated by the audit, not by the test set, but the **reported headline numbers stay those of the frozen run** (`e1_test_results_6sources.json`). Dev: 1 such item. NeurIPS-100: none.
