"""Shared helpers for evaluation scripts: dataset loading and split handling.

Split files in eval/data/splits/ store only indices and hashes (CiteAudit has no licence,
so citation text is never committed). Text is joined back from eval/data/raw/ at load time.
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path

EVAL = Path(__file__).resolve().parent
RAW = EVAL / "data" / "raw"
SPLITS = EVAL / "data" / "splits"

SOURCES = {
    "citeaudit": RAW / "citeaudit" / "benchmark.json",
    "citeaudit300": RAW / "atomgpt" / "data" / "citeaudit_300.json",
    "neurips100": RAW / "atomgpt" / "data" / "neurips2025_hallucinated.json",
}


def load_records(source: str) -> list[dict]:
    data = json.loads(SOURCES[source].read_text(encoding="utf-8"))
    return data["data"] if isinstance(data, dict) and "data" in data else data


def normalize_citation(text: str) -> str:
    """Lowercase, strip accents/punctuation and collapse whitespace, for duplicate detection."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def citation_hash(text: str) -> str:
    return hashlib.sha1(normalize_citation(text).encode()).hexdigest()[:16]


def load_split(name: str) -> list[dict]:
    """Return records of a split: each has citation, GT (True = real), source_type, plus split metadata."""
    spec = json.loads((SPLITS / f"{name}.json").read_text(encoding="utf-8"))
    rows = load_records(spec["source"])
    out = []
    for item in spec["items"]:
        rec = rows[item["index"]]
        if citation_hash(rec["citation"]) != item["hash"]:
            raise ValueError(f"{name}: hash mismatch at index {item['index']}; raw data changed, re-run make_splits.py")
        out.append({"split": name, "index": item["index"], "hash": item["hash"], "citation": rec["citation"],
                    "GT": rec["GT"], "source_type": rec.get("source_type")})
    return out
