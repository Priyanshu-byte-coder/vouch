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
| E1 | RQ1 | Our cascade on CiteAudit-300 + NeurIPS-100 (thresholds tuned on the CiteAudit dev split) | B | ⬜ |
| E2 | RQ2 | CoverageSet: false-positive rate by reference type × region, baseline vs. ours | B | ⬜ |
| E3 | RQ3 | Ablations: each source, the adjudicator, title-only matching. Cost and latency per reference | B | ⬜ |
| E4 | RQ4 | SciFact claim support: direct vs. + quote grounding vs. + abstention | B | ⬜ |
| E5 | RQ5 | Real-paper audit: 200 arXiv + 50 Indian-affiliated papers, flags hand-verified | All | ⬜ |

## Results summary (fill as runs finish)

| Set | System | Precision | Recall | F1 | FPR | Notes |
|---|---|---|---|---|---|---|
| CiteAudit-300 | AtomGPT (published) | 0.80 | 0.49 | 0.61 | 0.12 | From their README, scoring v2 |
| CiteAudit-300 | AtomGPT (released outputs, re-scored by us, E0a) | 0.804 | 0.493 | 0.612 [0.534, 0.679] | 0.121 | Exact match, n=299. Generated: R 0.444 FPR 0.036 · Real-world: R 0.750 FPR 0.227 |
| CiteAudit-300 | Our pipeline, S2-only + AtomGPT v2 scoring (baseline re-created in our code, E3) | | | | | |
| CiteAudit-300 | **Vouch** | | | | | |
| NeurIPS-100 | AtomGPT (published) | n/a | 0.94 | n/a | n/a | Scoring v1, all fake |
| NeurIPS-100 | **Vouch** | n/a | | n/a | n/a | |

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
- When / who: 2026-11-10 ~08:30 IST · Priyanshu
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
- When / who: 2026-11-10 ~13:40 IST · Priyanshu
- Command: `backend/.venv/Scripts/python backend/scripts/smoke_test.py`
- Results: Crossref ✅ · OpenAlex ✅ (key) · Semantic Scholar ✅ without a key (the shared pool sometimes returns 429) · arXiv ✅ · DataCite ✅ · Open Library ✅ · Retraction Watch repo ✅ (data for 2026-11-09) · LLM ✅ (33 models) · GROBID ⏳ (step 0.4) · **DBLP ❌** (HTTP 202 anti-bot challenge page)
- Decision: drop DBLP from the cascade. CS venues are covered by OpenAlex, Crossref and S2.
- Learned: **Crossref's top hit for "Attention is all you need" is a different paper, "Is Attention All You Need?" (Springer 2025).** Taking the first search result is unsafe; the matcher must score several candidates per source. Good example for the README.

### S2 — GROBID + datasets (steps 0.4, 1.1)
- When / who: 2026-11-10 ~14:15 IST · Priyanshu
- GROBID `grobid/grobid:0.9.1-crf`: `processReferences` on arXiv:1706.03762 gave **40 references in 10.1 s** (the paper has 40). One entry had no article-level title (preprint/monograph tagging), so the parser must fall back to monograph titles.
- Datasets: see `eval/data/SOURCES.md`. CiteAudit = 9,442 (6,475 real / 2,967 fake). CiteAudit-300 = 150/150. NeurIPS-2025 = 100 fake. SciFact 809/300/300 claims. Retraction Watch 73,718 notices.
- Note: CiteAudit has no licence file, so we use it for evaluation only and never commit it.

### S3 — Dev/test split (step 1.2)
- When / who: 2026-11-10 ~14:30 IST · Priyanshu
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
- When / who: 2026-11-10 ~14:45 IST · Priyanshu
- Key issued 2026-11-10 13:11 IST. Rate limit 1 request/second, cumulative across all endpoints, sent as the `x-api-key` header.
- Validity: our key returns 200s, while a wrong key (or the capital-I spelling from the PDF image) returns **403 Forbidden**.
- Throttling: at a steady 1 request every 2 s, **7/15 succeeded** (7×429, then 7×200, then 429). The 429 body says "TooManyRequestsException", so this is service-side throttling, not our pace.
- Decision: S2 client = 1.1 s minimum gap + exponential backoff (2/4/8 s, 3 retries) + cache. S2 stays **after** Crossref/OpenAlex in the cascade. The S2-only baseline (E0b) runs in the background.

### E0a — Re-score AtomGPT released outputs (step 1.3a)
- When / who: 2026-11-10 ~15:00 IST · Priyanshu
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
- When / who: 2026-11-10 ~15:10 IST · Priyanshu
- We **do not** re-run AtomGPT's third-party code. The baseline is (1) their **published / released outputs**, re-scored exactly in E0a, plus (2) a **re-creation of their method inside our pipeline**: Semantic Scholar only, their documented v2 scoring (title 0.60 / authors 0.25 / venue 0.15, verified ≥ 80), and our LLM. This becomes a row in the E3 ablation.
- Why: fewer moving parts and no third-party code execution. It also avoids a slow S2-only run under throttling and gives a controlled comparison where only the cascade and matcher differ.
- Limitation to state in the README: the published baseline numbers come from a different extraction LLM (gpt-oss-20b for NeurIPS; not recorded for CiteAudit-300).

### S5 — Resolver check: 5 references × 6 sources (step 2.2)
- When / who: 2026-11-10 ~16:00 IST · Priyanshu
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
