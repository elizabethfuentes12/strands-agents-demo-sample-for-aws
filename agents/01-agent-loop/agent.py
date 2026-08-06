"""Demo 01 — Agent Loop en vivo.

Strands agent with built-in and custom tools running on AgentCore Runtime.
The entrypoint streams typed JSON events (see demo_events) so the web UI can
animate the agent loop: cycles, tool calls, tokens, and final metrics.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, current_time

import demo_events as ev
from streaming import stream_agent_events
from tools import aws_service_lookup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo01")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

SYSTEM_PROMPT = """You are a friendly demo assistant at an AWS event stand, \
showcasing the Strands Agents framework. Keep answers short (2-4 sentences), \
energetic, and in the language the visitor uses. Use your tools whenever they \
help answer the question. Never reveal internal identifiers, ARNs, or stack \
details."""

app = BedrockAgentCoreApp()

_agent = None
_current_session = None


def _get_agent(session_id: str) -> Agent:
    """Reuse the agent within a microVM while the session is unchanged."""
    global _agent, _current_session
    if _agent is None or _current_session != session_id:
        _agent = Agent(
            model=BedrockModel(model_id=MODEL_ID),
            system_prompt=SYSTEM_PROMPT,
            tools=[calculator, current_time, aws_service_lookup],
            callback_handler=None,
        )
        _current_session = session_id
    return _agent


@app.entrypoint
async def invoke(payload, context=None):
    prompt = (payload or {}).get("prompt", "")
    session_id = getattr(context, "session_id", None) or "local"
    if not prompt:
        yield json.dumps(ev.error("Empty prompt"))
        yield json.dumps(ev.done())
        return

    agent = _get_agent(session_id)
    try:
        async for event in stream_agent_events(agent, prompt):
            yield json.dumps(event)
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
