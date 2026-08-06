"""Pure-logic tests for the chaos + resilience hooks (no model, no AWS).

Simulates the AfterToolCallEvent the Strands tool executor would pass, and
asserts:
- ChaosHook corrupts the FIRST climate_summary result exactly once.
- ResilienceHook detects the physically impossible value and requests a retry.
- On the (post-chaos) retry, the real value passes through untouched.

Run: python test_hooks.py   (or: pytest test_hooks.py)
"""
import json
import types

from hooks import CORRUPT_TEMP_C, ChaosHook, ResilienceHook


class _FakeAfterEvent:
    """Minimal stand-in for strands.hooks.AfterToolCallEvent."""

    def __init__(self, tool_name: str, payload: dict):
        self.tool_use = {"name": tool_name}
        self.result = {
            "toolUseId": "t1",
            "status": "success",
            "content": [{"text": json.dumps(payload)}],
        }
        self.exception = None
        self.retry = False


def _text(event) -> dict:
    return json.loads(event.result["content"][0]["text"])


def test_chaos_corrupts_first_climate_result_once():
    chaos = ChaosHook()
    real = {"avg_temp_c": 17.5, "total_precip_mm": 462.5, "source": "open-meteo-archive"}

    e1 = _FakeAfterEvent("climate_summary", real)
    chaos._corrupt_result(e1)
    assert _text(e1)["avg_temp_c"] == CORRUPT_TEMP_C, "first result should be corrupted"

    # Second call in the same turn must NOT be corrupted (one-shot).
    e2 = _FakeAfterEvent("climate_summary", real)
    chaos._corrupt_result(e2)
    assert _text(e2)["avg_temp_c"] == 17.5, "second result should pass through"


def test_chaos_ignores_other_tools():
    chaos = ChaosHook()
    e = _FakeAfterEvent("wikipedia_summary", {"avg_temp_c": 17.5})
    chaos._corrupt_result(e)
    assert _text(e)["avg_temp_c"] == 17.5


def test_resilience_retries_on_corruption():
    resilience = ResilienceHook()
    e = _FakeAfterEvent("climate_summary", {"avg_temp_c": CORRUPT_TEMP_C})
    resilience._recover(e)
    assert e.retry is True, "impossible temperature must trigger a retry"


def test_resilience_passes_sane_value():
    resilience = ResilienceHook()
    e = _FakeAfterEvent("climate_summary", {"avg_temp_c": 17.5})
    resilience._recover(e)
    assert e.retry is False, "a sane temperature must not trigger a retry"


def test_resilience_retries_on_error_status():
    resilience = ResilienceHook()
    e = _FakeAfterEvent("climate_summary", {"avg_temp_c": 17.5})
    e.result["status"] = "error"
    resilience._recover(e)
    assert e.retry is True, "an errored tool result must trigger a retry"


def test_end_to_end_two_rounds():
    """Round 1 (chaos only) reports garbage; round 2 (resilience+chaos) recovers."""
    real = {"avg_temp_c": 17.5, "total_precip_mm": 462.5, "source": "open-meteo-archive"}

    # Round 1: only chaos. The corrupted value survives (no harness).
    chaos1 = ChaosHook()
    e = _FakeAfterEvent("climate_summary", dict(real))
    chaos1._corrupt_result(e)
    assert _text(e)["avg_temp_c"] == CORRUPT_TEMP_C
    # No resilience hook -> retry stays False -> agent sees the garbage.
    assert e.retry is False

    # Round 2: chaos + resilience. Reverse callback order => chaos runs first.
    chaos2 = ChaosHook()
    resilience = ResilienceHook()
    first = _FakeAfterEvent("climate_summary", dict(real))
    chaos2._corrupt_result(first)          # chaos corrupts (runs first on After)
    resilience._recover(first)             # resilience sees corruption
    assert first.retry is True, "harness must request a retry"

    # The retry re-runs the tool; chaos is one-shot, so the real value returns.
    retry_result = _FakeAfterEvent("climate_summary", dict(real))
    chaos2._corrupt_result(retry_result)   # one-shot guard: no corruption now
    resilience._recover(retry_result)
    assert _text(retry_result)["avg_temp_c"] == 17.5
    assert retry_result.retry is False, "clean value must pass through"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and isinstance(v, types.FunctionType)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as exc:
            print(f"FAIL  {t.__name__}: {exc}")
    print(f"\n{passed}/{len(tests)} tests passed")
    raise SystemExit(0 if passed == len(tests) else 1)
