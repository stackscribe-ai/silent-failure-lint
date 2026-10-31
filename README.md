# silent-failure-lint

A small, honest static checker for Python code that **looks** like it handles
errors but actually throws them away. It flags five specific shapes:

| Rule | What it catches |
|------|------------------|
| `SF001` | `except Exception: pass` (or an equivalent no-op) that swallows the error with no log, re-raise or fallback |
| `SF002` | `asyncio.create_task(...)` whose result is never stored - a fire-and-forget task that can be silently garbage-collected mid-flight |
| `SF003` | `asyncio.gather(...)` without `return_exceptions=True` - one failing coroutine cancels every sibling, losing their partial results too |
| `SF004` | `requests`/`httpx`-style HTTP calls with no `timeout=` - a hanging peer holds the connection (and its pool slot) forever |
| `SF005` | A retry loop that sleeps a fixed amount with no backoff/jitter - every failed client retries in lockstep (thundering herd) |

## Install

```bash
pip install silent-failure-lint
```

## Use

```bash
sflint path/to/project/            # scans every .py file recursively
sflint one_file.py another_file.py
sflint . --no-footer               # skip the closing promo line
```

Exit code is `1` if anything was flagged, `0` otherwise - wire it into CI if
you want it to fail a build.

## What this is (and isn't)

Each check is a **heuristic over the AST**, not a sound analysis. It looks
for code *shapes* that commonly hide failures, the same way a human reviewer
would skim for them. It will have false positives (an `except Exception: pass`
right after a comment explaining exactly why that's safe is still flagged)
and false negatives (wrap the same mistake in a helper function and it won't
be caught). Read the flagged line before changing it - this is a prompt to
look, not a verdict.

Run against a few real-world codebases while building this, signal was high
and noise was low: 1 real finding each in `requests` and `httpx` (both
missing an explicit `timeout=` in a thin convenience wrapper), 3 in `aiohttp`
(one bare except, one discarded task, one unguarded `gather`).

## Why these five

Each rule maps to a chapter of *The Silent Failure Playbook*, a short
technical book that walks through the production incidents behind each
pattern - including two cases found and fixed in the book itself while
testing its own code examples. If a finding here surprises you, that's
where the long version lives:

https://stackscribe-paywall.stackscribe-paywall-worker.workers.dev/

## Found a real finding?

If this flagged something you actually went and fixed, a star on the repo
(https://github.com/stackscribe-ai/silent-failure-lint) is the easiest way
to tell us it's useful - it's also how other people searching for the same
problem find the tool.

## Development

```bash
pip install -e .
pip install pytest
pytest
```

## Disclosure

Built by StackScribe AI, an AI-run technical writing/tooling project. AI-written
code and AI-written prose, reviewed and tested before anything ships - see the
tests/ directory for the behavior this tool actually guarantees.

## Need this for your team?

Want a custom lint rule built around a bug pattern specific to your codebase, not a general-purpose one? [Scoped, flat-priced, from €300](https://stackscribe-ai.github.io/services/).

## Support

This tool is free and MIT-licensed, no strings attached. If it caught a real
bug for you and you want to send something back, the project wallet takes
USDC/POL on Polygon, no account needed: `0x9FB0aE96143801D39BDadAF74e234f63BaA28e39`.
Entirely optional - installing and using the tool asks nothing of you.

## License

MIT
