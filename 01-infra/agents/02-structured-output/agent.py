"""Demo 02 — Structured Output.

Free text in, validated Pydantic object out. The entrypoint emits a
`structured` event with the validated fields so the UI can render the schema
filling in, plus the usual metrics.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from pydantic import BaseModel, Field
from strands import Agent
from models import make_bedrock_model, resolve_model_id, CLAUDE_MODEL_ID

import demo_events as ev
import guardrails

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo02")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")


class EventLead(BaseModel):
    """Structured data extracted from a visitor's free-form introduction."""

    name: str | None = Field(None, description="Person's name if mentioned")
    company: str | None = Field(None, description="Company or organization")
    role: str | None = Field(None, description="Job role or title")
    interests: list[str] = Field(default_factory=list, description="Technical topics of interest")
    use_case: str | None = Field(None, description="The AI/agent use case they describe")
    cloud_experience: str | None = Field(
        None, description="Their cloud/AWS experience level: beginner, intermediate, or expert"
    )
    follow_up: str = Field(description="One-sentence suggested follow-up for the booth staff")


SYSTEM_PROMPT = """You extract structured lead data from what an event visitor \
writes about themselves. Be faithful to the text: never invent fields that are \
not mentioned — leave them null."""

POLICY = guardrails.Policy(topic="extracting your details into a structured lead")

app = BedrockAgentCoreApp()

# Conversation memory: Strands keeps the message history inside the Agent, and
# AgentCore keeps this process alive per sessionId (microVM). Reusing the agent
# for the same session = multi-turn memory. New sessionId = fresh conversation.
_agent = None
_current_session = None
_current_model = None


def _get_agent(session_id: str, model_id: str) -> Agent:
    global _agent, _current_session, _current_model
    if _agent is None or _current_session != session_id or _current_model != model_id:
        _agent = Agent(
            model=make_bedrock_model(model_id),
            system_prompt=SYSTEM_PROMPT,
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
        result = await agent.invoke_async(prompt, structured_output_model=EventLead)
        lead = result.structured_output
        yield json.dumps({"type": "structured", "fields": lead.model_dump()})
        summary = "Extracted a validated lead record — check the panel on the right. "
        if lead.name:
            summary = f"Nice to meet you, {lead.name}! " + summary
        yield json.dumps(ev.token(summary))
        yield json.dumps(ev.metrics_from_result(result))
    except Exception:
        logger.exception("Structured output failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
