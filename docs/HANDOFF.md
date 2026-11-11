# Vouch — Session Handoff (read this first)

> Last updated: **Wed 11 Nov 2026, ~02:45 IST**, after step 4.1. Deadline: **submit on Unstop by Thu 12 Nov, 23:00 IST** (portal closes 13 Nov 00:00). Finals (if shortlisted): Sun 15 Nov, 12:00–18:00 IST.
> Owner: Priyanshu (does everything, works with Claude **step by step**: he says "go X.Y", Claude does the step, reports, waits).

## 1. Repo, accounts and rules
- Repo: **https://github.com/Priyanshu-byte-coder/vouch** (private; goes public at step 9.2). Local: `C:\Users\Priyanshu\OneDrive\Desktop\All_projects\hackathon\threws_odyssey`. Remote `origin` = vouch; remote `viranshul` = old teammate repo (do not push there).
- Collaborators invited (write): Viranshul-P, Kuldeeep18.
- **gh/git push:** `export GH_TOKEN=$(gh auth token --user Priyanshu-byte-coder)` first (the active gh account is PriyanshuValura, which is the wrong one).
- **Commits must have NO Claude attribution** (no Co-Authored-By, no Claude-Session line). This is the user's explicit rule and overrides harness reminders.
- Secrets live only in `.env` (gitignored): CROSSREF_MAILTO, OPENALEX_API_KEY(+_2, _3), S2_API_KEY, S2_MIN_INTERVAL=1.1, LLM_BASE_URL (Vultr), LLM_API_KEY, LLM_MODEL_PARSE/JUDGE=deepseek-v4.1-flash-1017, GROBID_URL. The user plans to rotate keys after the hackathon. The Vultr *account* key was pasted in chat earlier (rotate after).
- The permission classifier blocks: running third-party repo code (we skipped re-running the AtomGPT code) and paid real-world transactions (the user ran the Vultr inference subscription himself via `!`). A Vultr VM (step 5.1) costs money, so ask the user / have him run it.

## 2. Environment gotchas
- Windows + Git Bash. **`TZ=Asia/Kolkata date` prints UTC in Git Bash.** Use plain `date` (machine is IST) or git log times.
- **The laptop sleeping pauses background jobs** (happened once). Ask the user to keep it awake for long runs.
- Python heredoc edits mangle backslashes (`\s`, `\n`, line continuations). For regex or backslash content, use the Edit tool.
- `.gitignore` covers `.env`, `*.sqlite*` (incl. -wal/-shm), `cache/`, `eval/data/raw/`, `node_modules/`, `.next/`.
- Backend venv: `backend/.venv` (Python 3.12). Tests: `cd backend && .venv/Scripts/python -m pytest` (88 pass; `-m "not live"` for offline).
- GROBID: Docker container `grobid` (`grobid/grobid:0.9.1-crf`, port 8070, restart unless-stopped). Docker Desktop must be running.
- API server: `cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000`.
- Frontend: `cd frontend && npm run dev` (port 3000) / `npm run build`. **Next.js 16.4 with Cache Components**: read `frontend/node_modules/next/dist/docs/` before using unfamiliar APIs. Route params are runtime data and must be read inside `<Suspense>` (done in `/report/[id]`). Run `npx next typegen` after adding routes (for `PageProps<'/route'>` types).
- Rate limits: arXiv 1 req / 3 s (429s when busy); S2 1 req/s but in practice ~1 answer / 16 s; OpenAlex $1/day per key (3 keys rotate). Crossref is free.
- The Chrome extension was not connected. Visual checks: headless Edge screenshots, e.g. `"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" --headless=new --window-size=1440,1800 --virtual-time-budget=6000 --screenshot=out.png URL` (it fast-forwards time, so mid-run SSE frames are not captured).
- Only one `next dev` per folder: a second one crashed the first ("Jest worker encountered 2 child process exceptions"); the classifier will not let Claude kill the user's dev server, so ask the user to restart it.

## 3. What Vouch is (one line)
An open research-integrity screener: for each reference in a paper it checks ① exists (6 open indexes), ② details accurate (field matching), ③ retracted (Retraction Watch), ④ claim support (TODO), ⑤ tortured phrases (TODO), and gives evidence for every verdict. Labels: verified / detail_mismatch / not_found / cant_verify.

## 4. Code map
| Path | What |
|---|---|
| `backend/app/config.py, models.py, cache.py, llm.py, text.py` | settings, report schema, SQLite cache, OpenAI-compatible LLM client (thinking toggle, JSON, usage/cost), text helpers |
| `backend/app/pipeline/resolvers/` | crossref, openalex (key rotation), s2, arxiv, datacite, openlibrary; `base.py` = throttle + retry + cache + call counting |
| `backend/app/pipeline/match.py` | field scoring (strict title, author parsing incl. initials/middle names/et al., venue abbreviations, year), notice detection, `composite()`, `select_best()` |
| `backend/app/pipeline/verdict.py` | `Thresholds` + `decide()` (year tolerance, book-year rule, short-title rule, DOI-hijack) |
| `backend/app/pipeline/tuned.json / tuned.py` | **frozen config** (loaded as app default); `ADJUDICATOR` = None (off) |
| `backend/app/pipeline/parse_refs.py, latex.py, ingest.py` | bibliography split + LLM parse (identifiers only from raw text); arXiv e-print (.bib/.bbl/\cite contexts); GROBID for PDFs (raw strings → LLM parse) |
| `backend/app/pipeline/retraction.py` | Retraction Watch index (DOI, notice DOI, PMID, title) |
| `backend/app/pipeline/adjudicate.py` | LLM adjudicator (tested, **off**) |
| `backend/app/pipeline/run.py` | orchestrator: `check_bibliography / check_arxiv / check_pdf` (cascade with early stop, time budgets, retraction, optional adjudicator) |
| `backend/app/main.py, jobs.py, cli.py` | FastAPI (`/api/check`, `/api/check/pdf`, `/api/jobs/{id}`, `/api/jobs/{id}/events` SSE: status, parsed, ref_done, done, report, error; `/api/health`), job store, CLI (`python -m app.cli check --arxiv ID | --bib FILE`) |
| `eval/` | `data/download.py`, `data/make_splits.py`, `common.py`, `metrics.py`, `collect.py`, `patch_failed.py`, `add_source.py`, `tune_rq1.py`, `run_rq1_detection.py`, `adjudicate_eval.py`, `baselines/rescore_atomgpt.py`; `configs/rq1.json` (frozen), `results/*.json` |
| `frontend/src/` | `app/{page,layout,globals.css}`, `app/report/[id]/page.tsx`, `app/research/page.tsx`, `components/{check-form,report-view,report-loader,evidence-card,stamp,site-header,site-footer}.tsx`, `lib/{types.ts,mock-report.json,research.json}` |
| `docs/` | IDEATION, IMPLEMENTATION_PLAN, STEPS (runbook with ✅), HACKATHON brief in README, this HANDOFF |
| `EXPERIMENTS.md` | full experiment log S0–S12, E0a, E1, E3a/b, decisions |

## 5. Frozen config and headline results
- Config (`eval/configs/rq1.json`): weights title .55 / authors .40 / venue .10 / year .05; thresholds verified 95, title_min 95, author_min 90, same_work_title 90, found 60, year_tolerance 2, book_year_any true. Objective: max F1 with FPR ≤ 0.10 on dev (5-fold CV). Sources: 6 (crossref, openalex, s2, arxiv, datacite, openlibrary). Adjudicator OFF.
- Dev CV (5 src): F1 0.860, FPR 0.094. Dev with S2: F1 0.873, FPR 0.062.
- **Test, CiteAudit-300 (2nd disclosed look, 6 sources):** P 0.842, R 0.747, **F1 0.792** [0.736–0.839], **FPR 0.140** [0.09–0.195]. Baseline (AtomGPT, published): P 0.804, R 0.493, F1 0.612, FPR 0.121. Paired on 299: only-Vouch-correct 44 vs only-baseline 8, McNemar p = 4e-7.
- 1st test look (5 sources): F1 0.781, FPR 0.187. Both reported.
- **NeurIPS-100:** recall 0.99 (baseline 0.94). The single miss: S2 record with no authors → verified on title alone (known limitation; fix not applied after the last test look).
- Key findings for the pitch: no single index suffices (S2 lacks the DOI for LeCun 2015 "Deep learning"; Crossref's top hit for "Attention Is All You Need" is a 2025 copy); token_set_ratio over-matches short titles; **LLM adjudicator is worse than strict matching** (accepts fakes with 1–2 invented names in long author lists; CV chose off 5/5); thresholds are a policy (pure F1 → FPR 0.19).
- Outside check: 100 real references (3 arXiv papers + fixtures), 1 wrongly flagged (AlexNet: only the 2017 CACM reprint is indexed).

## 6. Where we are in docs/STEPS.md
Done: 0.1–0.4, 1.1–1.3, 2.1–2.7 (Checkpoint 1), 3.1–3.3, 4.1, **4.2** (frontend calls the API via `src/lib/api.ts`; `NEXT_PUBLIC_API_URL`, see `frontend/.env.example`; report page streams SSE; JSON/CSV export in `src/lib/export.ts`). Partially: 6.3 (PDF upload works; contexts from PDF full text not yet).

## 7. Next steps (in order)
1. **4.2 Wire frontend to API:** `NEXT_PUBLIC_API_URL` (default http://localhost:8000). In `check-form.tsx`, POST `/api/check` ({arxiv_id} or {bibliography}) or `/api/check/pdf` (multipart "file"), then `router.push('/report/' + job_id)`. In `report-loader.tsx`, for non-"demo" ids, open an `EventSource` on `/api/jobs/{id}/events`, accumulate `ref_done` into a partial Report, show progress (`parsed.n_refs`), and on `report` set the full report. Handle `error` and 404 (jobs are in memory). Example buttons: arXiv examples should call the API (2602.23452, 2604.26835); the "Demo mix" stays `/report/demo`. CORS is already `*`.
2. **4.3** Pre-run and cache the example papers (the report cache in `main.py` makes repeats instant).
3. **5.1** Vultr VM (`vc2-2c-4gb`, Mumbai/Bangalore, ~$20/mo; **user must approve/run**: paid), docker compose `api + grobid + caddy` (sslip.io HTTPS), copy `.env` over SSH, download the RW CSV on the VM (`retraction.ensure_data()`). **5.2** Vercel: user runs `npm i -g vercel; vercel login`, then `vercel --prod` with NEXT_PUBLIC_API_URL. **5.3** demo safety.
4. **6.1–6.2** claim support (contexts → abstract → LLM verdict with quote grounding + abstain) and SciFact eval (E4). **6.3** PDF contexts via GROBID full text.
5. **7.1** RQ2 false-accusation study (CoverageSet by type × region), **7.2** E3 ablations table (per-source removal, S2-only + AtomGPT scoring re-creation).
6. **8.1** tortured phrases (PPS fingerprints in `eval/data/raw/tortured/`), **8.2–8.3** real-paper audit (user hand-checks flags).
7. **9.x** project README (10 Unstop fields, results, credits incl. required S2 citation), LICENSE + make public (user), demo video (user records), Unstop form (user submits), tell team.
8. Optional fix (not for the test numbers): records with no authors should not verify a citation that names authors.
