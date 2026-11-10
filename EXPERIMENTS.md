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
| E0 | — | Published baseline (AtomGPT detector) on CiteAudit-300 + NeurIPS-100, with our LLM. Re-score their released outputs | B | ⬜ |
| E1 | RQ1 | Our cascade on CiteAudit-300 + NeurIPS-100 (thresholds tuned on the CiteAudit dev split) | B | ⬜ |
| E2 | RQ2 | CoverageSet: false-positive rate by reference type × region, baseline vs. ours | B | ⬜ |
| E3 | RQ3 | Ablations: each source, the adjudicator, title-only matching. Cost and latency per reference | B | ⬜ |
| E4 | RQ4 | SciFact claim support: direct vs. + quote grounding vs. + abstention | B | ⬜ |
| E5 | RQ5 | Real-paper audit: 200 arXiv + 50 Indian-affiliated papers, flags hand-verified | All | ⬜ |

## Results summary (fill as runs finish)

| Set | System | Precision | Recall | F1 | FPR | Notes |
|---|---|---|---|---|---|---|
| CiteAudit-300 | AtomGPT (published) | 0.80 | 0.49 | 0.61 | 0.12 | From their README, scoring v2 |
| CiteAudit-300 | AtomGPT (our re-run) | | | | | |
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
