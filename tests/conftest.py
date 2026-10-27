"""Test setup: every test runs offline (a scripted fake model, never the API), with logs in a temporary folder and a
freshly generated synthetic bookings database."""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))  # tests/fakes.py

# A fake key shaped like a real one: logs must never contain it (tests/test_service.py checks).
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-0000000000000000"
os.environ.setdefault("PRICE_IN_PER_M", "0.10")
os.environ.setdefault("PRICE_OUT_PER_M", "0.50")


@pytest.fixture(scope="session", autouse=True)
def policy_index():
    """Build the keyword-only policy index once, so tests are fast."""
    from src.policy.ingest import build_index

    build_index(use_embeddings=False)


@pytest.fixture(autouse=True)
def isolated_logs(tmp_path, monkeypatch):
    import src.config
    import src.errors
    import src.usage

    log_dir = tmp_path / "logs"
    monkeypatch.setattr(src.config, "LOG_DIR", log_dir)
    monkeypatch.setattr(src.usage, "LOG_DIR", log_dir)
    monkeypatch.setattr(src.errors, "ERRORS_FILE", log_dir / "errors.jsonl")
    return log_dir


@pytest.fixture(scope="session")
def store(tmp_path_factory):
    from src.bookings import BookingStore, ensure_db

    path = tmp_path_factory.mktemp("db") / "bookings.sqlite"
    ensure_db(path)
    return BookingStore(path)


@pytest.fixture(autouse=True)
def no_live_settings(monkeypatch):
    """A developer's .env may hold the live DATABASE_URL (Neon) and passwords: tests never use them. Tests that need a
    database set their own (tests/test_store.py)."""
    from src import store

    for name in ("DATABASE_URL", "STAFF_PASSWORD", "KILL_SWITCH"):
        monkeypatch.delenv(name, raising=False)
    store.reset_connection()
    yield
    store.reset_connection()


@pytest.fixture(autouse=True)
def fresh_gate_counters():
    """The Admin/staff lockout also counts per process (hotel-ai-platform admin_gate): reset it between tests."""
    from hotelplatform import admin_gate

    admin_gate.reset_process_counters()
    yield
    admin_gate.reset_process_counters()


@pytest.fixture(autouse=True)
def ops_log_in_tmp(tmp_path, monkeypatch):
    """The shared ops store writes JSONL files without DATABASE_URL; tests write to a temp folder instead."""
    from hotelplatform import oplog

    from src import ops

    store = oplog.OpsStore("guest-request-agent", url="", log_dir=tmp_path / "ops")
    monkeypatch.setattr(ops, "store", lambda: store)
    yield store
