"""Download every dataset Vouch is evaluated on into eval/data/raw/ (gitignored).

Run from the repo root:
    backend/.venv/Scripts/python eval/data/download.py

Licences and citations: see eval/data/SOURCES.md. Raw files are never committed.
"""

import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import httpx
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

RAW = Path(__file__).resolve().parent / "raw"
GH = "https://raw.githubusercontent.com"
ATOMGPT = f"{GH}/atomgptlab/hallucination_detector/main"

FILES = {
    # name: (url, local path)
    "citeaudit": (f"{GH}/shiiiikw/CiteAudit/main/data/benchmark.json", "citeaudit/benchmark.json"),
    "atomgpt_citeaudit_300": (f"{ATOMGPT}/data/citeaudit_300.json", "atomgpt/data/citeaudit_300.json"),
    "atomgpt_neurips2025": (f"{ATOMGPT}/data/neurips2025_hallucinated.json", "atomgpt/data/neurips2025_hallucinated.json"),
    "atomgpt_results_citeaudit_300": (f"{ATOMGPT}/results/citeaudit_300_v2.json", "atomgpt/results/citeaudit_300_v2.json"),
    "atomgpt_results_neurips2025": (f"{ATOMGPT}/results/neurips2025_v1.json", "atomgpt/results/neurips2025_v1.json"),
    "scifact": ("https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz", "scifact/data.tar.gz"),
    "retraction_watch": ("https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv",
                         "retraction_watch/retraction_watch.csv"),
    "tortured_supplmat": ("https://zenodo.org/records/5031935/files/20210712_TorturedPhrases_supplmat.zip?download=1",
                          "tortured/20210712_TorturedPhrases_supplmat.zip"),
    "tortured_social_sciences": ("https://zenodo.org/records/14753785/files/20241114_social_sciences_fingerprints.csv?download=1",
                                 "tortured/social_sciences_fingerprints.csv"),
}


def fetch(client: httpx.Client, url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest.stat().st_size
    with client.stream("GET", url) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)
    return dest.stat().st_size


def records(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["data"] if isinstance(data, dict) and "data" in data else data


def summarize() -> None:
    print("\n=== Contents ===")
    ca = records(RAW / "citeaudit/benchmark.json")
    print(f"CiteAudit benchmark: {len(ca)} records · keys: {sorted(ca[0].keys())}")
    print("   GT:", pd.Series([r.get("GT") for r in ca]).value_counts(dropna=False).to_dict(),
          "· source_type:", pd.Series([r.get("source_type") for r in ca]).value_counts().to_dict())

    c300 = records(RAW / "atomgpt/data/citeaudit_300.json")
    print(f"CiteAudit-300: {len(c300)} records · GT:", pd.Series([r["GT"] for r in c300]).value_counts().to_dict())
    n100 = records(RAW / "atomgpt/data/neurips2025_hallucinated.json")
    print(f"NeurIPS-2025: {len(n100)} records · GT:", pd.Series([r["GT"] for r in n100]).value_counts().to_dict())

    sf_dir = RAW / "scifact"
    if not (sf_dir / "data").exists():
        with tarfile.open(sf_dir / "data.tar.gz") as t:
            t.extractall(sf_dir, filter="data")
    for name in ("corpus.jsonl", "claims_train.jsonl", "claims_dev.jsonl", "claims_test.jsonl"):
        p = sf_dir / "data" / name
        n = sum(1 for _ in open(p, encoding="utf-8")) if p.exists() else "missing"
        print(f"SciFact {name}: {n}")

    rw = pd.read_csv(RAW / "retraction_watch/retraction_watch.csv", encoding="latin-1", low_memory=False)
    print(f"Retraction Watch: {len(rw)} rows · nature:", rw["RetractionNature"].value_counts().head(4).to_dict())

    tz = RAW / "tortured/20210712_TorturedPhrases_supplmat.zip"
    with zipfile.ZipFile(tz) as z:
        names = z.namelist()
    print(f"Tortured supplmat zip: {len(names)} files, e.g. {names[:6]}")
    ss = pd.read_csv(RAW / "tortured/social_sciences_fingerprints.csv")
    print(f"Tortured social-sciences fingerprints: {len(ss)} rows · columns: {list(ss.columns)}")


def main() -> None:
    headers = {"User-Agent": "Vouch/0.1 (research-integrity hackathon project)"}
    with httpx.Client(timeout=120, follow_redirects=True, headers=headers) as client:
        for name, (url, rel) in FILES.items():
            size = fetch(client, url, RAW / rel)
            print(f"[ok] {name:32s} {size / 1e6:8.2f} MB  -> raw/{rel}")
    summarize()


if __name__ == "__main__":
    main()
