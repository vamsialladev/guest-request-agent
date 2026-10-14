"""A scripted stand-in for anthropic.Anthropic: no network, no key, no cost.

    client = FakeClient([[tool("find_booking", {})], [tool("draft_reply", {...})]])

Each turn is a list of content blocks the fake model "returns". Requests are recorded in `client.requests`.
"""

from types import SimpleNamespace

import anthropic
import httpx2


def tool(name: str, inputs: dict, block_id: str | None = None):
    return SimpleNamespace(type="tool_use", name=name, input=inputs, id=block_id or f"tu_{name}_{id(inputs)}")


def text(value: str):
    return SimpleNamespace(type="text", text=value)


def draft(reply: str, requests=None, escalate=False, reason="", language="en"):
    return tool(
        "draft_reply",
        {
            "requests": requests or [{"summary": "Question", "kind": "policy", "status": "answered"}],
            "reply": reply,
            "escalate": escalate,
            "escalation_reason": reason,
            "language": language,
        },
    )


class FakeMessages:
    def __init__(self, client):
        self.client = client

    def create(self, **params):
        self.client.requests.append(params)
        if self.client.error is not None:
            raise self.client.error
        if not self.client.turns:
            raise AssertionError("the fake model ran out of scripted turns")
        blocks = self.client.turns.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn"
        if self.client.stop_reason:
            stop = self.client.stop_reason
        return SimpleNamespace(
            content=blocks,
            stop_reason=stop,
            usage=SimpleNamespace(input_tokens=self.client.tokens_in, output_tokens=self.client.tokens_out),
        )


class FakeClient:
    def __init__(self, turns=None, error: Exception | None = None, tokens_in=1000, tokens_out=100, stop_reason=None):
        self.turns = list(turns or [])
        self.error = error
        self.tokens_in, self.tokens_out = tokens_in, tokens_out
        self.stop_reason = stop_reason
        self.requests: list[dict] = []
        self.messages = FakeMessages(self)


def api_error(status: int = 500, message: str = "server error") -> anthropic.APIStatusError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    cls = {401: anthropic.AuthenticationError, 429: anthropic.RateLimitError}.get(status, anthropic.InternalServerError)
    return cls(message, response=response, body=None)


def timeout_error() -> anthropic.APITimeoutError:
    return anthropic.APITimeoutError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))
