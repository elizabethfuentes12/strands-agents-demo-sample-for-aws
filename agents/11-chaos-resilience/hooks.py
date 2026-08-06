"""Demo 11 hooks: chaos injection + a resilience harness that recovers from it.

The chaos is injected DETERMINISTICALLY (fires once per run) so the
Before/After contrast is reproducible at a booth:

- ChaosHook rewrites the FIRST climate_summary result to a physically
  impossible mean temperature (999 C) via AfterToolCallEvent.result. To the
  model this looks like just another number, so a naive agent reports it.
- ResilienceHook is the harness that "catches what the model can't": on
  AfterToolCallEvent it checks avg_temp_c against sane physical bounds and, when
  it is out of range (or the call errored), sets event.retry = True to re-run
  the tool. This is Strands' NATIVE tool retry, verified in
  strands/tools/executors/_executor.py (the retry loop honors after_event.retry
  on the normal and exception paths).

On the retry, ChaosHook's one-shot guard has already fired, so the tool returns
the real value and the harness lets it through.

Design notes verified against the installed SDK:
- AfterToolCallEvent can only write `result` and `retry` (its _can_write).
- AfterToolCallEvent uses reverse callback order (should_reverse_callbacks).
  We register ResilienceHook FIRST and ChaosHook SECOND so that on After events
  ChaosHook runs first (corrupts) and ResilienceHook runs after (sees it).
- cancel_tool is terminal (retry is NOT honored after a cancel), so chaos is
  injected as a corrupted result, never as a cancel.

Round 1 (no harness) uses hooks=[chaos]; Round 2 uses hooks=[resilience, chaos].
"""
import json
import threading

from strands.hooks import (
    AfterToolCallEvent,
    BeforeInvocationEvent,
    HookProvider,
    HookRegistry,
)

CHAOS_TOOL = "climate_summary"
# A mean annual temperature outside these bounds is not physically plausible
# for any inhabited place -- the harness uses this to detect corruption.
SANE_TEMP_MIN_C = -40.0
SANE_TEMP_MAX_C = 45.0
CORRUPT_TEMP_C = 999.0


def _result_text(result) -> str:
    """Pull the text payload out of a Strands ToolResult (best effort)."""
    if not isinstance(result, dict):
        return ""
    parts = []
    for block in result.get("content", []) or []:
        if isinstance(block, dict) and "text" in block:
            parts.append(block["text"])
    return " ".join(parts)


def _set_result_text(result, new_text: str) -> None:
    if isinstance(result, dict):
        result["content"] = [{"text": new_text}]


class ChaosHook(HookProvider):
    """Injects a deterministic corrupted result, exactly once per turn."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._corrupt_done = False
        self.pending: list = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self._reset)
        registry.add_callback(AfterToolCallEvent, self._corrupt_result)

    def _reset(self, event: BeforeInvocationEvent) -> None:
        with self._lock:
            self._corrupt_done = False

    def _emit(self, effect: str, detail: str) -> None:
        with self._lock:
            self.pending.append(
                {"type": "chaos_injected", "tool": CHAOS_TOOL, "effect": effect, "detail": detail}
            )

    def drain(self) -> list:
        with self._lock:
            events, self.pending = self.pending, []
            return events

    def _corrupt_result(self, event: AfterToolCallEvent) -> None:
        if event.tool_use.get("name") != CHAOS_TOOL:
            return
        text = _result_text(event.result)
        if not text:
            return
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return
        if data.get("avg_temp_c") is None:
            return
        with self._lock:
            if self._corrupt_done:
                return
            self._corrupt_done = True
        data["avg_temp_c"] = CORRUPT_TEMP_C
        data["source"] = "CHAOS-corrupted"
        _set_result_text(event.result, json.dumps(data))
        self._emit("corrupted_result", f"avg_temp_c overwritten to {CORRUPT_TEMP_C} (injected).")


class ResilienceHook(HookProvider):
    """The harness that catches what the model can't: verifies + retries."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.pending: list = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._recover)

    def _emit(self, action: str, detail: str) -> None:
        with self._lock:
            self.pending.append(
                {"type": "recovered", "tool": CHAOS_TOOL, "action": action, "detail": detail}
            )

    def drain(self) -> list:
        with self._lock:
            events, self.pending = self.pending, []
            return events

    def _recover(self, event: AfterToolCallEvent) -> None:
        if event.tool_use.get("name") != CHAOS_TOOL:
            return

        # If the tool errored outright, retry it (native Strands retry).
        result = event.result
        if event.exception is not None or (
            isinstance(result, dict) and result.get("status") == "error"
        ):
            event.retry = True
            self._emit("retry", "Tool errored -> retrying (native Strands retry).")
            return

        # Present but physically impossible value -> corruption caught, retry.
        text = _result_text(result)
        if not text:
            return
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return
        temp = data.get("avg_temp_c")
        if isinstance(temp, (int, float)) and not (SANE_TEMP_MIN_C <= temp <= SANE_TEMP_MAX_C):
            event.retry = True
            self._emit(
                "verify_retry",
                f"avg_temp_c={temp} is physically impossible -> retrying.",
            )
