"""Command-line entry point.

    python -m app.cli check --bib refs.txt [--out report.json] [--no-s2]
"""

import argparse
import asyncio
import sys
from pathlib import Path

from .pipeline.resolvers import SOURCES
from .pipeline.run import check_arxiv, check_bibliography

ICON = {"verified": "✅", "detail_mismatch": "🟠", "not_found": "🔴", "cant_verify": "⚪"}


def print_report(report) -> None:
    if report.paper.title:
        print(f"Paper: {report.paper.title} ({report.paper.source})")
    for n in report.meta.notes:
        print(f"Note: {n}")
    for r in report.references:
        title = r.parsed.title or r.raw[:70]
        flag = " 🚫" if r.retraction and r.retraction.nature == "Retraction" else " ⚠️" if r.retraction else ""
        print(f"{ICON[r.status.value]}{flag} [{r.idx + 1:>2}] {r.status.value:15s} {title[:72]}")
        if r.match and r.status.value != "verified":
            print(f"        closest: {r.match.source}: {r.match.title[:70]} ({r.match.year})")
        for issue in r.issues:
            print(f"        · {issue[:130]}")
        if r.parsed.contexts and r.status.value != "verified":
            print(f"        cited as: \"{r.parsed.contexts[0][:110]}\"")
    s, m = report.summary, report.meta
    print(f"\n{len(report.references)} references: {s.verified} verified · {s.detail_mismatch} detail mismatch · "
          f"{s.not_found} not found · {s.cant_verify} can't verify · {s.retracted} retracted")
    print(f"{m.seconds}s · LLM {m.llm_calls} calls, ${m.cost_usd:.4f} · API {m.api_calls} · cache hits {m.cache_hits}")


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="vouch")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check a bibliography")
    src = c.add_mutually_exclusive_group(required=True)
    src.add_argument("--bib", type=Path, help="text file with one reference per entry")
    src.add_argument("--arxiv", help="arXiv ID or URL, e.g. 1706.03762")
    c.add_argument("--out", type=Path, help="write the JSON report here")
    c.add_argument("--no-s2", action="store_true", help="skip Semantic Scholar (rate-limited)")
    args = p.parse_args(argv)

    sources = [s for s in SOURCES if not (args.no_s2 and s == "s2")]
    if args.arxiv:
        report = asyncio.run(check_arxiv(args.arxiv, sources=sources))
    else:
        report = asyncio.run(check_bibliography(args.bib.read_text(encoding="utf-8"), sources=sources,
                                                source_label=f"bibliography:{args.bib.name}"))
    print_report(report)
    if args.out:
        args.out.write_text(report.model_dump_json(indent=1), encoding="utf-8")
        print(f"report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
