"""Demo 06 — Live Swarm.

Three specialized agents (researcher -> analyst -> writer) collaborate on the
visitor's question. Handoffs and per-node activity stream to the UI as
`handoff` and `node` events so the graph can animate.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from models import make_bedrock_model, resolve_model_id
from strands.multiagent import Swarm

import demo_events as ev
import guardrails
from streaming import _ThinkingSplitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo06")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

POLICY = guardrails.Policy(topic="how a multi-agent swarm collaborates")

app = BedrockAgentCoreApp()


def _build_swarm(model_id: str) -> Swarm:
    model = make_bedrock_model(model_id)
    researcher = Agent(
        name="researcher",
        model=model,
        system_prompt=(
            "You are the RESEARCHER in a 3-agent team. Gather the key facts about "
            "the user's question from your own knowledge (3-5 bullet points). Then hand "
            "off to the analyst. Never answer the user directly."
        ),
        callback_handler=None,
    )
    analyst = Agent(
        name="analyst",
        model=model,
        system_prompt=(
            "You are the ANALYST in a 3-agent team. Take the researcher's facts, find "
            "the 2-3 most important insights and trade-offs. Then hand off to the writer. "
            "Never answer the user directly."
        ),
        callback_handler=None,
    )
    writer = Agent(
        name="writer",
        model=model,
        system_prompt=(
            "You are the WRITER in a 3-agent team. Turn the analyst's insights into a "
            "short, friendly answer (3-5 sentences) in the user's language."
        ),
        callback_handler=None,
    )
    return Swarm(
        [researcher, analyst, writer],
        entry_point=researcher,
        max_handoffs=6,
        max_iterations=10,
    )


def _node_metrics(result) -> dict:
    """Aggregate per-node token usage from a SwarmResult."""
    nodes = {}
    for node_id, node_result in getattr(result, "results", {}).items():
        try:
            usage = node_result.result.metrics.accumulated_usage
            nodes[node_id] = {
                "input_tokens": usage.get("inputTokens", 0),
                "output_tokens": usage.get("outputTokens", 0),
                "total_tokens": usage.get("totalTokens", 0),
            }
        except AttributeError:
            nodes[node_id] = {}
    return nodes


@app.entrypoint
async def invoke(payload, context=None):
    payload = payload or {}
    prompt = payload.get("prompt", "")
    model_id = resolve_model_id(payload.get("model"))
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

    swarm = _build_swarm(model_id)
    current_node = None
    _nova_reasoning = "nova" in model_id.lower()
    writer_splitter = _ThinkingSplitter()
    writer_splitter.in_thinking = _nova_reasoning
    try:
        async for event in swarm.stream_async(prompt):
            etype = event.get("type")
            if etype == "multiagent_node_start":
                current_node = event.get("node_id", "?")
                writer_splitter.restart(in_thinking=_nova_reasoning)
                yield json.dumps({"type": "node_start", "node": current_node})
            elif etype == "multiagent_node_stream":
                inner = event.get("event", {})
                # Only stream the writer's text to the chat; other nodes work
                # behind the scenes (their activity shows in the graph).
                if "data" in inner and current_node == "writer":
                    for kind, chunk in writer_splitter.feed(inner["data"]):
                        if kind == "token":
                            yield json.dumps(ev.token(chunk))
            elif etype == "multiagent_handoff":
                for src in event.get("from_node_ids", []):
                    for dst in event.get("to_node_ids", []):
                        yield json.dumps(ev.handoff(src, dst))
            elif etype == "multiagent_result":
                result = event.get("result")
                if result is not None:
                    yield json.dumps(
                        {
                            "type": "swarm_metrics",
                            "nodes": _node_metrics(result),
                            "node_history": [
                                getattr(n, "node_id", str(n))
                                for n in getattr(result, "node_history", [])
                            ],
                            "status": str(getattr(result, "status", "")),
                        }
                    )
    except Exception:
        logger.exception("Swarm invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
