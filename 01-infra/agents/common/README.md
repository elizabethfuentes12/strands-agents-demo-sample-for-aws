# common: the shared event protocol

The contract between every demo agent and the frontend: a small set of typed JSON events plus the streaming translator that produces them from a Strands agent run.

Each agent yields JSON objects that AgentCore streams back as SSE `data:` lines. The web app renders `token` events in the chat pane and everything else in the "under the hood" insights panel (see the [root README](../../README.md)). Because these two files define that shared shape, they are copied into every agent's deployment package at build time (by [`scripts/create_deployment_package.sh`](../../scripts/create_deployment_package.sh)), which is why agents `import demo_events` and `from streaming import ...` directly.

## Files

| File | What it provides |
|------|------------------|
| [`demo_events.py`](./demo_events.py) | The typed event protocol: builder functions for each event type, plus a metrics builder |
| [`streaming.py`](./streaming.py) | Translates Strands `stream_async` events into the demo event protocol |

## `demo_events.py`: the event protocol

Each helper returns a plain `dict` with a `type` field. The event types documented in the module and their builder functions:

| Event type | Builder | Fields |
|------------|---------|--------|
| `token` | `token(text)` | `text` |
| `cycle_start` | `cycle_start(cycle)` | `cycle` |
| `tool_call_start` | `tool_call_start(tool, tool_input)` | `tool`, `input` |
| `tool_result` | `tool_result(tool, output, duration_ms=None)` | `tool`, `output`, `duration_ms` |
| `hook_blocked` | `hook_blocked(tool, reason, hook)` | `tool`, `reason`, `hook` |
| `handoff` | `handoff(from_agent, to_agent)` | `from_agent`, `to_agent` |
| `error` | `error(message)` | `message` |
| `done` | `done()` | (none) |
| `metrics` | `metrics_from_result(result)` | `cycles`, `input_tokens`, `output_tokens`, `total_tokens`, `duration_s`, `tools` |

`metrics_from_result(result)` builds a `metrics` event from a Strands `AgentResult`. It calls `result.metrics.get_summary()` and pulls `accumulated_usage` (token counts) and `total_cycles` / `total_duration`, plus a per-tool breakdown (`call_count`, `success_count`, `average_time_s`) from `tool_usage`.

Some demos emit additional event types not defined here (for example a `reasoning` event added by `streaming.py`, and demo-specific ones such as `memory_state`, `swarm_metrics`, or `comparison` produced inside individual agents). `demo_events.py` covers the common core that all agents share.

## `streaming.py`: Strands stream to protocol

`stream_agent_events(agent, prompt, drain=None, **stream_kwargs)` is an async generator that iterates `agent.stream_async(...)` and yields demo-protocol dicts. It maps Strands stream events as follows:

- `start_event_loop` increments the cycle counter and yields `cycle_start`.
- Native reasoning events (`reasoning` + `reasoningText`) yield a `reasoning` event tagged with the current `cycle`.
- `data` chunks go through a thinking splitter (see below) and yield `token` and/or `reasoning` events.
- `current_tool_use` (with a name) yields `tool_call_start` the first time a given tool-use id is seen, and records the start time.
- `message` blocks with a `toolResult` yield `tool_result`, computing `duration_ms` from the recorded start time and truncating the output text to 500 characters.
- `result` flushes any pending text and yields the `metrics` event via `metrics_from_result`.

The optional `drain` callable is invoked around the loop; if provided it returns a list of extra events to interleave. Hook-based demos (03 and 11) pass a drain function so blocks surface as `hook_blocked` events as they happen.

### Thinking splitter

Amazon Nova emits `<thinking>...</thinking>` blocks inline in the data stream. `_ThinkingSplitter` is a small streaming state machine that separates that reasoning from user-facing chat text: content inside the tags becomes `reasoning` events (attached to the current cycle card in the UI), and everything else becomes `token` events. It correctly holds back a partial `<thinking` prefix that arrives split across chunks, and `flush()` emits whatever remains when the stream ends.
