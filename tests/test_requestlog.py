from datetime import date

from src.display import diff_html, draft_html
from src.requestlog import (
    NOT_RECORDED,
    details,
    filter_requests,
    find,
    list_rows,
    log_since,
    request_json,
    selected_id,
    table_key,
    to_jsonl,
)

RECORDS = [
    {
        "time": "2026-10-13T10:00:00+00:00",
        "request_id": "a",
        "property": "beach-resort",
        "source": "inbox",
        "email": {"from": "elena.marsh@example.com", "subject": "Dog", "body": "Can we bring our dog?"},
        "outcome": "drafted",
        "escalate": False,
        "draft": "The fee is $75 [P1].",
        "api_calls": 2,
        "latency_s": 4.2,
        "cost_usd": 0.0012,
        "steps": [{"n": 1}],
        "schema_version": 1,
    },
    {
        "time": "2026-10-14T09:00:00+00:00",
        "request_id": "b",
        "property": "mountain-lodge",
        "source": "write",
        "email": {"from": "x@example.com", "subject": "", "body": "Gas smell in the cabin"},
        "outcome": "escalated",
        "escalate": True,
        "api_calls": 1,
        "latency_s": 2.0,
        "cost_usd": 0.0004,
    },
    {
        "time": "2026-10-14T09:05:00+00:00",
        "outcome": "greeting",
        "email": {"body": "hi"},
        "api_calls": 0,
        "latency_s": 0.0,
    },
]
DECISIONS = [{"request_id": "a", "decision": "approved", "final_text": "The pet fee is $75 per stay. See you soon!"}]


def test_rows_newest_first_with_decisions_and_not_recorded():
    rows = list_rows(RECORDS, DECISIONS)
    assert [r["outcome"] for r in rows] == ["greeting", "escalated", "drafted"]
    assert rows[2]["decision"] == "✅ Approved" and rows[1]["decision"] == "⏳ Pending"
    assert rows[0]["property"] == NOT_RECORDED and rows[0]["id"].startswith("old-") and rows[0]["total"] == "–"
    assert rows[2]["total"] == "4.2 s" and rows[2]["cost"] == "$0.00120" and rows[0]["cost"] == NOT_RECORDED


def test_filters():
    rows = list_rows(RECORDS, DECISIONS)
    assert [r["id"] for r in filter_requests(rows, escalated_only=True)] == ["b"]
    assert [r["id"] for r in filter_requests(rows, prop="beach-resort")] == ["a"]
    assert [r["id"] for r in filter_requests(rows, text="GAS smell")] == ["b"]
    assert [r["id"] for r in filter_requests(rows, text="elena.marsh")] == ["a"]
    assert len(filter_requests(rows, start=date(2026, 10, 14), end=date(2026, 10, 14))) == 2
    assert [r["outcome"] for r in filter_requests(rows, outcomes=["greeting"])] == ["greeting"]


def test_selection_and_lookup():
    rows = list_rows(RECORDS, DECISIONS)
    assert selected_id(rows, {"selection": {"rows": [2]}}) == "a"
    assert selected_id(rows, {"selection": {"rows": [9]}}) is None and selected_id(rows, None) is None
    assert find(RECORDS, "b")["outcome"] == "escalated" and find(RECORDS, "zzz") is None
    assert table_key((1,), 50) != table_key((2,), 50)


def test_details_show_draft_vs_final_and_missing_fields():
    d = details(RECORDS[0], DECISIONS)
    assert d["edited"] and d["final_text"].endswith("See you soon!") and d["decision"]["decision"] == "approved"
    old = details(RECORDS[2], [])
    assert old["model"] == "none (no API call)" and old["property"] == NOT_RECORDED and old["decision"] is None
    assert '"decision": "approved"' in request_json(RECORDS[0], DECISIONS)
    assert to_jsonl(RECORDS[:1]).count("\n") == 1 and log_since(RECORDS) == "2026-10-13 10:00:00"
    assert log_since([]) is None


def test_diff_and_draft_html_escape_everything():
    html = diff_html("The fee is $75.", "The fee is <b>$75</b> per stay.")
    assert "<del>" in html and "<ins>" in html and "&lt;b&gt;" in html
    draft = draft_html("Fee <script>x</script> [P1]", {"P1": 'Pets "policy"'})
    assert "&lt;script&gt;" in draft and 'class="gra-cite" title="Pets &quot;policy&quot;">P1<' in draft
