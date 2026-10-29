from sflint.checks import check_source


def rules(source: str) -> list[str]:
    return [f.rule for f in check_source(source)]


def test_bare_except_pass_flagged():
    src = """
try:
    do_thing()
except Exception:
    pass
"""
    assert "SF001" in rules(src)


def test_except_with_logging_not_flagged():
    src = """
try:
    do_thing()
except Exception:
    log.exception("failed")
    raise
"""
    assert "SF001" not in rules(src)


def test_except_with_specific_type_not_flagged():
    src = """
try:
    do_thing()
except KeyError:
    pass
"""
    assert "SF001" not in rules(src)


def test_fire_and_forget_task_flagged():
    src = """
import asyncio

async def main():
    asyncio.create_task(worker())
"""
    assert "SF002" in rules(src)


def test_assigned_task_not_flagged():
    src = """
import asyncio

async def main():
    task = asyncio.create_task(worker())
    background_tasks.add(task)
"""
    assert "SF002" not in rules(src)


def test_gather_without_return_exceptions_flagged():
    src = """
import asyncio

async def main():
    await asyncio.gather(fetch(1), fetch(2))
"""
    assert "SF003" in rules(src)


def test_gather_with_return_exceptions_not_flagged():
    src = """
import asyncio

async def main():
    await asyncio.gather(fetch(1), fetch(2), return_exceptions=True)
"""
    assert "SF003" not in rules(src)


def test_missing_timeout_flagged():
    src = """
import requests

def call():
    return requests.get("https://example.com")
"""
    assert "SF004" in rules(src)


def test_timeout_present_not_flagged():
    src = """
import requests

def call():
    return requests.get("https://example.com", timeout=5)
"""
    assert "SF004" not in rules(src)


def test_retry_without_backoff_flagged():
    src = """
import time

def call():
    for attempt in range(3):
        try:
            return do_thing()
        except Exception:
            time.sleep(1)
"""
    assert "SF005" in rules(src)


def test_retry_with_computed_backoff_not_flagged():
    src = """
import time

def call():
    for attempt in range(3):
        try:
            return do_thing()
        except Exception:
            time.sleep(backoff_with_jitter(attempt))
"""
    assert "SF005" not in rules(src)


def test_clean_file_has_no_findings():
    src = """
import asyncio
import requests


async def main():
    task = asyncio.create_task(worker())
    try:
        requests.get("https://example.com", timeout=5)
        await asyncio.gather(fetch(1), fetch(2), return_exceptions=True)
    except ValueError:
        raise
    return task
"""
    assert rules(src) == []
