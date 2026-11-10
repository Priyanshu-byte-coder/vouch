"""The frozen configuration tuned on the dev split (step 3.1). Used by the app and the test evaluation."""

import json
from pathlib import Path

from .match import WEIGHTS
from .verdict import DEFAULT, Thresholds

_PATH = Path(__file__).with_name("tuned.json")


def _load() -> tuple[dict[str, float], Thresholds, dict]:
    if not _PATH.exists():
        return WEIGHTS, DEFAULT, {}
    cfg = json.loads(_PATH.read_text(encoding="utf-8"))
    return cfg["weights"], Thresholds(**cfg["thresholds"]), cfg


TUNED_WEIGHTS, TUNED_THRESHOLDS, TUNED_INFO = _load()
