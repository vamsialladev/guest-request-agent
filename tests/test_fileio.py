"""Regression tests for the Assistant-page crash: on Windows, a second process holding a log or counter file
open makes os.replace / rewrites fail with PermissionError (reproduced with two processes: ~1 in 10 writes)."""

import json

import pytest

import src.errors as errors
import src.limits as limits
import src.usage as usage
from src.fileio import with_retries
from src.limits import DailyCounter


def flaky(failures: int):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] <= failures:
            raise PermissionError("[WinError 5] Access is denied")
        return "ok"

    return fn, calls


def test_short_collisions_are_retried():
    fn, calls = flaky(3)
    assert with_retries(fn, sleep=lambda s: None) == "ok" and calls["n"] == 4


def test_persistent_failure_is_raised_after_the_retries():
    fn, calls = flaky(100)
    with pytest.raises(PermissionError):
        with_retries(fn, retries=4, sleep=lambda s: None)
    assert calls["n"] == 4


def test_daily_counter_survives_a_locked_file_and_records_the_error(tmp_path, monkeypatch):
    monkeypatch.setattr(errors, "ERRORS_FILE", tmp_path / "errors.jsonl")
    monkeypatch.setattr("src.fileio.time.sleep", lambda s: None)

    def locked(src, dst):
        raise PermissionError("[WinError 5] Access is denied")

    monkeypatch.setattr(limits.os, "replace", locked)
    counter = DailyCounter(tmp_path / "daily.json", limit=5, today=lambda: "2026-10-10")
    assert counter.try_consume() is True  # the visitor isn't blocked and nothing crashes
    record = json.loads((tmp_path / "errors.jsonl").read_text(encoding="utf-8"))
    assert record["page"] == "Daily cap" and record["error"] == "PermissionError"
    assert not list(tmp_path.glob(".daily-*"))  # the temporary file is cleaned up


def test_log_write_failure_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("src.fileio.time.sleep", lambda s: None)
    target = tmp_path / "usage.jsonl"
    original_open = type(target).open

    def locked_open(self, *args, **kwargs):
        if self == target:
            raise PermissionError("[WinError 32] The process cannot access the file")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(type(target), "open", locked_open)
    assert usage.append_jsonl(target, {"a": 1}) is False


def test_locked_log_reads_as_empty_instead_of_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr("src.fileio.time.sleep", lambda s: None)
    target = tmp_path / "usage.jsonl"
    target.write_text('{"a": 1}\n', encoding="utf-8")

    def locked_read(self, *args, **kwargs):
        raise PermissionError("[WinError 32] The process cannot access the file")

    monkeypatch.setattr(type(target), "read_text", locked_read)
    assert usage.read_jsonl(target) == []
