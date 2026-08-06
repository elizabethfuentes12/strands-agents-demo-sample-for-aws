"""Demo 04 — Human-in-the-loop.

The travel agent searches flights on its own but FREEZES before booking:
`book_flight` raises an interrupt and the UI shows Approve/Reject buttons.
The response arrives as a new invocation on the same session; the cached
agent resumes exactly where it stopped.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

import demo_events as ev
import guardrails
from streaming import stream_agent_events
from tools import book_flight, search_flights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo04")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")
CLAUDE_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

SYSTEM_PROMPT = """You are a travel booking assistant in a demo. Search flights \
when asked, pick the best (cheapest) option, and book it with book_flight — do \
not ask the user for permission yourself; the booking tool has its own human \
approval step built in. Keep answers short. Reply in the user's language."""

POLICY = guardrails.Policy(topic="booking flights with human-in-the-loop approval")

app = BedrockAgentCoreApp()

_agent = None
_current_session = None
_current_model = None


def _get_agent(session_id: str, model_id: str) -> Agent:
    global _agent, _current_session, _current_model
    if _agent is None or _current_session != session_id or _current_model != model_id:
        _agent = Agent(
            model=BedrockModel(model_id=model_id),
            system_prompt=SYSTEM_PROMPT,
            tools=[search_flights, book_flight],
            callback_handler=None,
        )
        _current_session = session_id
        _current_model = model_id
    return _agent


def _interrupt_events(result) -> list:
    events = []
    for interrupt in result.interrupts:
        events.append(
            {
                "type": "interrupt",
                "id": interrupt.id,
                "name": interrupt.name,
                "reason": interrupt.reason,
            }
        )
    return events


@app.entrypoint
async def invoke(payload, context=None):
    payload = payload or {}
    model_id = payload.get("model", MODEL_ID)
    if model_id not in (MODEL_ID, CLAUDE_MODEL_ID):
        model_id = MODEL_ID
    session_id = getattr(context, "session_id", None) or "local"
    agent = _get_agent(session_id, model_id)

    # A turn is either a fresh prompt or a response to a pending interrupt.
    interrupt_response = payload.get("interrupt_response")
    if interrupt_response:
        prompt = [
            {
                "interruptResponse": {
                    "interruptId": interrupt_response["id"],
                    "response": interrupt_response["response"],
                }
            }
        ]
    else:
        prompt = payload.get("prompt", "")
        if not prompt:
            yield json.dumps(ev.error("Empty prompt"))
            yield json.dumps(ev.done())
            return
        verdict = guardrails.check(prompt, POLICY, session_id=session_id)
        if verdict.blocked:
            for event in guardrails.blocked_events(verdict):
                yield json.dumps(event)
            return

    try:
        result_holder = {}

        async def stream():
            async for event in agent.stream_async(prompt):
                if "result" in event:
                    result_holder["result"] = event["result"]
                yield event

        # Reuse the shared translator by wrapping the raw stream.
        import time

        cycle = 0
        tool_started_at = {}
        tool_names = {}
        async for event in stream():
            if event.get("start_event_loop"):
                cycle += 1
                yield json.dumps(ev.cycle_start(cycle))
            elif "data" in event:
                yield json.dumps(ev.token(event["data"]))
            elif "current_tool_use" in event and event["current_tool_use"].get("name"):
                tool_use = event["current_tool_use"]
                tool_id = tool_use.get("toolUseId")
                if tool_id and tool_id not in tool_started_at:
                    tool_started_at[tool_id] = time.time()
                    tool_names[tool_id] = tool_use["name"]
                    yield json.dumps(ev.tool_call_start(tool_use["name"], tool_use.get("input")))
            elif "message" in event:
                message = event["message"]
                if isinstance(message, dict) and message.get("role") == "user":
                    for block in message.get("content", []):
                        rb = block.get("toolResult") if isinstance(block, dict) else None
                        if rb:
                            tid = rb.get("toolUseId")
                            dur = (
                                round((time.time() - tool_started_at[tid]) * 1000)
                                if tid in tool_started_at
                                else None
                            )
                            text_out = " ".join(
                                c.get("text", "") for c in rb.get("content", []) if isinstance(c, dict)
                            )[:500]
                            yield json.dumps(
                                ev.tool_result(tool_names.get(tid, "unknown"), text_out, dur)
                            )

        result = result_holder.get("result")
        if result is not None:
            if str(getattr(result, "stop_reason", "")) == "interrupt":
                for ie in _interrupt_events(result):
                    yield json.dumps(ie)
            else:
                yield json.dumps(ev.metrics_from_result(result))
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
