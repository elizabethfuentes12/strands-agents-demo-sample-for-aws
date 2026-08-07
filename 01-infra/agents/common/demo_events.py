"""Typed event protocol shared by all demo agents.

Each agent entrypoint yields JSON objects (AgentCore streams them as SSE
``data:`` lines). The chat pane renders ``token`` events; the Insights pane
renders everything else.

Event types:
- token:            {type, text}
- cycle_start:      {type, cycle}
- tool_call_start:  {type, tool, input}
- tool_result:      {type, tool, output, duration_ms}
- hook_blocked:     {type, tool, reason, hook}
- agent_state:      {type, cycle, state}  # "thinking"|"calling_tools"|"responding"
- guardrail_blocked:{type, kind, reason}
- handoff:          {type, from_agent, to_agent}
- metrics:          {type, cycles, input_tokens, output_tokens, total_tokens,
                     duration_s, tools}
- error:            {type, message}
- done:             {type}
"""


def token(text: str) -> dict:
    return {"type": "token", "text": text}


def cycle_start(cycle: int) -> dict:
    return {"type": "cycle_start", "cycle": cycle}


def tool_call_start(tool: str, tool_input) -> dict:
    return {"type": "tool_call_start", "tool": tool, "input": tool_input}


def tool_result(tool: str, output, duration_ms: float | None = None) -> dict:
    return {"type": "tool_result", "tool": tool, "output": output, "duration_ms": duration_ms}


def hook_blocked(tool: str, reason: str, hook: str) -> dict:
    return {"type": "hook_blocked", "tool": tool, "reason": reason, "hook": hook}


def guardrail_blocked(kind: str, reason: str) -> dict:
    """An input guardrail refused the prompt before it reached the model."""
    return {"type": "guardrail_blocked", "kind": kind, "reason": reason}


def handoff(from_agent: str, to_agent: str) -> dict:
    return {"type": "handoff", "from_agent": from_agent, "to_agent": to_agent}


def error(message: str) -> dict:
    return {"type": "error", "message": message}


def done() -> dict:
    return {"type": "done"}


def metrics_from_result(result) -> dict:
    """Build a metrics event from a Strands AgentResult."""
    summary = result.metrics.get_summary()
    usage = summary.get("accumulated_usage", {})
    tools = {}
    for name, stats in summary.get("tool_usage", {}).items():
        exec_stats = stats.get("execution_stats", {})
        tools[name] = {
            "call_count": exec_stats.get("call_count", 0),
            "success_count": exec_stats.get("success_count", 0),
            "average_time_s": round(exec_stats.get("average_time", 0), 3),
        }
    return {
        "type": "metrics",
        "cycles": summary.get("total_cycles", 0),
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "total_tokens": usage.get("totalTokens", 0),
        "duration_s": round(summary.get("total_duration", 0), 2),
        "tools": tools,
    }
