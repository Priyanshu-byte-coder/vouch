# Vouch demo video: voice-over script

Video: `video/out/vouch_demo_captions.mp4` (captions burned in, read along) and `vouch_demo_clean.mp4` (same video, no captions), 1920×1080, 30 fps, 4:51.9 long, silent audio track for your voice-over. Captions as subtitles: `video/out/captions.srt`.

Read each line when it appears. Pace: calm, about 140 words a minute; every line has room for a short pause.

| Start | End | Scene | Say |
|---|---|---|---|
| 0:00.3 | 0:06.3 | title | Hello judges! We are Team Beyonders, and this is our project: Vouch. |
| 0:06.3 | 0:09.5 | title | Every citation, vouched for. |
| 0:10.6 | 0:17.9 | problem | Science runs on citations. But AI writing tools now invent references that look completely real. |
| 0:17.9 | 0:26.9 | problem | Papers citing references that don't exist went from one in 2,828 in 2023, to one in 277 this year. |
| 0:26.9 | 0:35.9 | problem | And 100 fabricated citations were found inside papers accepted at NeurIPS 2025, one of the world's top AI conferences. |
| 0:37.0 | 0:41.3 | gap | Today's open checkers look in a single database. |
| 0:41.3 | 0:49.8 | gap | The published AtomGPT detector uses only Semantic Scholar. On its own benchmark, it misses half of the fakes, |
| 0:49.8 | 0:57.5 | gap | and it wrongly accuses real datasets, book chapters and reports that its one database doesn't hold. |
| 0:58.6 | 1:02.9 | solution | So we built Vouch: an open research-integrity screener. |
| 1:02.9 | 1:11.5 | solution | Give it an arXiv ID, a PDF, or a reference list. For every reference, Vouch asks five questions. |
| 1:11.5 | 1:22.2 | solution | Does it exist? Are its details right? Was it retracted? Does it support the claim? And is the paper free of paper-mill language? |
| 1:22.2 | 1:28.2 | solution | Every verdict comes with its evidence. The labels describe evidence, never people. |
| 1:29.3 | 1:37.4 | how | Vouch searches six open scholarly indexes in turn: Crossref, OpenAlex, arXiv, DataCite, Open Library and Semantic Scholar. |
| 1:37.4 | 1:45.6 | how | It compares title, authors, year, venue and DOI field by field, and checks 73,718 Retraction Watch notices. |
| 1:45.6 | 1:55.0 | how | An open language model, served on Vultr, reads each citing sentence against the cited abstract, and must quote its evidence. |
| 1:56.1 | 2:05.1 | demo | Let's see it live. This example mixes six fake citations from accepted NeurIPS 2025 papers with four real ones. |
| 2:05.1 | 2:12.0 | demo | In seconds, all six fakes are flagged, and all four real references are verified. |
| 2:12.0 | 2:23.5 | demo | Here, a real paper, WebVoyager, was cited with invented authors: John Doe and Jane Smith. Vouch shows the real record, and exactly which field disagrees. |
| 2:23.5 | 2:32.5 | demo | And here, Kingma and Ba, the authors of the Adam optimizer, are credited with a paper they never wrote. |
| 2:32.5 | 2:42.2 | demo | Vouch also catches retracted work, like the Wakefield vaccine paper and the Surgisphere COVID study, with the official retraction notice. |
| 2:42.2 | 2:50.6 | demo | Upload a PDF, and Vouch reads the full text too, looking for paper-mill phrases. |
| 2:50.6 | 3:00.4 | demo | Here: 'counterfeit consciousness' instead of 'artificial intelligence', and 'irregular woodland' for 'random forest'. A reason to read closer, never an accusation. |
| 3:01.3 | 3:08.2 | results | Now, the research. We evaluated on CiteAudit-300: the exact benchmark the baseline published on. |
| 3:08.2 | 3:16.3 | results | Vouch reaches an F1 of 0.79 against 0.61, and catches 75 percent of the fakes, against 49. |
| 3:16.3 | 3:30.8 | results | Head to head on the same citations, Vouch is right 44 times where the baseline is wrong, and only 8 times the other way: significant at p below one in a million. |
| 3:30.8 | 3:36.8 | results | And on the 100 real fakes from NeurIPS 2025, Vouch flags 99. |
| 3:37.9 | 3:46.9 | why | Our ablations show why it works. Adding indexes cuts false alarms on real references from 55 percent to 6. |
| 3:46.9 | 3:54.6 | why | Strict field matching is what catches the fakes: title-only matching is no better than the baseline. |
| 3:54.6 | 4:01.9 | why | And an AI judge for borderline cases made things worse, so cross-validation switched it off. |
| 4:03.0 | 4:12.0 | claims | For claim support, we tested on SciFact: 0.84 macro-F1, and 0.91 accuracy when the model may say 'not sure'. |
| 4:12.0 | 4:22.2 | claims | We also measured who gets wrongly accused: a single-database checker flags 70 percent of real datasets, but only 5 percent of articles. |
| 4:23.3 | 4:33.2 | rigor | And everything is reproducible: we tuned only on separate data, report every test run, and publish our negative results and limitations. |
| 4:34.3 | 4:45.0 | close | Vouch is open source, live today, and costs less than a tenth of a cent per reference: for authors, reviewers and conference chairs. |
| 4:45.0 | 4:50.1 | close | Thank you! We are Team Beyonders, and this was Vouch. |
