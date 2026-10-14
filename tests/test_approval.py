"""Nothing is sent or created without approval."""

import pytest

from src.approval import ApprovalError, Desk, Review, approve, reject, reply_subject
from src.models import Action, Task


def review():
    return Review(
        request_id="r1",
        to="guest@example.com",
        subject="Dog",
        draft="The fee is $75 [P1].",
        tasks=[Task(id="T1", department="concierge", title="Book pickup")],
        actions=[Action(id="A1", action_type="refund", reason="AC broken")],
        property="beach-resort",
    )


def test_nothing_happens_until_approval():
    desk, r = Desk(), review()
    desk.reviews[r.request_id] = r
    assert desk.counts() == {"sent": 0, "tasks": 0, "manager": 0}


def test_approve_sends_simulated_and_opens_tasks():
    desk, r = Desk(), review()
    record = approve(desk, r, r.draft)
    assert desk.outbox[0]["body"] == "The fee is $75." and desk.outbox[0]["simulated"] is True
    assert desk.outbox[0]["subject"] == "Re: Dog" and record["edited"] is False
    assert desk.board[0]["status"] == "open" and desk.board[0]["request_id"] == "r1"
    assert desk.manager_queue[0]["status"] == "needs manager approval"  # approving a reply never approves a refund
    assert record == {
        "request_id": "r1",
        "decision": "approved",
        "edited": False,
        "final_text": "The fee is $75.",
        "tasks_opened": 1,
        "actions_queued": 1,
    }
    with pytest.raises(ApprovalError):
        approve(desk, r, r.draft)  # can't send twice


def test_edited_text_is_what_gets_sent():
    desk, r = Desk(), review()
    record = approve(desk, r, "The pet fee is $75 per stay. See you Friday!")
    assert record["edited"] and desk.outbox[0]["body"].endswith("See you Friday!")


def test_empty_reply_is_refused():
    with pytest.raises(ApprovalError):
        approve(Desk(), review(), "  [P1] ")


def test_reject_needs_a_reason_and_creates_nothing():
    desk, r = Desk(), review()
    with pytest.raises(ApprovalError):
        reject(desk, r, " ")
    record = reject(desk, r, "Wrong fee for this guest")
    assert record["decision"] == "rejected" and desk.counts() == {"sent": 0, "tasks": 0, "manager": 0}
    with pytest.raises(ApprovalError):
        approve(desk, r, r.draft)


def test_reply_subject():
    assert reply_subject("Re: hello") == "Re: hello" and reply_subject("") == "Re: Your stay"
