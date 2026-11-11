# Unstop submission text (Round 1)

Copy each block into the matching Unstop field. Numbers are from `EXPERIMENTS.md` / `eval/results/`; do not round them up.

---

**Project name**
Vouch — every citation, vouched for

**Track**
DeepTech & Scientific Computing

**Problem statement**
AI writing tools produce references that look real but are not, and peer review is not catching them: papers citing non-existent references rose from 1 in 2,828 (2023) to 1 in 277 (early 2026), and 100 fabricated citations were confirmed in accepted NeurIPS 2025 papers. Existing open checkers look a reference up in a single database, so they miss about half of the fakes and wrongly flag real books, reports and datasets they cannot find. Retractions, citations that do not support the claim, and paper-mill text are checked by separate tools, if at all.

**Proposed solution**
Vouch is an open research-integrity screener. Paste an arXiv ID, upload a PDF or paste a reference list. For every reference Vouch checks (1) that the work exists, across six open scholarly indexes, (2) that its title, authors, year, venue and DOI match the record, (3) that it was not retracted (Retraction Watch), and (4) whether the cited abstract supports the citing sentence; it also scans the paper for (5) paper-mill "tortured phrases". Every verdict comes with its evidence: the record found, field-by-field scores, the issue, the retraction notice or the quoted passage. Labels describe evidence (Verified / Mismatch / Not found / Unverified / Retracted), never people.

**Key features**
- Three inputs: arXiv ID (reads the LaTeX source and the sentences that cite each reference), PDF (GROBID), pasted bibliography.
- Six-index lookup cascade: Crossref → OpenAlex → arXiv / DataCite / Open Library → Semantic Scholar, routed by reference type.
- Strict field matching tuned on held-out data; catches invented co-authors, wrong years and a real DOI attached to a fake title.
- Retraction check against 73,718 Retraction Watch notices.
- Claim support with quote grounding and calibrated abstention ("needs a human").
- Tortured-phrase scan (86 fingerprints).
- Live report streamed reference by reference, evidence drawer, JSON/CSV export; instant example papers.
- Research page with every result, chart and limitation.

**Technology stack**
Python 3.12, FastAPI, httpx (async), Server-Sent Events, SQLite cache, GROBID 0.9.1, rapidfuzz; LLM deepseek-v4.1-flash on Vultr Serverless Inference (OpenAI-compatible); Next.js 16, React 19, Tailwind CSS 4; Docker Compose + Caddy on a Vultr VM; Vercel. Data: Crossref, OpenAlex, Semantic Scholar, arXiv, DataCite, Open Library APIs, Retraction Watch.

**Source code / repository**
https://github.com/Priyanshu-byte-coder/vouch

**Working prototype / demonstration**
https://vouch-theta-one.vercel.app (try the "NeurIPS 2025 fakes" and "Retracted papers" examples) · research results: https://vouch-theta-one.vercel.app/research · demo video: https://youtu.be/OhIqgDQpIck

**Brief explanation of the implementation**
References are read from the arXiv LaTeX source (.bib/.bbl and the sentences that cite them), from a PDF via GROBID's full-text model, or from a pasted list; an LLM parses the fields, while DOIs and arXiv IDs are taken from the raw text only. Each reference goes through the index cascade, which stops at the first confident match. Every candidate is scored field by field (strict length-aware title similarity, author matching that handles initials, et al. and diacritics, venue abbreviations, year tolerance), and a verdict is made with thresholds tuned by 5-fold cross-validation under a 10% false-alarm cap. Identified works are looked up in Retraction Watch and, when citing sentences exist, compared with their abstract by the LLM, which must quote evidence that is checked against the abstract and abstains below a confidence threshold set on SciFact. The full text is scanned for tortured phrases. Results stream to the browser over Server-Sent Events; lookups and reports are cached.

**Datasets and external resources**
CiteAudit benchmark (9,442 citations; tuning split with test duplicates removed), CiteAudit-300 and NeurIPS-2025 hallucinated citations (AtomGPT detector repo, Apache-2.0, plus its released outputs as the baseline), SciFact (claim support), a CoverageSet of 225 real works sampled from OpenAlex by type and region, Retraction Watch (Crossref), tortured-phrase fingerprints (Cabanac et al. 2021; Zenodo 14753785), and the Crossref, OpenAlex, Semantic Scholar, arXiv, DataCite and Open Library APIs.

**Results / evaluation**
On CiteAudit-300, the published baseline's own benchmark: F1 0.792 [95% CI 0.74–0.84] vs 0.612 for the AtomGPT detector, recall 0.747 vs 0.493, precision 0.842 vs 0.804; paired on the same citations 44 vs 8 cases only one system got right (McNemar p = 4×10⁻⁷). False-positive rate 0.140 vs 0.121 (not lower; intervals overlap). NeurIPS 2025 confirmed fakes: 99/100 flagged vs 94/100. Ablations: adding indexes cuts real references wrongly flagged from 55% (Crossref only) to 6%; title-only matching scores F1 0.61, strict field matching 0.87; an LLM judge for borderline matches made results worse and was switched off. Claim support on SciFact: macro-F1 0.843, accuracy 0.850 → 0.908 when abstaining on the least-confident 20%. False accusations (225 real works by type and region): a single-index checker flags 70% of real datasets, 36% of book chapters and 5% of articles; the regional gap we expected was not found. Audit of 30 recent arXiv papers (1,910 references): 9 confirmed citation problems in 5 papers, including references with invented co-authors; flag precision on real papers is 15%, because real problems are rare (≈0.5%), and the main false-alarm causes are documented. Tuning used dev data only; the test sets were used twice and both runs are reported. Full log: EXPERIMENTS.md.
