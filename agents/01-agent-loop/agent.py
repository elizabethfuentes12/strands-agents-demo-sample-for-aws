"""Demo 01 — Agent Loop en vivo.

Strands agent with built-in and custom tools running on AgentCore Runtime.
The entrypoint streams typed JSON events (see demo_events) so the web UI can
animate the agent loop: cycles, tool calls, tokens, and final metrics.
"""
import json
import logging
import os
import time

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator, current_time

import demo_events as ev
from tools import aws_service_lookup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo01")

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

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
    cycle = 0
    tool_started_at: dict = {}
    tool_names: dict = {}

    try:
        async for event in agent.stream_async(prompt):
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
                    yield json.dumps(
                        ev.tool_call_start(tool_use["name"], tool_use.get("input"))
                    )
            elif "message" in event:
                message = event["message"]
                if isinstance(message, dict) and message.get("role") == "user":
                    for block in message.get("content", []):
                        result_block = block.get("toolResult") if isinstance(block, dict) else None
                        if result_block:
                            tool_id = result_block.get("toolUseId")
                            duration_ms = None
                            if tool_id in tool_started_at:
                                duration_ms = round(
                                    (time.time() - tool_started_at[tool_id]) * 1000
                                )
                            content = result_block.get("content", [])
                            text_out = " ".join(
                                c.get("text", "") for c in content if isinstance(c, dict)
                            )[:500]
                            yield json.dumps(
                                ev.tool_result(
                                    tool_names.get(tool_id, "unknown"),
                                    text_out,
                                    duration_ms,
                                )
                            )
            elif "result" in event:
                yield json.dumps(ev.metrics_from_result(event["result"]))
    except Exception:
        logger.exception("Agent invocation failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
