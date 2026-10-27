"""Password gate for the owner-only Admin page (and, through src/roles.py, the staff sign-in).

This is simple demo protection, not real authentication (see SECURITY.md): one shared password from
the environment / Streamlit secrets, compared in constant time. Five wrong tries lock the gate for 15 minutes,
counted per browser session AND per server process, so opening a new tab doesn't reset the count (the shared
hotel-ai-platform gate, decision 5 there). Real sign-in for a client is SSO (hotel-ai-handoff docs).
"""

import hmac
import math

from hotelplatform import admin_gate

MAX_ATTEMPTS = admin_gate.MAX_ATTEMPTS
LOCKOUT_SECONDS = admin_gate.LOCKOUT_S
FAILURE_DELAY_SECONDS = 1.0  # slows down guessing; applied by the page after each failure

WRONG = admin_gate.WRONG

GateState = admin_gate.SessionGate  # failures, locked_until, unlocked, last_active


def password_matches(given: str, secret: str) -> bool:
    return hmac.compare_digest(given.encode("utf-8"), secret.encode("utf-8"))


def locked_message(state: GateState, now: float) -> str | None:
    if now < state.locked_until:
        minutes = math.ceil((state.locked_until - now) / 60)
        return f"Too many attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
    return None


def attempt(
    state: GateState, given: str, secret: str | None, now: float, scope: str = "admin"
) -> tuple[bool, str | None]:
    """Check a password attempt. Returns (unlocked, message). Never says how close a guess was."""
    return admin_gate.attempt(state, given, secret or "", now=now, scope=scope)


def sign_out(state: GateState) -> None:
    admin_gate.sign_out(state)


def still_signed_in(state: GateState, now: float, idle_seconds: float) -> bool:
    """Called on every Admin page load: locks the page after `idle_seconds` without activity, otherwise
    records the activity. Returns whether the owner is still signed in."""
    return admin_gate.still_signed_in(state, now, idle_seconds)
