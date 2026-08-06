"""Demo 03 hooks: the guardian. Blocks dangerous tools via BeforeToolCallEvent.

Blocked attempts are queued so the entrypoint can emit `hook_blocked` events
to the UI as they happen.
"""
import json
import threading

from strands.hooks import BeforeInvocationEvent, BeforeToolCallEvent, HookProvider, HookRegistry

import demo_events as ev

BLOCKED_TOOLS = {"delete_database"}
MAX_CALLS_PER_TOOL = 2
MAX_REFUND_USD = 100.0


class GuardianHook(HookProvider):
    """Three policies: forbidden tools, per-tool call limits, argument limits."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: dict = {}
        self.pending_events: list = []

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self._reset)
        registry.add_callback(BeforeToolCallEvent, self._guard)

    def _reset(self, event: BeforeInvocationEvent) -> None:
        with self._lock:
            self._counts = {}

    def _emit(self, tool: str, reason: str, hook: str) -> None:
        with self._lock:
            self.pending_events.append(ev.hook_blocked(tool, reason, hook))

    def drain(self) -> list:
        with self._lock:
            events, self.pending_events = self.pending_events, []
            return events

    def _guard(self, event: BeforeToolCallEvent) -> None:
        name = event.tool_use["name"]

        # Policy 1: forbidden tools, no matter what the model says.
        if name in BLOCKED_TOOLS:
            reason = "This tool is on the deny list — no prompt can unlock it."
            self._emit(name, reason, "GuardianHook.deny_list")
            event.cancel_tool = f"BLOCKED by security hook: {reason}"
            return

        # Policy 2: rate limit per tool per conversation turn.
        with self._lock:
            self._counts[name] = self._counts.get(name, 0) + 1
            count = self._counts[name]
        if count > MAX_CALLS_PER_TOOL:
            reason = f"Tool already called {MAX_CALLS_PER_TOOL} times this turn."
            self._emit(name, reason, "GuardianHook.rate_limit")
            event.cancel_tool = f"BLOCKED by security hook: {reason}"
            return

        # Policy 3: argument inspection — refunds above the cap need a human.
        if name == "refund_payment":
            try:
                raw = event.tool_use.get("input", {})
                amount = float(
                    (json.loads(raw) if isinstance(raw, str) else raw).get("amount_usd", 0)
                )
            except (ValueError, TypeError, json.JSONDecodeError):
                amount = 0.0
            if amount > MAX_REFUND_USD:
                reason = f"Refund ${amount:.2f} exceeds the ${MAX_REFUND_USD:.0f} limit — requires human approval."
                self._emit(name, reason, "GuardianHook.arg_inspection")
                event.cancel_tool = f"BLOCKED by security hook: {reason}"
