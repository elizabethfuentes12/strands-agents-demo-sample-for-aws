"""Demo 11 — Chaos Testing / Resilience.

A travel agent backed by REAL keyless APIs (Open-Meteo, Wikipedia). A press of
the play button runs the SAME question twice under injected chaos:

- Round 1 (no harness): chaos corrupts a climate result; the agent reports the
  garbage (e.g. "avg temp 999 C") because the model can't tell it's wrong.
- Round 2 (with harness): the SAME chaos is injected, but a ResilienceHook
  verifies the value and triggers Strands' native tool retry, so the agent
  answers with the correct real data.

This mirrors the chaos-testing / diagnose-fix-validate idea (formalized by
Strands Evals' ChaosExperiment for offline suites); here it runs live so booth
visitors watch the harness catch what the model can't. The same resilience
patterns are general agent concepts and carry over to other agent frameworks.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from models import make_bedrock_model, resolve_model_id, CLAUDE_MODEL_ID

import demo_events as ev
import guardrails
from hooks import ChaosHook, ResilienceHook
from streaming import stream_agent_events
from tools import climate_summary, geocode_place, wikipedia_summary

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo11")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

SYSTEM_PROMPT = """You are a travel assistant in a demo. You have real tools: \
geocode_place (place -> coordinates), climate_summary (coordinates -> historical \
average temperature and precipitation), and wikipedia_summary (a place overview). \
To answer about a place's climate, first geocode it, then call climate_summary \
with those coordinates. Always report the numbers the tools return. Keep answers \
short (2-3 sentences) and reply in the user's language."""

DEFAULT_PROMPT = "What is the historical climate like in Lisbon?"

POLICY = guardrails.Policy(topic="chaos testing and agent resilience")

app = BedrockAgentCoreApp()

TOOLS = [geocode_place, climate_summary, wikipedia_summary]


async def _run_round(phase: str, prompt: str, hooks: list, drains: list, model_id: str):
    """Stream one round, interleaving chaos/resilience events via drains."""

    def drain_all():
        out = []
        for d in drains:
            out.extend(d())
        return out

    yield json.dumps({"type": "phase", "phase": phase})
    agent = Agent(
        model=make_bedrock_model(model_id),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        hooks=hooks,
        callback_handler=None,
    )
    async for event in stream_agent_events(agent, prompt, drain=drain_all):
        yield json.dumps(event)


@app.entrypoint
async def invoke(payload, context=None):
    payload = payload or {}
    prompt = payload.get("prompt", "") or DEFAULT_PROMPT
    model_id = resolve_model_id(payload.get("model"))
    session_id = getattr(context, "session_id", None) or "local"

    verdict = guardrails.check(prompt, POLICY, session_id=session_id)
    if verdict.blocked:
        for event in guardrails.blocked_events(verdict):
            yield json.dumps(event)
        return

    try:
        # Round 1: chaos only, no harness — the agent trusts the corrupted data.
        chaos1 = ChaosHook()
        async for e in _run_round("chaos_naive", prompt, [chaos1], [chaos1.drain], model_id):
            yield e

        # Round 2: same chaos, plus the resilience harness that recovers.
        # Register resilience FIRST so that on After events (reverse order) chaos
        # runs first and resilience sees the corruption.
        resilience = ResilienceHook()
        chaos2 = ChaosHook()
        async for e in _run_round(
            "chaos_resilient", prompt, [resilience, chaos2], [resilience.drain, chaos2.drain], model_id
        ):
            yield e
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
