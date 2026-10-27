"""The same agent as src/agent.py's manual loop, written as a LangGraph state graph (ORCHESTRATOR=langgraph).

    model ──(tool calls)──► tools ──(no draft yet, turns left)──► model
      │                       │
      └─(refusal / no tool)─► END   └─(draft received / step limit)──► END

Both orchestrations call the same functions for a model turn (`model_turn`), the stop check (`stop_reason_failure`)
and the tools (`run_tools`), so prompts, tools, guards, spans and the step timeline are identical. What differs is only
how the loop is expressed, which is what decision 27 compares: accuracy, p95, cost, code size and debuggability.
"""

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agent import model_turn, run_tools, stop_reason_failure
from src.config import MAX_AGENT_STEPS


class State(TypedDict):
    messages: list
    turn: int
    pending: list  # tool_use blocks from the last model turn
    final: Any  # DraftReplyInput once the model has drafted
    failure: str | None
    language_retries: int


def build(client, system: str, ctx, language: str, usage: dict, clock):
    def model(state: State) -> dict:
        turn = state["turn"] + 1
        response, tool_uses = model_turn(client, system, state["messages"], ctx, turn, usage, clock)
        failure = stop_reason_failure(response, tool_uses)
        if failure:
            return {"turn": turn, "failure": failure, "pending": []}
        messages = state["messages"] + [{"role": "assistant", "content": response.content}]
        return {"turn": turn, "messages": messages, "pending": tool_uses}

    def tools(state: State) -> dict:
        results, final, retries = run_tools(state["pending"], ctx, language, state["turn"], state["language_retries"])
        if final is not None:
            return {"final": final, "language_retries": retries, "pending": []}
        update = {"messages": state["messages"] + [{"role": "user", "content": results}], "language_retries": retries}
        if state["turn"] >= MAX_AGENT_STEPS:
            update["failure"] = "step_limit"
        return update

    def after_model(state: State) -> str:
        return END if state["failure"] else "tools"

    def after_tools(state: State) -> str:
        return END if state["final"] is not None or state["failure"] else "model"

    graph = StateGraph(State)
    graph.add_node("model", model)
    graph.add_node("tools", tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", after_model, ["tools", END])
    graph.add_conditional_edges("tools", after_tools, ["model", END])
    return graph.compile()


def run_graph(client, system: str, messages: list, ctx, language: str, usage: dict, clock):
    """Returns (final draft or None, failure or None), like run_loop."""
    app = build(client, system, ctx, language, usage, clock)
    start: State = {"messages": list(messages), "turn": 0, "pending": [], "final": None, "failure": None,
                    "language_retries": 0}  # fmt: skip
    out = app.invoke(start, {"recursion_limit": 2 * MAX_AGENT_STEPS + 4})
    return out["final"], out["failure"]
