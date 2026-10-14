"""Startup secrets check. Fake values only; the check must never reveal a value."""

import logging

from src.secrets_check import REQUIRED, is_set, log_missing, missing_required, secret_status

FAKE = {"ANTHROPIC_API_KEY": "sk-ant-fake-for-tests", "ADMIN_PASSWORD": "fake-admin-pass", "PRICE_IN_PER_M": "0.10"}


def test_status_is_only_set_or_missing():
    status = secret_status(FAKE)
    # Only secrets: prices are configuration with documented defaults, not secrets.
    assert status == {"ANTHROPIC_API_KEY": "set", "ADMIN_PASSWORD": "set"}
    assert "sk-ant-fake-for-tests" not in str(status) and "fake-admin-pass" not in str(status)


def test_empty_blank_and_example_placeholders_count_as_missing():
    assert not is_set(None) and not is_set("") and not is_set("   ")
    assert not is_set("your-key-here") and not is_set("Your-Key") and not is_set("change-me")
    assert is_set("a-real-looking-value")


def test_missing_required_names_the_keys():
    assert missing_required(FAKE) == []
    assert missing_required({}) == list(REQUIRED)
    assert missing_required({"ANTHROPIC_API_KEY": "sk-ant-fake"}) == ["ADMIN_PASSWORD"]


def test_startup_log_names_the_missing_key_but_never_a_value(caplog):
    env = {"ANTHROPIC_API_KEY": "", "ADMIN_PASSWORD": "fake-admin-pass"}
    with caplog.at_level(logging.ERROR, logger="guest_agent.config"):
        missing = log_missing(env)
    assert missing == ["ANTHROPIC_API_KEY"]
    assert "Missing required secret: ANTHROPIC_API_KEY" in caplog.text
    assert "fake-admin-pass" not in caplog.text


def test_nothing_logged_when_everything_is_set(caplog):
    with caplog.at_level(logging.ERROR, logger="guest_agent.config"):
        assert log_missing(FAKE) == []
    assert caplog.text == ""


def test_reads_the_environment_by_default(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    assert secret_status()["ANTHROPIC_API_KEY"] == "set"
    assert missing_required() == ["ADMIN_PASSWORD"]


def test_secrets_file_has_every_setting_quoted_at_the_top_level():
    import tomllib

    from src.secrets_check import CLOUD_SETTINGS, build_secrets, to_toml

    tricky = 'fa"ke\\pa#s\x01s'  # quote, backslash, # and a control character
    env = {"ANTHROPIC_API_KEY": "sk-ant-fake", "ADMIN_PASSWORD": tricky, "LLM_EFFORT": "medium"}
    settings = build_secrets(env)
    parsed = tomllib.loads(to_toml(settings))
    assert parsed == settings and list(parsed) == list(CLOUD_SETTINGS)
    assert all(isinstance(v, str) for v in parsed.values())  # no booleans or tables: Streamlit skips those
    assert parsed["LLM_EFFORT"] == "medium"  # .env wins over the default
    assert parsed["ADMIN_PASSWORD"] == tricky  # survives the round trip unchanged


def test_secrets_file_uses_env_values_then_defaults(tmp_path):
    from dotenv import dotenv_values

    from src.secrets_check import build_secrets

    env_file = tmp_path / ".env"
    env_file.write_text("MAX_EMAILS_PER_DAY=120   # daily cap\nMAX_AGENT_STEPS=\n", encoding="utf-8")
    settings = build_secrets(dotenv_values(env_file))
    assert settings["MAX_EMAILS_PER_DAY"] == "120" and settings["MAX_AGENT_STEPS"] == "6"
    assert settings["ANTHROPIC_API_KEY"] == "" and settings["LLM_MODEL"] == "claude-haiku-5-5"
