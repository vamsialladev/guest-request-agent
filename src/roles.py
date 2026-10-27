"""Demo mode and the Staff role (Project 4).

- Demo mode (default, no sign-in): the public demo, unchanged. Everyone can ask questions.
- Staff (STAFF_PASSWORD): unlocks the write actions that change what other people see: reporting an answer for review
  (the review queue on the Operations page) and no per-session question cap (the daily cap still applies).
- Owner (ADMIN_PASSWORD): the Admin and Operations pages.

Same protection as the Admin gate (src/admin.py): constant-time compare, 5 tries then a 15-minute lockout, sign-out
after STAFF_IDLE_MINUTES idle. A shared password is a demo-grade control; a real client deployment would put the app
behind the client's SSO (OIDC) and map an identity-provider group to the Staff role (decision 54).
"""

from src.admin import GateState, attempt, sign_out, still_signed_in

DEMO, STAFF = "demo", "staff"
REPORT_REASONS = ("Wrong or outdated", "Harmful or unsafe", "Missing a manager note", "Other")
DEMO_LABEL = "Demo mode · synthetic hotel data · open to everyone"


def role(gate: GateState | None, now: float, idle_seconds: float) -> str:
    return STAFF if gate is not None and still_signed_in(gate, now, idle_seconds) else DEMO


def staff_attempt(gate: GateState, given: str, secret: str | None, now: float) -> tuple[bool, str | None]:
    ok, message = attempt(gate, given, secret, now, scope="staff")  # its own lockout counter
    if message == "The admin page is not configured.":
        message = "Staff sign-in is not configured."
    return ok, message


def report_record(request_id: str | None, question: str, reason: str, note: str, now_iso: str) -> dict:
    """A staff report of a bad or harmful answer (runbook: docs/RUNBOOKS.md in hotel-ai-handoff)."""
    if reason not in REPORT_REASONS:
        reason = "Other"
    return {
        "time": now_iso,
        "request_id": request_id,
        "question": question[:500],
        "reason": reason,
        "note": (note or "").strip()[:500],
        "role": STAFF,
        "status": "open",
    }


__all__ = ["DEMO", "STAFF", "GateState", "role", "sign_out", "staff_attempt", "report_record", "REPORT_REASONS"]
