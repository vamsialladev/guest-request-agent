"""The A2A server end to end over an in-process ASGI transport: agent card, auth, task lifecycle, data artifact."""

import asyncio

import httpx
import pytest
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_data_message
from a2a.types import Role, SendMessageRequest
from google.protobuf.json_format import MessageToDict

from src import a2a_server
from src.models import AgentResult, Task

URL = "http://guest-agent.test"


def fake_process(email, prop, source):
    assert source == "a2a"
    result = AgentResult(outcome="drafted", reply=f"Dogs are welcome at {prop} [P1].",
                         tasks=[Task(id="T1", department="front_desk", title="Note the dog", details="")])  # fmt: skip
    return result, {"trace_id": "4f1c9a2e" * 4, "request_id": "r1"}


def client_for(app, token="test-token"):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=URL,
                             headers={"Authorization": f"Bearer {token}"})  # fmt: skip


async def send(app, data, token="test-token"):
    async with client_for(app, token) as http:
        card = await A2ACardResolver(httpx_client=http, base_url=URL).get_agent_card()
        client = await create_client(agent=card, client_config=ClientConfig(streaming=False, httpx_client=http))
        request = SendMessageRequest(message=new_data_message(data, role=Role.ROLE_USER))
        events = [e async for e in client.send_message(request)]
        await client.close()
        return card, events


def test_card_describes_the_skill_and_bearer_auth():
    card = a2a_server.agent_card(URL)
    assert card.name == "Guest Request Agent" and card.skills[0].id == "handle_guest_email"
    assert "bearer" in card.security_schemes


def test_a_guest_email_completes_with_a_data_artifact():
    app = a2a_server.create_app("test-token", URL, process=fake_process)
    email = {"property": "mountain-lodge", "sender": "a@b.co", "body": "Can we bring a dog?"}
    _, events = asyncio.run(send(app, email))
    text = str(MessageToDict(events[-1][0] if isinstance(events[-1], tuple) else events[-1]))
    assert "TASK_STATE_COMPLETED" in text and "Dogs are welcome at mountain-lodge" in text
    assert "Note the dog" in text and "nothing was sent to the guest" in text


def test_wrong_token_is_refused():
    app = a2a_server.create_app("test-token", URL, process=fake_process)
    with pytest.raises(Exception, match="401|nauthorized"):  # noqa: B017 - the SDK's HTTP error type varies by transport
        asyncio.run(send(app, {"body": "hi"}, token="wrong"))


def test_an_empty_email_fails_cleanly():
    app = a2a_server.create_app("test-token", URL, process=fake_process)
    _, events = asyncio.run(send(app, {"subject": "nothing"}))
    assert "TASK_STATE_FAILED" in str(events[-1])
