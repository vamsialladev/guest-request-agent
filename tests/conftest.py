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
