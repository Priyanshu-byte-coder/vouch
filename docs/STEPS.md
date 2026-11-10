# Vouch — Step-by-Step Runbook

> **Owner:** Priyanshu (all roles: pipeline, research, product, deploy), building with Claude Code.
> **Rule:** one step at a time. A step is done only when its **✅ Done when** check passes. Then tick it and move on.
> **Deadline:** submit by **Thu 12 Nov, 23:00 IST** (portal closes 13 Nov 00:00).
> Design details live in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Numbers go in [../EXPERIMENTS.md](../EXPERIMENTS.md).

**Who does what:**
- 👤 **You** — accounts, keys, payments, approvals, hand-checking, recording the video, submitting
- 🤖 **Claude** — writes code, runs commands, reports results; you review

| Phase | Steps | Target finish (IST) |
|---|---|---|
| 0. Setup | 0.1–0.4 | Tue 10 Nov, 10:00 |
| 1. Data + baseline | 1.1–1.3 | Tue 10 Nov, 15:00 |
| 2. Core pipeline (MVP backend) | 2.1–2.7 | Tue 10 Nov, 23:00 ← **Checkpoint 1** |
| 3. Measure RQ1 | 3.1–3.3 | Wed 11 Nov, 11:00 |
| 4. Frontend | 4.1–4.3 | Wed 11 Nov, 16:00 |
| 5. Deploy | 5.1–5.3 | Wed 11 Nov, 19:00 |
| 6. P1: claim support + PDF | 6.1–6.3 | Wed 11 Nov, 24:00 ← **Checkpoint 2** |
| 7. P2: RQ2 + RQ3 | 7.1–7.2 | Thu 12 Nov, 08:00 |
| 8. P3: tortured phrases + audit | 8.1–8.3 | Thu 12 Nov, 13:00 |
| 9. Ship | 9.1–9.6 | Thu 12 Nov, 23:00 ← **Submit** |
| 10. Finals prep | 10.1–10.3 | Sun 15 Nov, 12:00 |

---

## Phase 0 — Setup

### 0.1 Repo ✅
- 🤖 Created private repo `Priyanshu-byte-coder/vouch` and pushed all history.
- ✅ Done when: https://github.com/Priyanshu-byte-coder/vouch shows the docs.

### 0.2 Accounts and API keys (👤 you, ~20 min) ✅ (S2 key pending, Vercel login deferred to Phase 5)
| # | What | Where | Notes |
|---|---|---|---|
| a | **Semantic Scholar API key** | https://www.semanticscholar.org/product/api#api-key-form | Approval can take hours or days. Request it **first**. We work without it meanwhile |
| b | **OpenAlex API key** (free, $1/day) | https://openalex.org → sign up → Settings → API key | Instant |
| c | **Crossref polite-pool email** | — | Just your email, no signup |
| d | **LLM endpoint**: Vultr Serverless Inference | Vultr dashboard → Serverless Inference → subscribe → copy the **inference API key** | ⚠️ Paid from your $200 credit. Confirm the price on the page before subscribing. This key is separate from the Vultr account key |
| e | **Vercel account** + CLI | https://vercel.com (sign in with GitHub), then run `npm i -g vercel` and `vercel login` | For the frontend deploy |
| f | Docker Desktop running | — | For GROBID (PDF parsing) |

- Then: copy `.env.example` → `.env` and paste the keys in. **Don't paste keys in chat.** Tell Claude when it's done.
- ✅ Done when: `.env` exists locally with at least the OpenAlex key, the Crossref email and the LLM key filled in.

### 0.3 Local dev environment (🤖) ✅
- Create `backend/` with a Python 3.12 venv and `requirements.txt` (fastapi, uvicorn, httpx, pydantic, rapidfuzz, unidecode, bibtexparser, pymupdf, openai, pandas, python-dotenv, pytest).
- Smoke-test each API with a single request: Crossref, OpenAlex, S2, arXiv, and the LLM `/models` endpoint.
- ✅ Done when: the smoke-test script prints OK for every source and lists the LLM model names. We then pick `LLM_MODEL_PARSE` and `LLM_MODEL_JUDGE`.

### 0.4 GROBID container (🤖, you approve the Docker pull) ✅
- `docker run -d --name grobid --restart unless-stopped -p 8070:8070 --memory 4g grobid/grobid:0.9.1-crf` (lightweight CRF models, 0.5 GB; the 15 GB `-full` image isn't needed for references)
- ✅ Done when: `curl localhost:8070/api/isalive` returns `true`.

---

## Phase 1 — Data + baseline

### 1.1 Download datasets (🤖) ✅
- CiteAudit `benchmark.json` (9,442 citations) · AtomGPT `data/` (CiteAudit-300, NeurIPS-100) · SciFact · Retraction Watch CSV · PPS tortured-phrase fingerprints
- Record each licence in `eval/data/SOURCES.md`. Large raw files go in `eval/data/raw/` (gitignored), with download scripts committed.
- ✅ Done when: `python eval/data/download.py` fetches everything and prints row counts.

### 1.2 Dev/test split (🤖) ✅
- Test = CiteAudit-300 + NeurIPS-100 (untouched). Dev = full CiteAudit **minus** any citation in the 300 set (deduplicated on normalised text).
- ✅ Done when: the split files are written, overlap = 0, and the counts are logged in `EXPERIMENTS.md`.

### 1.3 Baseline E0 (🤖 runs, 👤 reviews) ✅ (a) done · (b) replaced by an in-pipeline re-creation in E3 (see EXPERIMENTS.md)
- (a) Re-score AtomGPT's **released outputs**, which reproduces their published table without any API calls.
- (b) Re-run their detector on CiteAudit-300 with **our LLM**, so the comparison against our system is fair.
- ✅ Done when: the E0 rows in `EXPERIMENTS.md` are filled in, and (a) matches the published P 0.80 / R 0.49 / F1 0.61 / FPR 0.12.

---

## Phase 2 — Core pipeline (MVP backend)

### 2.1 Foundations (🤖) ✅
- `models.py` (pydantic schema from plan §4.8), `config.py`, `cache.py` (SQLite), `llm.py` (OpenAI-compatible, JSON mode, token and cost logging)
- ✅ Done when: unit tests pass, and one LLM JSON call works and is logged.

### 2.2 Resolvers (🤖) ✅ (all 6 sources, incl. DataCite + Open Library pulled forward from 3.3)
- Crossref (DOI + bibliographic search), OpenAlex (search + abstract), Semantic Scholar (match), arXiv (by ID + search). All async, cached, rate-limited.
- ✅ Done when: 5 known references (article, preprint, book, dataset, fake) return sensible candidates from each source in a test script.

### 2.3 Matcher + verdict v1 (🤖) ✅
- Field scores (title, authors, year, venue), diacritic folding, `et al.` handling, DOI–title consistency check, the 4 labels.
- ✅ Done when: the unit tests on the edge cases from the AtomGPT "Known limitations" list pass.

### 2.4 Bibliography-text path, end to end (🤖) ✅
- CLI: `python -m app.cli check --bib refs.txt` → report JSON.
- ✅ Done when: a pasted 20-reference list (with 3 planted fakes) produces a report that flags the fakes.

### 2.5 arXiv ingestion (🤖) ✅
- Fetch the e-print → parse `.bbl`/`.bib`. Map `\cite{}` to sentences (contexts for step 6).
- ✅ Done when: `check --arxiv <id>` works on 3 real recent papers.

### 2.6 Retraction check (🤖) ✅
- RW CSV → DOI/PMID lookup.
- ✅ Done when: a reference list containing a known retracted DOI gets flagged with date and reason.

### 2.7 FastAPI + live progress (🤖) ✅
- Routes from plan §4.9, background jobs, SSE events.
- ✅ Done when: `curl` POST → job ID → events stream → final report.

> **🚩 Checkpoint 1 (Tue 23:00): ✅ reached Tue 17:34 IST.** an arXiv ID gives a real report through the API. Baseline numbers are logged. Commit + push.

---

## Phase 3 — Measure RQ1

### 3.1 Tune on dev (🤖, 👤 approves thresholds)
- Grid-search weights and thresholds on the **dev split only**. Log every configuration tried.
- ✅ Done when: the chosen config is frozen in `eval/configs/rq1.yaml` and the dev numbers are logged.

### 3.2 E1 on test (🤖)
- Run on CiteAudit-300 + NeurIPS-100 with the frozen config. Bootstrap 95% CIs. Error analysis on misses and false positives.
- ✅ Done when: the results summary table in `EXPERIMENTS.md` has our numbers next to the baseline's.

### 3.3 More sources + AI review (🤖)
- (DataCite + Open Library already built in 2.2.) Add the LLM adjudicator for borderline matches → re-run on dev → re-freeze → re-test once.
- ✅ Done when: the v2 numbers are logged. Keep whichever version is honestly better on dev; the test set is not used for that choice.

---

## Phase 4 — Frontend

### 4.1 Scaffold + design (🤖)
- Next.js + Tailwind + shadcn/ui in `frontend/`. Pages `/`, `/report/[id]`, `/research`, using mock JSON.
- ✅ Done when: `npm run dev` shows all 3 pages with mock data.

### 4.2 Wire to the API (🤖)
- Input tabs (arXiv / bibliography / PDF), live progress from SSE, report table, evidence drawer, download JSON/CSV.
- ✅ Done when: a local end-to-end run from the browser works on 3 papers.

### 4.3 Example papers (🤖, 👤 picks)
- Pre-run and cache 3 demo papers (one with a fake, one with a retraction, one clean) for the "Try an example" buttons.
- ✅ Done when: the example buttons load instantly.

---

## Phase 5 — Deploy

### 5.1 Vultr VM (👤 approves the cost, 🤖 sets it up)
- ⚠️ Creates a billable server (`vc2-2c-4gb`, ~$20/month, Mumbai or Bangalore). Delete it after the finals.
- docker compose: `api` + `grobid` + `caddy` (HTTPS through an `sslip.io` hostname). `.env` is copied over SSH, never committed.
- ✅ Done when: `https://api.<ip>.sslip.io/api/health` returns OK from your phone.

### 5.2 Vercel frontend (🤖 runs `vercel`, 👤 logged in)
- Set `NEXT_PUBLIC_API_URL`, then `vercel --prod`.
- ✅ Done when: the public URL runs a full check end to end.

### 5.3 Demo safety (🤖)
- Cache warm-up, a request timeout, a friendly error message, a rate limit on the public API.
- ✅ Done when: three checks in parallel don't break it.

---

## Phase 6 — P1: claim support + PDF

### 6.1 Claim support (🤖)
- Context → abstract → LLM verdict, the quote-grounding check, abstention.
- ✅ Done when: the evidence drawer shows claim checks with highlighted quotes.

### 6.2 E4 SciFact (🤖)
- Three variants: direct / + grounding / + abstention. Report macro-F1, the accuracy-vs-coverage curve and ECE.
- ✅ Done when: the numbers and a figure are logged.

### 6.3 PDF upload via GROBID (🤖) 🟡 upload + references done in 2.7 (40/40 on a test PDF); citation contexts from the PDF full text still to do
- ✅ Done when: uploading a PDF gives a report on both local and deployed versions.

> **🚩 Checkpoint 2 (Wed 24:00):** MVP + P1 live on the public URL. RQ1 + RQ4 logged. Commit + push.

---

## Phase 7 — P2: research depth

### 7.1 E2 CoverageSet / RQ2 (🤖, 👤 spot-checks 30 items)
- Sample ~600 real references by type × region (Indian and Global South vs. others) through OpenAlex/Crossref, plus ~300 generated fakes. Run the baseline and ours.
- ✅ Done when: the FPR-by-stratum table and chart are logged.

### 7.2 E3 ablations / RQ3 (🤖)
- Remove one source at a time, remove the adjudicator, title-only matching. Measure cost and latency.
- ✅ Done when: the ablation table is logged.

---

## Phase 8 — P3: tortured phrases + real-paper audit

### 8.1 Tortured-phrase scanner (🤖)
- ✅ Done when: a test text containing "counterfeit consciousness" gets flagged in the report.

### 8.2 E5 audit run (🤖)
- ~200 recent arXiv papers + ~50 Indian-affiliated papers. Batch run.
- ✅ Done when: all reports are saved and the flags are exported to `eval/results/e5_flags.csv`.

### 8.3 Hand verification (👤 you, ~2–3 h)
- Check each flagged reference by hand and label it correct flag / wrong flag. This gives honest precision.
- ✅ Done when: every flag is labelled. 🤖 then computes prevalence + precision (aggregate only, no paper names).

> **Code freeze: Thu 14:00.** Bug fixes only after this.

---

## Phase 9 — Ship

### 9.1 Project README (🤖 drafts, 👤 edits)
- Convert README.md into the project README: all 10 Unstop fields, architecture, results tables and figures, how to run, datasets and AI tools used, limitations, acknowledgements. Keep the hackathon brief in `docs/HACKATHON.md`.
- ✅ Done when: someone new could run it and understand our results from the README alone.

### 9.2 Licence + public repo (👤 you)
- Choose a licence (MIT or Apache-2.0) → 🤖 adds the LICENSE → you run `gh repo edit --visibility public` (or use repo Settings).
- ✅ Done when: the repo is public and the licence shows in its About section.

### 9.3 Demo video ≤ 3 min (👤 records, 🤖 writes the script)
- Follow plan §9. Upload to YouTube (unlisted or public).
- ✅ Done when: the link plays in a logged-out browser.

### 9.4 Fresh-browser dry run (👤)
- ✅ Done when: the live URL, example buttons, a new arXiv ID, PDF upload and the research page all work from incognito.

### 9.5 Unstop form (👤 submits, 🤖 drafts every field)
- Fill all 10 fields, using the mapping in plan §8.
- ✅ Done when: submitted and a confirmation screenshot is saved. **Target 21:00, hard stop 23:00.**

### 9.6 Tell the team
- Share the links with Viranshul and Kuldeep. Optionally add a pointer from `Viranshul-P/threws-odyssey-2026` to the new repo.

---

## Phase 10 — Finals prep (if shortlisted)
### 10.1 Slides (🤖 drafts, 👤 edits): 8–10 slides, problem → gap → method → results → demo → impact → limitations
### 10.2 Rehearse the live demo twice, and keep a recorded fallback ready
### 10.3 Q&A sheet: thresholds, data leakage, false accusations, cost, ethics, comparison with CiteAudit and AtomGPT

**Finals: Sun 15 Nov, 12:00–18:00 IST.** After the finals, delete the Vultr VM and rotate the Vultr account key.
