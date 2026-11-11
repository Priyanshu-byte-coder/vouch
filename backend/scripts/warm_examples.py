"""Pre-run the website's example checks so the "Try an example" buttons load instantly (step 4.3).

The examples live in frontend/src/lib/examples.json (one list for the website and this script). Each example
is sent to the API exactly as the website sends it, so the finished report lands in the API's report cache.
Run it after every deploy and after bumping REPORT_VERSION.

    cd backend && .venv/Scripts/python scripts/warm_examples.py [--api http://localhost:8000] [--refresh]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

EXAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "examples.json"


def wait(c: httpx.Client, api: str, job_id: str, timeout: float = 900) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = c.get(f"{api}/api/jobs/{job_id}").json()
        if d["status"] in ("done", "error"):
            return d
        time.sleep(2)
    raise TimeoutError(job_id)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--refresh", action="store_true", help="ignore cached reports and recompute")
    args = ap.parse_args()
    api = args.api.rstrip("/")

    failed = 0
    with httpx.Client(timeout=60) as c:
        for ex in json.loads(EXAMPLES.read_text(encoding="utf-8")):
            if ex["kind"] == "demo":
                continue
            body = {"arxiv_id": ex["value"]} if ex["kind"] == "arxiv" else {"bibliography": ex["value"]}
            if args.refresh:
                body["refresh"] = True
            t0 = time.time()
            r = c.post(f"{api}/api/check", json=body)
            if r.status_code != 200:
                print(f"✗ {ex['label']}: HTTP {r.status_code} {r.text}")
                failed += 1
                continue
            d = wait(c, api, r.json()["job_id"])
            if d["status"] == "error":
                print(f"✗ {ex['label']}: {d['error']}")
                failed += 1
                continue
            rep = d["report"]
            counts = {k: v for k, v in rep["summary"].items() if v}
            print(f"✓ {ex['label']}: {len(rep['references'])} refs in {time.time() - t0:.1f}s · {counts}")
            for x in rep["references"]:
                if x["status"] != "verified" or x["retraction"]:
                    ret = f" [{x['retraction']['nature']}]" if x["retraction"] else ""
                    issue = f" — {x['issues'][0][:90]}" if x["issues"] and x["status"] != "verified" else ""
                    print(f"    {x['idx'] + 1:>2} {x['status']}{ret}: {(x['parsed']['title'] or x['raw'])[:60]}{issue}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
