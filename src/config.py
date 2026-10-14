"""Central settings. Everything can be overridden with environment variables / .env.

On Streamlit Community Cloud, root-level secrets are exposed as environment variables, so the same names work there.
Prices and caps are configuration, never hard-coded in the logic.
"""

import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LOG_DIR = Path(os.getenv("LOG_DIR", DATA_DIR / "logs"))
REPORTS_DIR = ROOT / "eval" / "reports"
BOOKINGS_DB = Path(os.getenv("BOOKINGS_DB", DATA_DIR / "bookings.sqlite"))
INBOX_FILE = DATA_DIR / "inbox.jsonl"


def _float(name: str, default: str = "") -> float | None:
    value = os.getenv(name, default).strip()
    return float(value) if value else None


# The synthetic world has a fixed "today", so bookings, availability and evals are reproducible on any real date.
SIM_TODAY = date.fromisoformat(os.getenv("SIM_TODAY", "2026-11-02"))

# Model and agent loop
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))  # per model turn; thinking counts toward it
LLM_EFFORT = os.getenv("LLM_EFFORT", "low").strip() or None  # low | medium | high; empty = model default (medium)
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "30"))  # per API call
LLM_RETRIES = int(os.getenv("LLM_RETRIES", "1"))  # one retry on timeouts, 429 and 5xx
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "6"))  # model turns per email

# Public demo protections
MAX_EMAIL_CHARS = int(os.getenv("MAX_EMAIL_CHARS", "2000"))
MAX_EMAILS_PER_SESSION = int(os.getenv("MAX_EMAILS_PER_SESSION", "10"))
MAX_EMAILS_PER_DAY = int(os.getenv("MAX_EMAILS_PER_DAY", "150"))
LOG_MAX_ENTRIES = int(os.getenv("LOG_MAX_ENTRIES", "5000"))

# USD per million tokens, used only for cost estimates (defaults: Claude Haiku 5.5 list prices, Oct 2026).
# Set to an empty value to show cost as "not configured".
PRICE_IN_PER_M = _float("PRICE_IN_PER_M", "0.10")
PRICE_OUT_PER_M = _float("PRICE_OUT_PER_M", "0.50")

# Owner monitoring (Admin page)
ALERT_ERROR_RATE = float(os.getenv("ALERT_ERROR_RATE", "0.2"))
ALERT_MIN_EVENTS = int(os.getenv("ALERT_MIN_EVENTS", "5"))
ALERT_DAILY_COST_USD = float(os.getenv("ALERT_DAILY_COST_USD", "1.00"))
ADMIN_IDLE_MINUTES = int(os.getenv("ADMIN_IDLE_MINUTES", "30"))


def admin_password() -> str | None:
    """Read at call time so a secret added on Streamlit Cloud is picked up. Never log the value."""
    return os.getenv("ADMIN_PASSWORD") or None


PROPERTIES = ("beach-resort", "mountain-lodge")
