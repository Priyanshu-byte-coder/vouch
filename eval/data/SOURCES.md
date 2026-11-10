# Datasets and external data

`python eval/data/download.py` fetches everything below into `eval/data/raw/`. That folder is gitignored, and **raw data is never committed**.

| Dataset | Size (10 Nov 2026) | Use in Vouch | Licence | Source / citation |
|---|---|---|---|---|
| **CiteAudit benchmark** | 9,442 citations (6,475 real / 2,967 fake; 6,086 generated + 3,356 real-world) | RQ1 **dev split** for tuning (minus the CiteAudit-300 items) | **No licence file** in the repo. Used for evaluation only, not redistributed | [shiiiikw/CiteAudit](https://github.com/shiiiikw/CiteAudit) · CiteAudit, [arXiv:2602.23452](https://arxiv.org/abs/2602.23452) |
| **CiteAudit-300** | 300 (150 real / 150 fake) | RQ1 **test set**, comparable to the published baseline | Apache-2.0 (derived from CiteAudit, so cite it too) | [atomgptlab/hallucination_detector](https://github.com/atomgptlab/hallucination_detector) `data/citeaudit_300.json` |
| **NeurIPS-2025 hallucinated** | 100 confirmed fabrications | RQ1 recall on real-world fakes | Apache-2.0 | same repo, `data/neurips2025_hallucinated.json` (from the GPTZero audit) |
| AtomGPT released outputs | per-citation results | E0: reproduce the baseline's published numbers | Apache-2.0 | same repo, `results/` · Neralla et al., [arXiv:2607.09774](https://arxiv.org/abs/2607.09774) |
| **SciFact** | 5,183 abstracts · 809 train / 300 dev / 300 test claims | RQ4 claim support | CC BY-NC 2.0 | [allenai/scifact](https://github.com/allenai/scifact) · Wadden et al., EMNLP 2020 |
| **Retraction Watch** | 73,718 notices (68,272 retractions · 3,734 expressions of concern · 1,549 corrections · 163 reinstatements) | Check ③ retracted citations | Open, from Crossref ([terms](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)) | [gitlab.com/crossref/retraction-watch-data](https://gitlab.com/crossref/retraction-watch-data) |
| **Tortured phrases** (supplementary material) | 27 files | Check ⑤ fingerprints | CC-BY-4.0 | Cabanac, Labbé & Magazinov 2021, [Zenodo 5031935](https://zenodo.org/records/5031935) |
| **Tortured phrases, social sciences** | 42 fingerprints | Check ⑤ | CC-BY-4.0 | [Zenodo 14753785](https://zenodo.org/records/14753785) |

## Live APIs (queried at run time, responses cached locally)
Crossref REST · OpenAlex (API key) · Semantic Scholar Graph API (API key, 1 req/s) · arXiv API · DataCite REST · Open Library Search · GROBID 0.9.1 (local Docker, `grobid/grobid:0.9.1-crf`).
DBLP was dropped on 10 Nov 2026 because its API now returns an anti-bot challenge page.

## AI models
Vultr Serverless Inference (OpenAI-compatible). Parsing: `deepseek-v4.1-flash-1017` (thinking off). Judging: `deepseek-v4.1-flash-1017` (thinking on), with other models to be compared. See `EXPERIMENTS.md` S0.

## Required attribution
- **Semantic Scholar:** data from the Semantic Scholar Academic Graph API. Cite: Kinney et al., *The Semantic Scholar Open Data Platform*, [arXiv:2301.10140](https://arxiv.org/abs/2301.10140) (2023). This is required by the API licence and has to appear in the README and on the web app.
- **OpenAlex:** Priem, Piwowar & Orr, *OpenAlex: A fully-open index of scholarly works, authors, venues, institutions, and concepts*, [arXiv:2205.01833](https://arxiv.org/abs/2205.01833) (2022).
- **Crossref** metadata and the **Retraction Watch** database (Crossref).
