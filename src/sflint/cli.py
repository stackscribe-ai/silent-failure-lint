from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .checks import check_source

FOOTER = (
    "\nWant the full write-up of each pattern (with fixes, tested code, and "
    "the pool-exhaustion + retry-storm case studies)? -> "
    "https://stackscribe-paywall.stackscribe-paywall-worker.workers.dev/"
)


def iter_python_files(paths: list[str]):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            yield from sorted(p.rglob("*.py"))
        elif p.suffix == ".py":
            yield p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sflint",
        description="Flag silently-swallowed async/IO failures in Python code "
        "(bare excepts, fire-and-forget tasks, gather() without "
        "return_exceptions, missing HTTP timeouts, retry loops without backoff).",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to scan")
    parser.add_argument(
        "--no-footer", action="store_true", help="Suppress the closing promo line"
    )
    args = parser.parse_args(argv)

    total = 0
    for path in iter_python_files(args.paths):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"{path}: skipped ({exc})", file=sys.stderr)
            continue
        try:
            findings = check_source(source)
        except SyntaxError as exc:
            print(f"{path}: skipped (syntax error: {exc})", file=sys.stderr)
            continue
        for finding in findings:
            total += 1
            print(f"{path}:{finding.line}:{finding.col}: {finding.rule} {finding.message}")

    if total:
        print(f"\n{total} finding(s).")
        if not args.no_footer:
            print(FOOTER)
        return 1

    print("No silent-failure patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
