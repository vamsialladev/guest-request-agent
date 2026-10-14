"""The sample inbox: 30 synthetic guest emails (data/inbox.jsonl), and the inbox list's statuses and filters."""

import json
from pathlib import Path

from src.agent import Email
from src.config import INBOX_FILE
from src.triage import escalation_reasons


def load_inbox(path: Path = INBOX_FILE) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def to_email(item: dict) -> Email:
    return Email(
        sender=item["from"], subject=item.get("subject", ""), body=item["body"], sender_name=item.get("name", "")
    )


def status_of(item_id: str, results: dict, reviews: dict) -> str:
    """new | drafted | escalated | approved | rejected, for this browser session."""
    done = results.get(item_id)
    if not done:
        return "new"
    result, request_id = done[0], done[1]
    review = reviews.get(request_id)
    if review and review.status in ("approved", "rejected"):
        return review.status
    return "escalated" if result.escalate else "drafted"


def flagged(item: dict) -> bool:
    """Preview before processing: the escalation rules (no API call) already flag this email."""
    return bool(escalation_reasons(f"{item.get('subject', '')}\n{item['body']}"))


STATUS_ICONS = {
    "new": "✉️ New",
    "drafted": "📝 Draft ready",
    "escalated": "🟠 Escalated",
    "approved": "✅ Sent",
    "rejected": "✖ Rejected",
}


def rows(
    items: list[dict],
    results: dict,
    reviews: dict,
    prop: str | None = None,
    status: str | None = None,
    escalated_only: bool = False,
) -> list[dict]:
    out = []
    for item in items:
        st = status_of(item["id"], results, reviews)
        escalated = st == "escalated" or flagged(item) or (item["id"] in results and results[item["id"]][0].escalate)
        if prop and item["property"] != prop:
            continue
        if status and st != status:
            continue
        if escalated_only and not escalated:
            continue
        out.append(
            {
                "id": item["id"],
                "status": STATUS_ICONS[st],
                "from": item.get("name") or item["from"],
                "subject": item.get("subject", ""),
                "property": {"beach-resort": "Beach", "mountain-lodge": "Lodge"}.get(
                    item["property"], item["property"]
                ),
                "received": item.get("received", "").replace("T", " ")[5:],
                "escalated": "⚑" if escalated else "",
            }
        )
    return out
