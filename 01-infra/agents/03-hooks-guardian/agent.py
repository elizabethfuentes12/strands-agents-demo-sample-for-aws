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
from models import make_bedrock_model, resolve_model_id

import demo_events as ev
import guardrails
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

# Attack demo: visitors are meant to try adversarial prompts, so scope /
# jailbreak / extraction rules are OFF here. Only the abuse brakes stay on.
POLICY = guardrails.Policy(
    topic="the security hooks demo",
    block_offtopic=False,
    block_extraction=False,
    block_jailbreak=False,
)

app = BedrockAgentCoreApp()

_agent = None
_guardian = None
_current_session = None
_current_model = None


def _get_agent(session_id: str, model_id: str):
    global _agent, _guardian, _current_session, _current_model
    if _agent is None or _current_session != session_id or _current_model != model_id:
        _guardian = GuardianHook()
        _agent = Agent(
            model=make_bedrock_model(model_id),
            system_prompt=SYSTEM_PROMPT,
            tools=[check_order_status, refund_payment, send_email_blast, delete_database],
            hooks=[_guardian],
            callback_handler=None,
        )
        _current_session = session_id
        _current_model = model_id
    return _agent, _guardian


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

    agent, guardian = _get_agent(session_id, model_id)
    try:
        async for event in stream_agent_events(agent, prompt, drain=guardian.drain):
            yield json.dumps(event)
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
