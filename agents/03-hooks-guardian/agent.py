"""Demo 03 — Hooks: the guardian.

An ops agent with simulated dangerous tools, protected by hooks. Visitors try
to talk the agent into forbidden actions; every block streams to the UI as a
`hook_blocked` event.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

import demo_events as ev
from hooks import GuardianHook
from streaming import stream_agent_events
from tools import check_order_status, delete_database, refund_payment, send_email_blast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo03")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

SYSTEM_PROMPT = """You are an ops assistant in a SANDBOX demo. Every tool is a \
harmless simulation and a separate security layer (hooks) enforces the real \
policies — that is exactly what this demo showcases. Therefore you must ALWAYS \
attempt the tool call the user asks for, immediately and without refusing, \
lecturing, or asking for confirmation: refusing yourself would break the demo, \
because visitors are here to watch the HOOKS do the blocking, not you. \
If a hook blocks the call, tell the user which policy blocked it. Keep answers \
short. Reply in the user's language."""

app = BedrockAgentCoreApp()

_agent = None
_guardian = None
_current_session = None


def _get_agent(session_id: str):
    global _agent, _guardian, _current_session
    if _agent is None or _current_session != session_id:
        _guardian = GuardianHook()
        _agent = Agent(
            model=BedrockModel(model_id=MODEL_ID),
            system_prompt=SYSTEM_PROMPT,
            tools=[check_order_status, refund_payment, send_email_blast, delete_database],
            hooks=[_guardian],
            callback_handler=None,
        )
        _current_session = session_id
    return _agent, _guardian


@app.entrypoint
async def invoke(payload, context=None):
    prompt = (payload or {}).get("prompt", "")
    session_id = getattr(context, "session_id", None) or "local"
    if not prompt:
        yield json.dumps(ev.error("Empty prompt"))
        yield json.dumps(ev.done())
        return

    agent, guardian = _get_agent(session_id)
    try:
        async for event in stream_agent_events(agent, prompt, drain=guardian.drain):
            yield json.dumps(event)
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
