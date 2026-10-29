"""AST-based checks for silently-swallowed failures in async/IO Python code.

Each check is a best-effort heuristic, not a sound analysis: it flags code
*shapes* that commonly hide errors (see README for the reasoning behind each
rule). False positives are possible; read the flagged line before changing it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    col: int
    message: str


_HTTP_CALL_ATTRS = {
    "get", "post", "put", "patch", "delete", "head", "options", "request",
}
_HTTP_CALLEE_ROOTS = {"requests", "httpx", "session", "client"}


def _is_noop_body(body: list[ast.stmt]) -> bool:
    if len(body) != 1:
        return False
    stmt = body[0]
    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        return True  # a lone docstring/comment-as-string, still a no-op
    if isinstance(stmt, ast.Continue):
        return True
    return False


def check_silent_except(tree: ast.AST) -> list[Finding]:
    """except: / except Exception: whose body does nothing and never re-raises."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}
        )
        if is_broad and _is_noop_body(node.body):
            findings.append(
                Finding(
                    "SF001",
                    node.lineno,
                    node.col_offset,
                    "bare except swallows the error with no log, re-raise or fallback "
                    "- the failure disappears silently",
                )
            )
    return findings


def check_fire_and_forget_task(tree: ast.AST) -> list[Finding]:
    """asyncio.create_task(...) result that is never assigned/awaited/stored."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr):
            continue
        call = node.value
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        is_create_task = (
            isinstance(func, ast.Attribute)
            and func.attr == "create_task"
        ) or (isinstance(func, ast.Name) and func.id == "create_task")
        if is_create_task:
            findings.append(
                Finding(
                    "SF002",
                    node.lineno,
                    node.col_offset,
                    "create_task() result is discarded - if nothing holds a reference, "
                    "the task can be garbage-collected mid-flight and any exception "
                    "it raises is only logged by asyncio's default handler, if at all",
                )
            )
    return findings


def check_gather_without_return_exceptions(tree: ast.AST) -> list[Finding]:
    """asyncio.gather(...) without return_exceptions=True."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_gather = (isinstance(func, ast.Attribute) and func.attr == "gather") or (
            isinstance(func, ast.Name) and func.id == "gather"
        )
        if not is_gather:
            continue
        has_return_exceptions = any(kw.arg == "return_exceptions" for kw in node.keywords)
        if not has_return_exceptions:
            findings.append(
                Finding(
                    "SF003",
                    node.lineno,
                    node.col_offset,
                    "gather() without return_exceptions=True cancels every other "
                    "still-running task the instant one coroutine raises - partial "
                    "results are lost, not just the failed one",
                )
            )
    return findings


def check_missing_timeout(tree: ast.AST) -> list[Finding]:
    """requests/httpx-style HTTP calls with no timeout= kwarg."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in _HTTP_CALL_ATTRS:
            continue
        root = func.value
        root_name = root.id if isinstance(root, ast.Name) else getattr(root, "attr", None)
        if root_name not in _HTTP_CALLEE_ROOTS:
            continue
        has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
        if not has_timeout:
            findings.append(
                Finding(
                    "SF004",
                    node.lineno,
                    node.col_offset,
                    "HTTP call has no timeout - a hanging peer holds this connection "
                    "(and its slot in the pool) forever instead of failing loudly",
                )
            )
    return findings


def check_retry_without_backoff(tree: ast.AST) -> list[Finding]:
    """A try/except inside a loop that sleeps a fixed amount with no jitter/backoff."""
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
        if not has_try:
            continue
        for n in ast.walk(node):
            if not isinstance(n, ast.Call):
                continue
            func = n.func
            is_sleep = (isinstance(func, ast.Attribute) and func.attr == "sleep") or (
                isinstance(func, ast.Name) and func.id == "sleep"
            )
            if not is_sleep or not n.args:
                continue
            arg = n.args[0]
            is_constant_delay = isinstance(arg, ast.Constant) and isinstance(
                arg.value, (int, float)
            )
            if is_constant_delay:
                findings.append(
                    Finding(
                        "SF005",
                        n.lineno,
                        n.col_offset,
                        "retry loop sleeps a fixed amount with no backoff/jitter - "
                        "every failed client retries in lockstep and re-floods the "
                        "service at the same instant (thundering herd)",
                    )
                )
    return findings


ALL_CHECKS = (
    check_silent_except,
    check_fire_and_forget_task,
    check_gather_without_return_exceptions,
    check_missing_timeout,
    check_retry_without_backoff,
)


def check_source(source: str) -> list[Finding]:
    tree = ast.parse(source)
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(tree))
    return sorted(findings, key=lambda f: (f.line, f.col))
