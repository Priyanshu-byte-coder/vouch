# Vouch manual test sheet

Inputs for testing the website on http://localhost:3000. Every "Expect" below was produced by running the
same input through the API on 11 Nov 2026 (frozen config, 6 sources). Times depend on caches and on arXiv.

**Before you start** (three terminals):
1. Docker Desktop running (GROBID container `grobid` on port 8070, only needed for PDFs).
2. API: `cd backend; $env:VOUCH_RATE_LIMIT=100; .venv\Scripts\python -m uvicorn app.main:app --port 8000`, then once: `.venv\Scripts\python scripts\warm_examples.py` (pre-runs the example buttons)
3. Website: `cd frontend; npm run dev` (only one `next dev` at a time).

Check http://localhost:8000/api/health shows `"grobid":true` and `"retraction_index_loaded":true`.

## A. Happy paths

| # | Where | Input | Expect |
|---|---|---|---|
| A1 | Example button | **Demo mix** | Opens `/report/demo` instantly. 27 refs: 16 verified, 2 mismatch (#16 ResNet with wrong details, #17 invented "Graph transformers for protein folding at scale"), 1 not found (#15 invented), 8 unverified (web pages/tools), **2 RETRACTED** (#18 Wakefield 1998, #19 Obokata 2014). |
| A2 | Example button | **NeurIPS 2025 fakes** | Instant (pre-run). 10 refs: 4 verified (Attention, ResNet, BERT, Adam), **2 mismatch** (#2 "John Doe and Jane Smith" on WebVoyager, #5 speculative decoding with invented co-authors), **4 not found** (#3 Kingma & Ba credited for DeepFM, #6 invented title on a real arXiv ID, #8 `arXiv:2305.XXXX`, #9 whitepaper with wrong authors and ID). |
| A2b | Example button | **Retracted papers** | Instant. 5 refs, **3 RETRACTED** stamps: #1 Wakefield 1998, #3 Obokata 2014, #4 Surgisphere/Mehra 2020 (this one is also UNVERIFIED: the best record is a data deposit, not the paper). #2 LeCun and #5 AlphaFold verified. |
| A2c | Example button | **CiteAudit (2026)** | Instant. 33 refs: 24 verified, 9 unverified (GPTZero, Citely, SwanRef, CiteCheck, RefCheck AI, news articles, Playwright). 0 not found. |
| A3 | arXiv tab | `https://arxiv.org/abs/2604.26835` | HalluCiteChecker paper. 18 refs: 16 verified, 2 unverified (#1 "Grobid" software, #2 "Delft", title too short to be sure). |
| A4 | Bibliography tab | paste `01-planted-fakes.txt` | 8 refs: 6 verified, **2 not found**: #3 "Recursive entropy pruning…" and #6 "A unified theory of gradient echo…" (both invented). ~30 s. |
| A5 | Bibliography tab | paste `02-retracted.txt` | 4 refs, all verified, **2 RETRACTED** stamps: #1 Wakefield (Lancet 1998), #2 Obokata (Nature 2014). Open a row to see the retraction notice. ~30 s. |
| A6 | Bibliography tab | paste `03-wrong-details.txt` | 4 refs: 1 verified (#4 ResNet), **3 mismatch**: #1 "year 2009 vs record 2017", #2 "authors differ" (AlphaFold with invented authors), #3 "DOI … belongs to a different work: Adam" (real DOI, fake title). ~1 min. |
| A7 | Bibliography tab | paste `04-software-and-web.txt` | 4 refs: 1 verified (#4 PyTorch), 3 unverified (Python docs, HF docs, Wikipedia). Shows that non-scholarly sources are sent to a human, not called fake. ~1 min. |
| A8 | PDF tab | upload `05-hallucitechecker.pdf` | Title shows the file name. **16 refs** (GROBID finds 16 of the 18 the LaTeX source has): 15 verified, 1 unverified (rapidfuzz software release). ~1 min. |
| A9 | arXiv tab | `1706.03762` (Attention Is All You Need), **not pre-run** | Watch it stream live: stage line, progress bar, rows appearing one by one, then the page switches to "Needs attention" if anything was flagged. Expect mostly verified. If arXiv is busy it can take a few minutes. |

On every finished report also try: the five stamp boxes (filter), **Needs attention / All references**, clicking a row
(evidence card: cited text, best record, field scores, issues), and **JSON ↓ / CSV ↓** downloads.

## B. Errors and edge cases

| # | Where | Input | Expect |
|---|---|---|---|
| B1 | arXiv tab | `hello` | Red message under the form at once: "'hello' is not an arXiv ID (expected e.g. 2602.23452 …)". |
| B2 | arXiv tab | `2501.99999` (valid format, no such paper) | Report page opens, then "Check failed — arXiv has no paper with this ID" (can take ~1.5 min while arXiv retries). |
| B3 | Bibliography tab | type `abc` | **Check citations** stays disabled (needs > 20 characters). |
| B4 | PDF tab | upload `06-not-a-pdf.pdf` | Red message: "not a PDF file". |
| B5 | Browser | open http://localhost:3000/report/abc123 | "EXPIRED · This report is no longer on the server" with New check / demo buttons. |
| B6 | Stop the API, then submit anything | | Red message: "Can't reach the Vouch API. Is the backend running?" |
| B7 | Reload a report page while it is still running | | It rebuilds the same rows and keeps streaming. |
| B8 | Restart the API, then open an old report link | | Expired page (jobs live in memory); running the same input again is instant (report cache). |

`05-hallucitechecker.pdf` is not committed (arXiv licence); download it with
`curl -L -o test-inputs/05-hallucitechecker.pdf https://arxiv.org/pdf/2604.26835`.
