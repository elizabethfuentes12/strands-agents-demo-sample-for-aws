"""Demo 09 — Agents as Tools: hierarchical orchestration.

A concierge orchestrator delegates to specialist agents wrapped as tools.
Unlike Swarm (peer handoffs) or Graph (fixed pipeline), here ONE agent owns
the conversation and calls the others like functions. Use case: a support
desk with specialized departments.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from models import make_bedrock_model, resolve_model_id, CLAUDE_MODEL_ID

import demo_events as ev
import guardrails
from streaming import stream_agent_events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo09")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

ORCHESTRATOR_PROMPT = """You are the front-desk concierge of an AWS demo booth. \
Delegate every question to the right specialist tool: aws_expert for AWS/cloud \
questions, agents_expert for AI-agent/Strands questions, event_guide for \
questions about the booth or event. Synthesize their answer briefly in the \
user's language. Always use at least one specialist."""

POLICY = guardrails.Policy(topic="specialist agents used as tools")

app = BedrockAgentCoreApp()

_agent = None
_current_session = None
_current_model = None


def _specialist(name: str, prompt: str, model_id: str) -> Agent:
    return Agent(
        name=name,
        model=make_bedrock_model(model_id),
        system_prompt=prompt,
        callback_handler=None,
    )


def _get_agent(session_id: str, model_id: str) -> Agent:
    global _agent, _current_session, _current_model
    if _agent is None or _current_session != session_id or _current_model != model_id:
        aws_expert = _specialist(
            "aws_expert",
            "You are an AWS solutions architect. Answer cloud/AWS questions in 2-3 sentences.",
            model_id,
        )
        agents_expert = _specialist(
            "agents_expert",
            "You are a Strands Agents specialist. Answer AI-agent questions in 2-3 sentences.",
            model_id,
        )
        event_guide = _specialist(
            "event_guide",
            "You are the event guide. This booth showcases Strands Agents demos: "
            "agent loop, structured output, security hooks, human-in-the-loop, "
            "observability, multi-agent patterns, and token optimization. Answer in 2 sentences.",
            model_id,
        )
        _agent = Agent(
            model=make_bedrock_model(model_id),
            system_prompt=ORCHESTRATOR_PROMPT,
            tools=[
                aws_expert.as_tool(description="AWS and cloud architecture questions"),
                agents_expert.as_tool(description="AI agents and Strands framework questions"),
                event_guide.as_tool(description="Questions about this booth, demos, or the event"),
            ],
            callback_handler=None,
        )
        _current_session = session_id
        _current_model = model_id
    return _agent


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

    agent = _get_agent(session_id, model_id)
    try:
        async for event in stream_agent_events(agent, prompt):
            yield json.dumps(event)
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
