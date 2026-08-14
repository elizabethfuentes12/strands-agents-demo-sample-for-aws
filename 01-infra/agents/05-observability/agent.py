"""Demo 05 — Agent X-Ray (observability).

The travel agent instrumented to the bone:
- span events building a live trace tree (agent -> cycle -> model/tool),
- business attributes tagged from an AfterToolCallEvent hook (VIP bookings),
- ground truth: what the agent SAYS vs what the ledger RECORDS.
On AgentCore, OTEL traces also flow automatically to CloudWatch GenAI
Observability — this demo makes the same story visible to booth visitors.
"""
import json
import logging
import os
import threading

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry
from models import make_bedrock_model, resolve_model_id

import demo_events as ev
import guardrails
from streaming import stream_agent_events
from tools import book_flight, get_weather, query_bookings, search_flights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo05")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")
VIP_THRESHOLD_USD = 200.0

SYSTEM_PROMPT = """You are a travel assistant in a demo. Search flights, check \
weather, and book flights when asked. Book the cheapest matching offer without \
asking for confirmation (it's a simulation). Keep answers short. Reply in the \
user's language."""

POLICY = guardrails.Policy(topic="a travel assistant with full observability")

app = BedrockAgentCoreApp()


class TagVipBookings(HookProvider):
    """Business observability: tag bookings above the VIP threshold."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.pending: list = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._tag)

    def drain(self) -> list:
        with self._lock:
            events, self.pending = self.pending, []
            return events

    def _tag(self, event: AfterToolCallEvent) -> None:
        if event.tool_use.get("name") != "book_flight":
            return
        bookings = query_bookings()
        if not bookings:
            return
        last = bookings[-1]
        with self._lock:
            self.pending.append(
                {
                    "type": "business_attr",
                    "attrs": {
                        "business.booking_amount_usd": last["price_usd"],
                        "business.vip_booking": last["price_usd"] >= VIP_THRESHOLD_USD,
                        "business.booking_id": last["id"],
                    },
                }
            )


_agent = None
_hook = None
_current_session = None
_current_model = None


def _get_agent(session_id: str, model_id: str):
    global _agent, _hook, _current_session, _current_model
    if _agent is None or _current_session != session_id or _current_model != model_id:
        _hook = TagVipBookings()
        _agent = Agent(
            model=make_bedrock_model(model_id),
            system_prompt=SYSTEM_PROMPT,
            tools=[search_flights, get_weather, book_flight],
            hooks=[_hook],
            callback_handler=None,
            trace_attributes={"session.id": session_id},
        )
        _current_session = session_id
        _current_model = model_id
    return _agent, _hook


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

    agent, hook = _get_agent(session_id, model_id)
    try:
        async for event in stream_agent_events(agent, prompt, drain=hook.drain):
            yield json.dumps(event)
        # Ground truth after the turn: the ledger, read independently of
        # whatever the agent claimed in its answer.
        yield json.dumps({"type": "ground_truth", "bookings": query_bookings()})
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
