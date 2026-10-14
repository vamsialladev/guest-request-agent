"""Synthetic data: reproducible bookings, the sample inbox, the eval files and the pinned Project 1 copy."""

import json
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import make_data  # noqa: E402


def test_bookings_are_reproducible_and_never_overbooked():
    rows = make_data.build_rows()
    assert rows == make_data.build_rows() and len(rows) == make_data.TARGET_TOTAL
    taken = Counter()
    for r in rows:
        if r[14] in ("cancelled", "no_show"):
            continue
        for night in make_data.nights(r[8], r[9]):
            taken[(r[1], r[7], night)] += 1
    assert max(taken.values()) == 1
    assert all(r[3].endswith("@example.com") for r in rows)
    statuses = Counter(r[14] for r in rows)
    assert {"confirmed", "checked_in", "checked_out", "cancelled", "no_show"} <= set(statuses)


def test_nights_the_emails_need_stay_free_and_sold_out_nights_are_full(store):
    assert store.availability("beach-resort", date(2026, 11, 26), date(2026, 11, 28))["Ocean View King"]["free"] == 0
    assert store.availability("beach-resort", date(2026, 11, 21), date(2026, 11, 22))["Suite"]["free"] == 0
    assert store.availability("beach-resort", date(2026, 11, 15), date(2026, 11, 16))["Standard King"]["free"] >= 1
    assert store.availability("mountain-lodge", date(2026, 11, 20), date(2026, 11, 22))["Suite"]["free"] >= 1
    assert store.availability("mountain-lodge", date(2026, 12, 4), date(2026, 12, 6))["Standard Queen"]["free"] >= 1


def test_duplicate_names_and_meta(store):
    assert len(store.by_name("chris  morgan")) == 2
    assert store.by_ref("br-1042").guest_name == "Elena Marsh"
    assert store.window() == (date(2026, 10, 26), date(2026, 12, 8))


def test_inbox_has_thirty_labelled_synthetic_emails():
    inbox = [json.loads(line) for line in (ROOT / "data" / "inbox.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(inbox) == 30 and all(e["synthetic"] and e["from"].endswith("@example.com") for e in inbox)
    cases = [json.loads(line) for line in (ROOT / "eval" / "cases.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(cases) == 40 and {c["inbox_id"] for c in cases if "inbox_id" in c} == {e["id"] for e in inbox}
    cats = Counter(c for case in cases for c in case["categories"])
    assert cats["must-escalate"] == 8 and cats["prompt injection"] == 6 and cats["Spanish"] >= 1
    visitor = (ROOT / "eval" / "visitor.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(visitor) == 10


def test_escalation_rules_on_the_labelled_cases():
    """The rules alone catch the 8 must-escalate cases with no false alarm (I wrote both, so this flatters: the
    held-out set is the real test)."""
    from eval.run_eval import load_cases
    from src.triage import escalation_reasons

    for case in load_cases("main"):
        e = case["email"]
        assert bool(escalation_reasons(f"{e['subject']}\n{e['body']}")) == case["expect_escalate"], case["id"]


def test_policy_copy_matches_the_pinned_project1_commit():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_policy.py"), "--check"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout
    source = json.loads((ROOT / "src" / "policy" / "SOURCE.json").read_text())
    assert source["version"] == "1.5.0" and len(source["commit"]) == 40
    assert (ROOT / "src" / "policy" / "retrieve.py").read_text(encoding="utf-8").startswith("# Copied from Project 1")


def test_ensure_db_builds_a_missing_database(tmp_path):
    from src.bookings import BookingStore, ensure_db

    path = ensure_db(tmp_path / "new.sqlite")
    assert path.exists() and len(BookingStore(path).all()) == 80
