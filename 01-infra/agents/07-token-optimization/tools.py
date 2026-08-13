"""Demo 07 tools: naive log fetching vs the memory-pointer pattern.

Adapted from stop-wasting-tokens-sample-for-aws (demo 01).
"""
import json
import random

from strands import tool

_seeded = random.Random(42)  # nosec B311 — deterministic demo dataset, not crypto


def _generate_logs(hours: int = 3) -> list:
    """Synthetic application logs: ~100 events/hour, noisy stack traces on errors."""
    logs = []
    for hour in range(hours):
        for i in range(100):
            level = _seeded.choices(["INFO", "WARN", "ERROR"], weights=[80, 12, 8])[0]
            entry = {
                "ts": f"2026-08-05T{10 + hour:02d}:{i % 60:02d}:00Z",
                "level": level,
                "service": _seeded.choice(["api", "auth", "payments", "search"]),
                "latency_ms": _seeded.randint(5, 2500),
                "message": f"request {hour * 100 + i} processed",
            }
            if level == "ERROR":
                entry["stack_trace"] = "\n".join(
                    f'  File "handler.py", line {_seeded.randint(10, 400)}, in step_{n}'
                    for n in range(15)
                )
            logs.append(entry)
    return logs


_LOGS = _generate_logs()


@tool
def naive_fetch_logs(hours: int) -> str:
    """Fetch raw application logs for the last N hours (returns EVERYTHING).

    Args:
        hours: How many hours of logs to fetch (1-3).
    """
    return json.dumps(_LOGS[: max(1, min(hours, 3)) * 100])


@tool(context=True)
def fetch_logs_pointer(hours: int, tool_context) -> str:
    """Fetch application logs for the last N hours; stores them out of context
    and returns only a summary pointer.

    Args:
        hours: How many hours of logs to fetch (1-3).
    """
    data = _LOGS[: max(1, min(hours, 3)) * 100]
    raw = json.dumps(data)
    tool_context.agent.state.set("logs", data)
    errors = sum(1 for e in data if e["level"] == "ERROR")
    slow = sum(1 for e in data if e["latency_ms"] > 2000)
    return (
        f"POINTER logs://last-{hours}h — {len(data)} events stored out of context "
        f"({len(raw):,} bytes). Summary: {errors} errors, {slow} slow requests. "
        "Use analyze_stored_logs to inspect."
    )


@tool(context=True)
def analyze_stored_logs(question: str, tool_context) -> str:
    """Analyze the logs previously stored by fetch_logs_pointer.

    Args:
        question: What to look for, e.g. "errors by service".
    """
    data = tool_context.agent.state.get("logs") or []
    if not data:
        return "No logs stored yet — call fetch_logs_pointer first."
    by_service: dict = {}
    for e in data:
        if e["level"] == "ERROR":
            by_service[e["service"]] = by_service.get(e["service"], 0) + 1
    worst = max(by_service, key=by_service.get) if by_service else "none"
    avg_latency = sum(e["latency_ms"] for e in data) / len(data)
    return (
        f"Analyzed {len(data)} stored events. Errors by service: {json.dumps(by_service)}. "
        f"Worst service: {worst}. Average latency: {avg_latency:.0f}ms."
    )
