"""Staff approval: the only path from a draft to the (simulated) outbox and from proposed tasks to the task board.

Pure state, no Streamlit, so the rule "nothing is sent or created without approval" is unit-tested:
- `approve` puts the final text (citation markers removed) in the outbox and opens the proposed tasks.
  Proposed actions (refunds, upgrades, ...) go to the manager queue, still "needs manager approval".
- `reject` needs a reason; nothing is sent and the proposed tasks are discarded.
The outbox is a list in the browser session. Nothing is ever emailed.
"""

from dataclasses import dataclass, field

from src.guards import strip_citations
from src.models import Action, Task
from src.usage import now_iso


@dataclass
class Review:
    request_id: str
    to: str
    subject: str
    draft: str
    tasks: list[Task]
    actions: list[Action]
    property: str
    escalate: bool = False
    status: str = "pending"  # pending | approved | rejected
    final_text: str = ""
    reason: str = ""


@dataclass
class Desk:
    """One browser session's simulated outbox, task board and manager queue."""

    outbox: list[dict] = field(default_factory=list)
    board: list[dict] = field(default_factory=list)
    manager_queue: list[dict] = field(default_factory=list)
    reviews: dict[str, Review] = field(default_factory=dict)

    def counts(self) -> dict:
        return {"sent": len(self.outbox), "tasks": len(self.board), "manager": len(self.manager_queue)}


class ApprovalError(ValueError):
    pass


def reply_subject(subject: str) -> str:
    subject = (subject or "").strip() or "Your stay"
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def approve(desk: Desk, review: Review, final_text: str) -> dict:
    """Approve and 'send' (simulated). Returns the decision record for the log."""
    if review.status != "pending":
        raise ApprovalError(f"This draft was already {review.status}.")
    body = strip_citations(final_text).strip()
    if len(body) < 10:
        raise ApprovalError("The reply is empty. Write a reply or reject the draft.")
    review.status, review.final_text = "approved", body
    edited = " ".join(strip_citations(review.draft).split()) != " ".join(body.split())
    time = now_iso()
    desk.outbox.append(
        {
            "request_id": review.request_id,
            "to": review.to,
            "subject": reply_subject(review.subject),
            "body": body,
            "time": time,
            "simulated": True,
            "edited": edited,
        }
    )
    for t in review.tasks:
        desk.board.append({**t.model_dump(), "status": "open", "request_id": review.request_id, "time": time})
    for a in review.actions:
        desk.manager_queue.append(
            {**a.model_dump(), "status": "needs manager approval", "request_id": review.request_id, "time": time}
        )
    return {
        "request_id": review.request_id,
        "decision": "approved",
        "edited": edited,
        "final_text": body,
        "tasks_opened": len(review.tasks),
        "actions_queued": len(review.actions),
    }


def reject(desk: Desk, review: Review, reason: str) -> dict:
    if review.status != "pending":
        raise ApprovalError(f"This draft was already {review.status}.")
    reason = " ".join((reason or "").split())
    if len(reason) < 3:
        raise ApprovalError("Give a short reason for rejecting the draft.")
    review.status, review.reason = "rejected", reason
    return {
        "request_id": review.request_id,
        "decision": "rejected",
        "reason": reason,
        "final_text": None,
        "tasks_opened": 0,
        "actions_queued": 0,
    }
