import anthropic
import httpx2
import pytest

from src.errors import CATEGORIES, UNAVAILABLE, category, classify, error_record, private_detail

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, code, message="error"):
    return cls(message, response=httpx2.Response(code, request=REQUEST), body=None)


@pytest.mark.parametrize(
    "exc,code",
    [
        (status_error(anthropic.RateLimitError, 429), "rate_limit"),
        (status_error(anthropic.AuthenticationError, 401), "auth"),
        (status_error(anthropic.PermissionDeniedError, 403), "permission"),
        (status_error(anthropic.BadRequestError, 400, "Your credit balance is too low"), "credit_exhausted"),
        (status_error(anthropic.NotFoundError, 404, "model: claude-not-a-model"), "model_not_found"),
        (status_error(anthropic.InternalServerError, 500), "server_error"),
        (status_error(anthropic.BadRequestError, 400, "invalid request"), "api_400"),
        (anthropic.APIConnectionError(request=REQUEST), "connection"),
        (TypeError("Could not resolve authentication method. Expected one of api_key"), "missing_key"),
        (RuntimeError("something else"), "unexpected"),
    ],
)
def test_errors_are_classified_for_the_private_log(exc, code):
    assert classify(exc) == code


def test_visitor_message_reveals_nothing():
    assert UNAVAILABLE == "The demo is temporarily unavailable. Please try again later."


def test_private_detail_is_short_and_masks_keys():
    detail = private_detail(RuntimeError("key sk-ant-abc123 " + "x" * 500))
    assert detail.startswith("RuntimeError: key sk-ant-***") and len(detail) == 300


@pytest.mark.parametrize(
    "code,words",
    [
        ("auth", "authentication"),
        ("missing_key", "ANTHROPIC_API_KEY is missing"),
        ("credit_exhausted", "credit balance"),
        ("model_not_found", "LLM_MODEL"),
        ("rate_limit", "rate limit"),
        ("connection", "network"),
        ("api_400", "HTTP 400"),
        ("unexpected", "unexpected"),
    ],
)
def test_each_error_code_has_a_plain_category_for_the_owner(code, words):
    assert words in category(code)


def test_categories_never_contain_key_material():
    assert not any("sk-ant" in text for text in CATEGORIES.values())


def test_error_record_carries_the_category_and_masks_the_key():
    exc = status_error(anthropic.AuthenticationError, 401, "invalid x-api-key sk-ant-fake-value-123")
    rec = error_record("Assistant", exc)
    assert rec["type"] == "auth" and rec["category"].startswith("authentication")
    assert "sk-ant-fake" not in str(rec) and "sk-ant-***" in rec["message"]
