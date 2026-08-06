"""Demo 08 — Graph: deterministic multi-agent pipeline.

Unlike a Swarm (agents decide handoffs), a Graph fixes the execution path:
    brainstormer ──► fact_checker ──► editor
                └──► critic ────────────┘
The UI animates the DAG. Use case: content pipeline where order matters.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

import demo_events as ev
import guardrails

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo08")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")
CLAUDE_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

POLICY = guardrails.Policy(topic="a multi-agent graph pipeline")

app = BedrockAgentCoreApp()

GRAPH_EDGES = [
    ["brainstormer", "fact_checker"],
    ["brainstormer", "critic"],
    ["fact_checker", "editor"],
    ["critic", "editor"],
]


def _build_graph(model_id: str):
    model = BedrockModel(model_id=model_id)
    brainstormer = Agent(
        name="brainstormer",
        model=model,
        system_prompt="Generate 3 short, creative angles on the user's topic. Bullet points only.",
        callback_handler=None,
    )
    fact_checker = Agent(
        name="fact_checker",
        model=model,
        system_prompt="Review the ideas you receive: flag anything factually doubtful in one line each.",
        callback_handler=None,
    )
    critic = Agent(
        name="critic",
        model=model,
        system_prompt="Critique the ideas you receive: which is strongest and why, in 2 lines.",
        callback_handler=None,
    )
    editor = Agent(
        name="editor",
        model=model,
        system_prompt=(
            "You receive ideas, fact-check notes, and a critique. Write the final short "
            "paragraph (3-4 sentences) in the user's language."
        ),
        callback_handler=None,
    )
    builder = GraphBuilder()
    for agent in (brainstormer, fact_checker, critic, editor):
        builder.add_node(agent, agent.name)
    builder.add_edge("brainstormer", "fact_checker")
    builder.add_edge("brainstormer", "critic")
    builder.add_edge("fact_checker", "editor")
    builder.add_edge("critic", "editor")
    builder.set_entry_point("brainstormer")
    return builder.build()


@app.entrypoint
async def invoke(payload, context=None):
    payload = payload or {}
    prompt = payload.get("prompt", "")
    model_id = payload.get("model", MODEL_ID)
    if model_id not in (MODEL_ID, CLAUDE_MODEL_ID):
        model_id = MODEL_ID
    session_id = getattr(context, "session_id", None) or "local"
    if not prompt:
        yield json.dumps(ev.error("Empty prompt"))
        yield json.dumps(ev.done())
        return

    verdict = guardrails.check(prompt, POLICY, session_id=session_id)
    if verdict.blocked:
        for event in guardrails.blocked_events(verdict):
            yield json.dumps(event)
        return

    graph = _build_graph(model_id)
    # Tell the UI the topology up front so it can draw the DAG.
    yield json.dumps({"type": "graph_topology", "edges": GRAPH_EDGES})
    current_node = None
    try:
        async for event in graph.stream_async(prompt):
            etype = event.get("type")
            if etype == "multiagent_node_start":
                current_node = event.get("node_id", "?")
                yield json.dumps({"type": "node_start", "node": current_node})
            elif etype == "multiagent_node_stream":
                inner = event.get("event", {})
                if "data" in inner and current_node == "editor":
                    yield json.dumps(ev.token(inner["data"]))
            elif etype == "multiagent_node_stop":
                yield json.dumps({"type": "node_stop", "node": event.get("node_id", "?")})
            elif etype == "multiagent_result":
                result = event.get("result")
                if result is not None:
                    nodes = {}
                    for node_id, node_result in getattr(result, "results", {}).items():
                        try:
                            usage = node_result.result.metrics.accumulated_usage
                            nodes[node_id] = {"total_tokens": usage.get("totalTokens", 0)}
                        except AttributeError:
                            nodes[node_id] = {}
                    yield json.dumps({"type": "swarm_metrics", "nodes": nodes,
                                      "node_history": [e[0] for e in GRAPH_EDGES],
                                      "status": str(getattr(result, "status", ""))})
    except Exception:
        logger.exception("Graph invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
