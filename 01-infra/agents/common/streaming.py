"""Shared translation: Strands stream_async events -> demo event protocol.

Also separates model reasoning from user-facing text: Nova emits
``<thinking>...</thinking>`` inline in the data stream; that content is
captured and emitted as `reasoning` events (the UI attaches them to the
current cycle card) instead of chat tokens.
"""
import time

import demo_events as ev

_OPEN, _CLOSE = "<thinking>", "</thinking>"


class _ThinkingSplitter:
    """Streaming state machine that splits chat text from <thinking> blocks."""

    def __init__(self) -> None:
        self.pending = ""
        self.thinking = ""
        self.in_thinking = False

    def feed(self, text: str) -> list:
        """Returns a list of ('token'|'reasoning', text) tuples ready to emit."""
        out = []
        self.pending += text
        while True:
            if self.in_thinking:
                idx = self.pending.find(_CLOSE)
                if idx == -1:
                    # Hold back any partial "</thinking" prefix at the tail so a
                    # close tag split across chunks is still detected next feed.
                    keep = 0
                    for n in range(min(len(_CLOSE) - 1, len(self.pending)), 0, -1):
                        if _CLOSE.startswith(self.pending[-n:]):
                            keep = n
                            break
                    self.thinking += self.pending[: len(self.pending) - keep]
                    self.pending = self.pending[len(self.pending) - keep:]
                    break
                self.thinking += self.pending[:idx]
                self.pending = self.pending[idx + len(_CLOSE):]
                out.append(("reasoning", self.thinking.strip()))
                self.thinking = ""
                self.in_thinking = False
            else:
                idx = self.pending.find(_OPEN)
                if idx == -1:
                    # Hold back any partial "<thinking" prefix at the tail.
                    keep = 0
                    for n in range(min(len(_OPEN) - 1, len(self.pending)), 0, -1):
                        if _OPEN.startswith(self.pending[-n:]):
                            keep = n
                            break
                    emit = self.pending[: len(self.pending) - keep]
                    self.pending = self.pending[len(self.pending) - keep:]
                    if emit:
                        out.append(("token", emit))
                    break
                if idx > 0:
                    out.append(("token", self.pending[:idx]))
                self.pending = self.pending[idx + len(_OPEN):]
                self.in_thinking = True
        return out

    def flush(self) -> list:
        out = []
        if self.in_thinking and (self.thinking or self.pending):
            out.append(("reasoning", (self.thinking + self.pending).strip()))
        elif self.pending:
            out.append(("token", self.pending))
        self.pending = self.thinking = ""
        self.in_thinking = False
        return out

    def restart(self, in_thinking: bool = False) -> None:
        """Reset state for a new segment (e.g. a new agent-loop cycle)."""
        self.pending = self.thinking = ""
        self.in_thinking = in_thinking


async def stream_agent_events(agent, prompt, drain=None, **stream_kwargs):
    """Yield demo-protocol dicts from a Strands agent stream.

    drain: optional callable returning a list of extra events to interleave
    (used by hook-based demos to surface blocks as they happen).
    """
    cycle = 0
    tool_started_at = {}
    tool_names = {}
    splitter = _ThinkingSplitter()
    # Nova streams its answer through the native reasoning channel, opening with
    # implicit thinking (no <thinking> tag) and closing with </thinking>; the
    # text AFTER that close tag is the user-facing answer.
    # Claude (and other models) use explicit reasoningText events — their data
    # channel carries plain user-facing text, not thinking blocks.
    # Only pre-arm the splitter for Nova-style implicit thinking.
    _model_id = ""
    try:
        _model_id = agent.model.config.get("model_id", "") if hasattr(agent, "model") else ""
    except Exception:  # nosec B110
        pass
    _nova_reasoning = "nova" in _model_id.lower()
    reasoning_splitter = _ThinkingSplitter()
    reasoning_splitter.in_thinking = _nova_reasoning

    _last_state = None

    async for event in agent.stream_async(prompt, **stream_kwargs):
        if drain:
            for extra in drain():
                yield extra
        if event.get("start_event_loop"):
            # Close out the previous cycle's reasoning before starting a new one.
            for kind, chunk in reasoning_splitter.flush():
                yield ev.token(chunk) if kind == "token" else {"type": "reasoning", "cycle": cycle, "text": chunk}
            reasoning_splitter.restart(in_thinking=_nova_reasoning)
            cycle += 1
            _last_state = None
            yield ev.cycle_start(cycle)
            if "thinking" != _last_state:
                _last_state = "thinking"
                yield {"type": "agent_state", "cycle": cycle, "state": "thinking"}
        elif event.get("reasoning") and event.get("reasoningText"):
            # Native reasoning events from explicit-reasoning models (e.g. Claude).
            # Nova uses implicit thinking via </thinking> tags and is handled by
            # the pre-armed reasoning_splitter. For all other models, the SDK
            # already separates thinking (reasoningText) from answer (data), so
            # every reasoningText chunk is reasoning — no splitter needed.
            if "thinking" != _last_state:
                _last_state = "thinking"
                yield {"type": "agent_state", "cycle": cycle, "state": "thinking"}
            if _nova_reasoning:
                for kind, chunk in reasoning_splitter.feed(event["reasoningText"]):
                    yield ev.token(chunk) if kind == "token" else {"type": "reasoning", "cycle": cycle, "text": chunk}
            elif event["reasoningText"]:
                yield {"type": "reasoning", "cycle": cycle, "text": event["reasoningText"]}
        elif "data" in event:
            if "responding" != _last_state:
                _last_state = "responding"
                yield {"type": "agent_state", "cycle": cycle, "state": "responding"}
            for kind, chunk in splitter.feed(event["data"]):
                yield ev.token(chunk) if kind == "token" else {"type": "reasoning", "cycle": cycle, "text": chunk}
        elif "current_tool_use" in event and event["current_tool_use"].get("name"):
            tool_use = event["current_tool_use"]
            tool_id = tool_use.get("toolUseId")
            if tool_id and tool_id not in tool_started_at:
                tool_started_at[tool_id] = time.time()
                tool_names[tool_id] = tool_use["name"]
                if "calling_tools" != _last_state:
                    _last_state = "calling_tools"
                    yield {"type": "agent_state", "cycle": cycle, "state": "calling_tools"}
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
            # Flush reasoning_splitter as tokens: if we reach the result and
            # reasoning_splitter still has content, it means Nova answered via
            # the data channel (not reasoningText) while the splitter was still
            # in in_thinking=True from the last restart — that content is the
            # user-facing answer, not internal reasoning.
            for kind, chunk in reasoning_splitter.flush():
                yield ev.token(chunk)
            for kind, chunk in splitter.flush():
                yield ev.token(chunk) if kind == "token" else {"type": "reasoning", "cycle": cycle, "text": chunk}
            yield ev.metrics_from_result(event["result"])
    if drain:
        for extra in drain():
            yield extra
