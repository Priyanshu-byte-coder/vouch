# Experiment Log — CiteSentinel

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
| CiteAudit-300 | **CiteSentinel** | | | | | |
| NeurIPS-100 | AtomGPT (published) | n/a | 0.94 | n/a | n/a | Scoring v1, all fake |
| NeurIPS-100 | **CiteSentinel** | n/a | | n/a | n/a | |

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
