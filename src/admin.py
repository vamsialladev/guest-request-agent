"""Password gate for the owner-only Admin page.

This is simple demo protection, not real authentication (see SECURITY.md): one shared password from
the environment / Streamlit secrets, compared in constant time, with a per-session lockout after
repeated failures. Proper sign-in with roles is planned for Project 4.
"""

import hmac
import math
from dataclasses import dataclass

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60
FAILURE_DELAY_SECONDS = 1.0  # slows down guessing; applied by the page after each failure

WRONG = "Incorrect password."


@dataclass
class GateState:
    failures: int = 0
    locked_until: float = 0.0
    unlocked: bool = False
    last_active: float = 0.0


def password_matches(given: str, secret: str) -> bool:
    return hmac.compare_digest(given.encode("utf-8"), secret.encode("utf-8"))


def locked_message(state: GateState, now: float) -> str | None:
    if now < state.locked_until:
        minutes = math.ceil((state.locked_until - now) / 60)
        return f"Too many attempts. Try again in {minutes} minute{'s' if minutes != 1 else ''}."
    return None


def attempt(state: GateState, given: str, secret: str | None, now: float) -> tuple[bool, str | None]:
    """Check a password attempt. Returns (unlocked, message). Never says how close a guess was."""
    if not secret:
        return False, "The admin page is not configured."
    locked = locked_message(state, now)
    if locked:
        return False, locked
    if now >= state.locked_until and state.locked_until:
        state.failures, state.locked_until = 0, 0.0  # lockout expired: start counting again
    if password_matches(given or "", secret):
        state.failures, state.unlocked, state.last_active = 0, True, now
        return True, None
    state.failures += 1
    if state.failures >= MAX_ATTEMPTS:
        state.locked_until = now + LOCKOUT_SECONDS
        return False, locked_message(state, now)
    return False, WRONG


def sign_out(state: GateState) -> None:
    state.unlocked = False
    state.last_active = 0.0


def still_signed_in(state: GateState, now: float, idle_seconds: float) -> bool:
    """Called on every Admin page load: locks the page after `idle_seconds` without activity, otherwise
    records the activity. Returns whether the owner is still signed in."""
    if not state.unlocked:
        return False
    if now - state.last_active > idle_seconds:
        sign_out(state)
        return False
    state.last_active = now
    return True
