"""The Guest Request Agent as an A2A agent (official `a2a-sdk`, protocol 1.0, JSON-RPC binding).

Another agent (stage 6's concierge) hands it a guest email and gets back the same structured result staff see:
requests found, a cited draft, proposed tasks, and actions that only a manager can approve.

    python -m src.a2a_server                       serve on A2A_PORT (default 9100) with A2A_TOKEN required
    GET  /.well-known/agent-card.json               the agent card (public: what it does, how to authenticate)
    POST /                                          JSON-RPC: SendMessage, GetTask, ... (Bearer A2A_TOKEN)

Task lifecycle: submitted → working ("Reading the email, checking the booking and policy") → completed with one data
artifact, or failed with a safe message. Nothing is ever sent to a guest: the draft goes to staff review like any
other email, and money or guest-impacting actions stay proposals.

Streamlit Community Cloud can't serve this endpoint, so it runs locally or in Docker (`docker compose up`), and the
concierge falls back to doing the work itself when it can't reach it (decision 28).
"""

import asyncio
import hmac
import json
import os

from a2a.helpers import get_data_parts, get_message_text, new_task_from_user_message, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    HTTPAuthSecurityScheme,
    Part,
    SecurityRequirement,
    SecurityScheme,
    StringList,
    TaskState,
)
from google.protobuf import struct_pb2
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.agent import Email
from src.ops import APP_VERSION

PROPERTIES = ("beach-resort", "mountain-lodge")
CARD_PATH = "/.well-known/agent-card.json"


def agent_card(url: str) -> AgentCard:
    skill = AgentSkill(
        id="handle_guest_email",
        name="Handle a guest email",
        description=(
            "Reads one guest email, checks the sender's booking, availability and hotel policy, and returns the "
            "requests found, a cited draft reply for staff review, proposed tasks, and actions that need a manager."
        ),
        input_modes=["application/json", "text/plain"],
        output_modes=["application/json"],
        tags=["hotel", "guest-email", "simulated"],
        examples=[
            '{"property": "beach-resort", "sender": "elena.marsh@example.com", "subject": "Dog", '
            '"body": "Can we bring our dog?"}'
        ],  # fmt: skip
    )
    return AgentCard(
        name="Guest Request Agent",
        description="Stage 2 of a simulated hotel engagement (synthetic data). Drafts are for staff review only.",
        version=APP_VERSION,
        default_input_modes=["application/json", "text/plain"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=url, protocol_version="1.0")],
        security_schemes={"bearer": SecurityScheme(http_auth_security_scheme=HTTPAuthSecurityScheme(scheme="bearer"))},
        security_requirements=[SecurityRequirement(schemes={"bearer": StringList()})],
        skills=[skill],
    )


def parse_email(context: RequestContext) -> tuple[Email, str]:
    """The email from a data part ({property, sender, sender_name, subject, body}) or, failing that, plain text."""
    data = next(iter(get_data_parts(context.message.parts)), None) if context.message else None
    if isinstance(data, dict) and data.get("body"):
        prop = data.get("property") if data.get("property") in PROPERTIES else "beach-resort"
        return Email(str(data.get("sender", "")), str(data.get("subject", "")), str(data["body"]),
                     str(data.get("sender_name", ""))), prop  # fmt: skip
    return Email("", "", get_message_text(context.message) or ""), "beach-resort"


def summary(result, record: dict) -> dict:
    """What another agent gets back: the structured result, never the guest's personal data beyond the email."""
    return {
        "outcome": result.outcome,
        "escalate": result.escalate,
        "escalation_reasons": result.escalation_reasons,
        "language": result.language,
        "requests": [r.model_dump() for r in result.requests],
        "draft": result.reply,
        "citations": [c.get("id") for c in result.citations],
        "tasks": [t.model_dump() for t in result.tasks],
        "actions_needing_approval": [a.model_dump() for a in result.actions],
        "trace_id": record.get("trace_id"),
        "request_id": record.get("request_id"),
        "note": "Draft for staff review; nothing was sent to the guest.",
    }


class GuestEmailExecutor(AgentExecutor):
    def __init__(self, process=None):
        from src.service import process as default_process

        self.process = process or default_process

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Reading the email, checking the booking and policy"),
        )
        email, prop = parse_email(context)
        if not email.body.strip():
            await updater.update_status(state=TaskState.TASK_STATE_FAILED, message=new_text_message("No email body."))
            return
        try:
            result, record = await asyncio.to_thread(self.process, email, prop, source="a2a")
        except Exception:  # noqa: BLE001 - another agent gets a safe message, never a stack trace
            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED, message=new_text_message("The agent couldn't process this email.")
            )
            return
        payload = struct_pb2.Struct()
        payload.update(json.loads(json.dumps(summary(result, record), default=str)))
        await updater.add_artifact(parts=[Part(data=struct_pb2.Value(struct_value=payload))], name="guest_email_result")
        await updater.update_status(state=TaskState.TASK_STATE_COMPLETED, message=new_text_message("Draft ready."))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Cancel is not supported: one email takes a few seconds.")


class BearerAuth(BaseHTTPMiddleware):
    """Every call except the public agent card needs `Authorization: Bearer <A2A_TOKEN>` (constant-time compare)."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request, call_next):
        if request.url.path == CARD_PATH:
            return await call_next(request)
        given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        if not self.token or not hmac.compare_digest(given.encode(), self.token.encode()):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


def create_app(token: str, url: str = "http://127.0.0.1:9100", process=None) -> Starlette:
    card = agent_card(url)
    handler = DefaultRequestHandler(
        agent_executor=GuestEmailExecutor(process), task_store=InMemoryTaskStore(), agent_card=card
    )
    app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")])
    app.add_middleware(BearerAuth, token=token)
    return app


def main() -> None:  # pragma: no cover - a server process
    import uvicorn

    token = os.getenv("A2A_TOKEN", "")
    if not token:
        raise SystemExit("Set A2A_TOKEN (a long random value the calling agent also has).")
    port = int(os.getenv("A2A_PORT", "9100"))
    uvicorn.run(create_app(token, os.getenv("A2A_PUBLIC_URL", f"http://127.0.0.1:{port}")), host="0.0.0.0", port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
