"""Persistent log store and personal-data redaction (Project 4).

SQLite runs everywhere; the same tests run against Postgres when TEST_DATABASE_URL is set (CI starts a Postgres
service container), so the Postgres code path is tested without the live database."""

import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from src import pii, store, usage

PLANTED = {
    "email": "priya.shah@example.com",
    "phone": "(555) 123-4567",
    "card": "4111 1111 1111 1111",
    "booking": "ML-2040",
    "name": "Priya Shah",
}
QUESTION = (
    f"My name is {PLANTED['name']}, booking {PLANTED['booking']}. Email {PLANTED['email']}, phone {PLANTED['phone']}, "
    f"card {PLANTED['card']}. What is the pet fee?"
)


def leaks(text: str) -> list[str]:
    """Planted values (or their pieces) still present in stored text."""
    found = [k for k, v in PLANTED.items() if v.lower() in text.lower()]
    found += [p for p in ("Priya", "Shah", "4111", "123-4567") if p in text]
    return found


def full_record() -> dict:
    """A Project 2 request record shaped like src/service.build_record, with personal data in every free-text field."""
    return {
        "request_id": "r-1",
        "session_id": "s-1",
        "property": "mountain-lodge",
        "outcome": "drafted",
        "email": {
            "from": PLANTED["email"],
            "name": PLANTED["name"],
            "subject": f"Booking {PLANTED['booking']}",
            "body": QUESTION + "\n\nThanks,\nPriya",
        },
        "reply": f"Dear Priya,\n\nYour booking {PLANTED['booking']} is confirmed. We'll call {PLANTED['phone']}.",
        "bookings": [{"booking_id": PLANTED["booking"], "guest_name": PLANTED["name"], "member_number": "GR-99812"}],
        "steps": [{"name": "find_booking", "summary": f"Found booking {PLANTED['booking']} for {PLANTED['name']}"}],
        "error_message": f"card {PLANTED['card']} declined",
        "cost_usd": 0.0013,
    }


@pytest.fixture(params=["sqlite", "postgres"])
def db(request, tmp_path, monkeypatch):
    if request.param == "postgres":
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("TEST_DATABASE_URL not set (CI runs this against a Postgres service)")
    else:
        url = f"sqlite:///{(tmp_path / 'logs.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setattr(store, "APP_NAME", f"test-{os.getpid()}-{tmp_path.name}")
    store.reset_connection()
    store.purge(days=-1)  # a clean slate for this test's app name
    yield url
    store.purge(days=-1)
    store.reset_connection()


def raw_rows(url: str) -> list[str]:
    """What is physically stored, read past the store module."""
    if url.startswith("sqlite"):
        conn = sqlite3.connect(url.removeprefix("sqlite:///"))
        return [r[0] for r in conn.execute("SELECT data FROM app_log WHERE app = ?", (store.APP_NAME,))]
    import psycopg

    with psycopg.connect(url) as conn:
        return [r[0] for r in conn.execute("SELECT data FROM app_log WHERE app = %s", (store.APP_NAME,))]


def test_backend_is_chosen_from_the_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert store.backend() is None and not store.enabled()
    assert store.backend("postgresql://u:p@host/db") == "postgres"
    assert store.backend("postgres://u:p@host/db") == "postgres"
    assert store.backend("sqlite:///x.db") == "sqlite"
    assert store.backend("mysql://x") == "invalid"


def test_not_configured_means_files_exactly_as_before(monkeypatch, isolated_logs):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    usage.log_request({"question": "Is there parking?"})
    assert (isolated_logs / "requests.jsonl").exists()
    assert usage.read_jsonl(isolated_logs / "requests.jsonl")[0]["question"] == "Is there parking?"
    assert store.status()["backend"] == "files" and store.status()["configured"] is False


def test_records_round_trip_through_the_database(db, isolated_logs):
    usage.log_request({"question": "Is there parking?", "request_id": "r-1"})
    usage.log_request({"question": "Pet fee?", "request_id": "r-2"})
    assert not (isolated_logs / "requests.jsonl").exists()  # the database is the log
    rows = usage.read_jsonl(isolated_logs / "requests.jsonl")
    assert [r["request_id"] for r in rows] == ["r-1", "r-2"]
    status = store.status()
    assert status["ok"] and status["counts"] == {"requests": 2} and status["retention_days"] == 30
    assert db not in json.dumps(status)  # never shows the connection string


def test_apps_sharing_one_database_never_see_each_other(db, monkeypatch, isolated_logs):
    usage.log_request({"question": "mine"})
    mine = store.APP_NAME
    monkeypatch.setattr(store, "APP_NAME", mine + "-other")
    assert usage.read_jsonl(isolated_logs / "requests.jsonl") == []
    store.purge(days=-1)
    monkeypatch.setattr(store, "APP_NAME", mine)
    assert len(usage.read_jsonl(isolated_logs / "requests.jsonl")) == 1


def test_retention_deletes_only_records_older_than_the_limit(db):
    old = (datetime.now(UTC) - timedelta(days=31)).isoformat(timespec="seconds")
    recent = (datetime.now(UTC) - timedelta(days=29)).isoformat(timespec="seconds")
    store._STATE["last_purge"] = 1e18  # no automatic purge during the test
    store.save("requests", {"time": old, "request_id": "old"})
    store.save("requests", {"time": recent, "request_id": "recent"})
    assert store.purge(days=30) == 1
    assert [r["request_id"] for r in store.load("requests")] == ["recent"]


def test_purge_runs_at_most_once_a_day(db, monkeypatch):
    calls = []
    monkeypatch.setattr(store, "purge", lambda **_: calls.append(1) or 0)
    store._STATE["last_purge"] = 0.0
    store.maybe_purge(clock=lambda: 100_000.0)
    store.maybe_purge(clock=lambda: 100_000.0 + 3600)
    store.maybe_purge(clock=lambda: 100_000.0 + 25 * 3600)
    assert len(calls) == 2


def test_a_database_failure_falls_back_to_the_file_and_never_raises(db, monkeypatch, isolated_logs):
    def down(*_a, **_k):
        raise ConnectionError("database unreachable")

    monkeypatch.setattr(store, "_run", down)
    assert usage.append_jsonl(isolated_logs / "requests.jsonl", {"question": "Q", "time": "2026-10-15T10:00:00+00:00"})
    assert (isolated_logs / "requests.jsonl").exists()
    assert usage.read_jsonl(isolated_logs / "requests.jsonl")[0]["question"] == "Q"  # read falls back too
    assert store.status()["ok"] is False


@pytest.mark.parametrize("configured", [False, True])
def test_no_personal_data_reaches_storage_in_any_field(configured, db, monkeypatch, isolated_logs):
    if not configured:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    usage.log_request(full_record())
    usage.append_jsonl(isolated_logs / "decisions.jsonl", {"request_id": "r-1", "comment": QUESTION})
    stored = (
        "\n".join(raw_rows(db))
        if configured
        else "\n".join(p.read_text(encoding="utf-8") for p in isolated_logs.glob("*.jsonl"))
    )
    assert stored and leaks(stored) == []
    assert pii.booking_pseudonym(PLANTED["booking"]) in stored  # hashed, not dropped: same booking, same pseudonym


def test_the_leak_check_fails_when_redaction_is_switched_off(db, monkeypatch, isolated_logs):
    monkeypatch.setattr(pii, "redact_record", lambda r: r)
    usage.log_request(full_record())
    assert set(leaks("\n".join(raw_rows(db)))) >= {"email", "phone", "card", "booking", "name"}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Call +1 555 987 6543 please", "Call [phone] please"),
        ("Gracias,\nLucía Romero", "Gracias,\n[name]"),
        ("Hola,\n\nLlegamos el viernes.", "Hola,\n\nLlegamos el viernes."),  # a greeting line is not a name
        (
            "Pool 7:00 AM to 10:00 PM, $45, 2026-11-20, cost 0.00019769",
            "Pool 7:00 AM to 10:00 PM, $45, 2026-11-20, cost 0.00019769",
        ),
        ("I am Gold member", "I am Gold member"),
        ("Guest Services, Beach Resort", "Guest Services, Beach Resort"),
    ],
)
def test_scrub_text_keeps_hotel_facts(text, expected):
    assert pii.scrub_text(text) == expected


def test_whole_personal_fields_are_replaced_and_ids_are_kept():
    out = pii.redact_record(
        {"sender": "a@b.com", "sender_name": "Nina Ross", "body": "Nina here", "request_id": "r-9", "property": "x"}
    )
    assert out == {
        "sender": "[email]",
        "sender_name": "[name]",
        "body": "[name] here",
        "request_id": "r-9",
        "property": "x",
    }


def test_privacy_page_wording_matches_where_logs_live(monkeypatch, tmp_path):
    from views.components import privacy_storage_line

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert "until the app restarts" in privacy_storage_line("The logs", 5000)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'x.db').as_posix()}")
    line = privacy_storage_line("The logs", 5000)
    assert "deleted after 30 days" in line and "names are removed" in line and "restarts" not in line
