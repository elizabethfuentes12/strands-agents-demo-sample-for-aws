"""Shared translation: Strands stream_async events -> demo event protocol."""
import time

import demo_events as ev


async def stream_agent_events(agent, prompt, drain=None, **stream_kwargs):
    """Yield demo-protocol dicts from a Strands agent stream.

    drain: optional callable returning a list of extra events to interleave
    (used by hook-based demos to surface blocks as they happen).
    """
    cycle = 0
    tool_started_at = {}
    tool_names = {}

    async for event in agent.stream_async(prompt, **stream_kwargs):
        if drain:
            for extra in drain():
                yield extra
        if event.get("start_event_loop"):
            cycle += 1
            yield ev.cycle_start(cycle)
        elif "data" in event:
            yield ev.token(event["data"])
        elif "current_tool_use" in event and event["current_tool_use"].get("name"):
            tool_use = event["current_tool_use"]
            tool_id = tool_use.get("toolUseId")
            if tool_id and tool_id not in tool_started_at:
                tool_started_at[tool_id] = time.time()
                tool_names[tool_id] = tool_use["name"]
                yield ev.tool_call_start(tool_use["name"], tool_use.get("input"))
        elif "message" in event:
            message = event["message"]
            if isinstance(message, dict) and message.get("role") == "user":
                for block in message.get("content", []):
                    result_block = block.get("toolResult") if isinstance(block, dict) else None
                    if result_block:
                        tool_id = result_block.get("toolUseId")
                        duration_ms = None
                        if tool_id in tool_started_at:
                            duration_ms = round((time.time() - tool_started_at[tool_id]) * 1000)
                        content = result_block.get("content", [])
                        text_out = " ".join(
                            c.get("text", "") for c in content if isinstance(c, dict)
                        )[:500]
                        yield ev.tool_result(
                            tool_names.get(tool_id, "unknown"), text_out, duration_ms
                        )
        elif "result" in event:
            yield ev.metrics_from_result(event["result"])
    if drain:
        for extra in drain():
            yield extra
