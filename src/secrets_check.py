"""Which secrets are configured. Reports only "set" or "missing", never a value.

Read at call time from the environment: `streamlit run` copies top-level string values from
.streamlit/secrets.toml (local) or Streamlit Cloud's Secrets into the environment, and .env fills the rest.
"""

import logging
import os

REQUIRED = ("ANTHROPIC_API_KEY", "ADMIN_PASSWORD")
PLACEHOLDER_PREFIXES = ("your-", "change-me", "replace-me")  # copied from an example file, never filled in

log = logging.getLogger("guest_agent.config")


def is_set(value: str | None) -> bool:
    value = (value or "").strip()
    return bool(value) and not value.lower().startswith(PLACEHOLDER_PREFIXES)


def secret_status(env=None, names=REQUIRED) -> dict[str, str]:
    env = os.environ if env is None else env
    return {name: "set" if is_set(env.get(name)) else "missing" for name in names}


SECRET_NAME_PARTS = ("KEY", "SECRET", "PASSWORD", "TOKEN")
MIN_SECRET_CHARS = 8  # shorter values would mask ordinary words


def secret_values(env=None) -> list[str]:
    """Values of the configured secrets (required ones, plus anything named like a key, secret, password or
    token), longest first. Used only to mask them out of the logs; never shown or logged."""
    env = os.environ if env is None else env
    names = set(REQUIRED) | {n for n in env if any(part in n.upper() for part in SECRET_NAME_PARTS)}
    values = {(env.get(n) or "").strip() for n in names}
    return sorted((v for v in values if len(v) >= MIN_SECRET_CHARS and is_set(v)), key=len, reverse=True)


def missing_required(env=None) -> list[str]:
    return [name for name, state in secret_status(env, REQUIRED).items() if state == "missing"]


def log_missing(env=None, logger=log) -> list[str]:
    """Startup check: one clear log line per missing required secret, naming the key only."""
    missing = missing_required(env)
    for name in missing:
        logger.error(
            "Missing required secret: %s. Add it to .streamlit/secrets.toml or .env locally, "
            "or to the app's Secrets on Streamlit Cloud, then reboot the app.",
            name,
        )
    return missing


# ---------- .streamlit/secrets.toml for Streamlit Cloud, built from .env ----------
# Every setting the deployed app needs, with the app's defaults when .env doesn't set one.
CLOUD_SETTINGS = {
    "ANTHROPIC_API_KEY": "",
    "ADMIN_PASSWORD": "",
    "LLM_MODEL": "claude-haiku-5-5",
    "LLM_MAX_TOKENS": "2000",
    "LLM_EFFORT": "low",
    "LLM_TIMEOUT_S": "30",
    "LLM_RETRIES": "1",
    "MAX_AGENT_STEPS": "6",
    "PRICE_IN_PER_M": "0.10",
    "PRICE_OUT_PER_M": "0.50",
    "MAX_EMAIL_CHARS": "2000",
    "MAX_EMAILS_PER_SESSION": "10",
    "MAX_EMAILS_PER_DAY": "150",
    "LOG_MAX_ENTRIES": "5000",
    "ADMIN_IDLE_MINUTES": "30",
    "ALERT_ERROR_RATE": "0.2",
    "ALERT_MIN_EVENTS": "5",
    "ALERT_DAILY_COST_USD": "1.00",
}
FORCED: dict[str, str] = {}  # Project 1 forced keyword-only search here; Project 2 is always keyword-only


def build_secrets(env: dict) -> dict[str, str]:
    """Cloud settings from a .env mapping: .env values win over defaults, except the forced cloud ones."""
    out = {}
    for name, default in CLOUD_SETTINGS.items():
        value = (env.get(name) or "").strip() or default  # python-dotenv already drops inline comments
        out[name] = FORCED.get(name, value)
    return out


def to_toml(settings: dict[str, str]) -> str:
    """Top-level keys only, every value a double-quoted string, so Streamlit copies each one into the
    environment (it skips booleans and tables). Escaping follows TOML basic strings."""

    def quote(value: str) -> str:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return '"' + "".join(c if c >= " " and c != "\x7f" else f"\\u{ord(c):04x}" for c in escaped) + '"'

    lines = [
        "# Streamlit secrets for this app. NEVER commit this file (it is git- and docker-ignored).",
        "# Paste the whole file into Streamlit Cloud: app menu > Settings > Secrets > Save, then Reboot.",
        "# Rebuild it with: python scripts/make_secrets.py",
        "",
    ]
    lines += [f"{name} = {quote(value)}" for name, value in settings.items()]
    return "\n".join(lines) + "\n"
