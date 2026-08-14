"""Demo 07 — Stop Wasting Tokens.

Runs the SAME question against two agents: naive (raw logs into context) vs
memory-pointer (agent.state + ~50-token pointer). Emits `comparison` with both
token counts so the UI can render the side-by-side meters.
"""
import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from models import make_bedrock_model, resolve_model_id

import demo_events as ev
import guardrails
from tools import analyze_stored_logs, fetch_logs_pointer, naive_fetch_logs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo07")

MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-pro-v1:0")

BASE_PROMPT = (
    "You are an SRE assistant. Answer briefly (2-3 sentences) in the user's language."
)

POLICY = guardrails.Policy(topic="token optimization for agents")

app = BedrockAgentCoreApp()


def _usage(result) -> dict:
    usage = result.metrics.accumulated_usage
    return {
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "total_tokens": usage.get("totalTokens", 0),
    }


@app.entrypoint
async def invoke(payload, context=None):
    payload = payload or {}
    prompt = payload.get("prompt", "") or (
        "Analyze the last 3 hours of logs: which service has the most errors?"
    )
    model_id = resolve_model_id(payload.get("model"))
    session_id = getattr(context, "session_id", None) or "local"

    verdict = guardrails.check(prompt, POLICY, session_id=session_id)
    if verdict.blocked:
        for event in guardrails.blocked_events(verdict):
            yield json.dumps(event)
        return

    model = make_bedrock_model(model_id)
    try:
        # Round 1: naive agent — raw logs flood the context.
        yield json.dumps({"type": "phase", "phase": "naive"})
        naive_agent = Agent(
            model=model,
            system_prompt=BASE_PROMPT + " Use naive_fetch_logs to get the data.",
            tools=[naive_fetch_logs],
            callback_handler=None,
        )
        naive_result = await naive_agent.invoke_async(prompt)
        naive = _usage(naive_result)
        yield json.dumps({"type": "phase_result", "phase": "naive", **naive})

        # Round 2: pointer agent — logs live in agent.state, not the context.
        yield json.dumps({"type": "phase", "phase": "pointer"})
        pointer_agent = Agent(
            model=model,
            system_prompt=BASE_PROMPT
            + " Use fetch_logs_pointer then analyze_stored_logs to get the data.",
            tools=[fetch_logs_pointer, analyze_stored_logs],
            callback_handler=None,
        )
        pointer_result = await pointer_agent.invoke_async(prompt)
        pointer = _usage(pointer_result)
        yield json.dumps({"type": "phase_result", "phase": "pointer", **pointer})

        reduction = 0.0
        if naive["total_tokens"]:
            reduction = 100 * (1 - pointer["total_tokens"] / naive["total_tokens"])
        yield json.dumps(
            {
                "type": "comparison",
                "naive": naive,
                "pointer": pointer,
                "reduction_pct": round(reduction, 1),
            }
        )
        answer = str(pointer_result)
        yield json.dumps(ev.token(answer))
        yield json.dumps(ev.metrics_from_result(pointer_result))
    except Exception:
        logger.exception("Comparison failed")
        yield json.dumps(ev.error("The agent hit an error. Please try again."))
    yield json.dumps(ev.done())


if __name__ == "__main__":
    app.run()
