"""The LangGraph orchestration behaves like the manual loop on the same scripted model turns."""

import pytest
from fakes import FakeClient, draft, text, tool

import src.agent
from src import agent
from src.agent import Email

GUEST = Email("elena.marsh@example.com", "Dog", "Can we bring our dog?", "Elena Marsh")
SCRIPTS = {
    "search then draft": [[tool("search_policy", {"question": "pets"})], [draft("Dogs are welcome [P1].")]],
    "draft at once": [[draft("Thanks for writing, we'll check.")]],
    "no tool": [[text("Hello")]],
    "step limit": [[tool("search_policy", {"question": "pets"})]] * 6,
}


@pytest.fixture
def db(store, monkeypatch):
    from src.tools import ToolContext

    monkeypatch.setattr(src.agent, "ToolContext", lambda **kw: ToolContext(store=store, **kw))


def summary(result):
    return (result.outcome, result.fallback_reason, result.reply, result.api_calls,
            [(s.kind, s.name, s.ok) for s in result.steps])  # fmt: skip


@pytest.mark.parametrize("name", list(SCRIPTS))
def test_both_orchestrations_give_the_same_result(name, db, monkeypatch):
    results = {}
    for orchestrator in ("manual", "langgraph"):
        monkeypatch.setattr(agent, "ORCHESTRATOR", orchestrator)
        client = FakeClient([list(t) for t in SCRIPTS[name]])
        results[orchestrator] = summary(agent.run_agent(GUEST, "beach-resort", client=client))
    assert results["manual"] == results["langgraph"]


def test_langgraph_stops_at_the_step_limit(db, monkeypatch):
    monkeypatch.setattr(agent, "ORCHESTRATOR", "langgraph")
    result = agent.run_agent(GUEST, "beach-resort", client=FakeClient([list(t) for t in SCRIPTS["step limit"]]))
    assert result.fallback_reason == "step_limit" and result.api_calls == 6
