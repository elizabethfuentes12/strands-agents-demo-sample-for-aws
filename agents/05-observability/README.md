# 05 · Agent X-Ray

A travel agent instrumented to the bone: business attributes, per-tool latency, and a ground-truth ledger.

## What it shows

This observability demo makes an agent's internals visible three ways: the live trace tree (agent, cycles, model and tool calls), business attributes tagged from a hook, and a ground-truth ledger that shows what the agent SAYS versus what was ACTUALLY recorded. The teaching point: you cannot trust an agent's narration of its own actions. You need independent instrumentation and a source of truth to verify what really happened.

On AgentCore, the OpenTelemetry (OTEL) traces this agent emits also flow automatically to CloudWatch GenAI Observability. This demo surfaces the same story to booth visitors in the panel.

## How it works

A single Strands `Agent` (see `agent.py`) runs on AgentCore Runtime with a `BedrockModel` (default `us.amazon.nova-pro-v1:0`, overridable via `MODEL_ID`). It is created with `trace_attributes={"session.id": session_id}` so traces carry the session, and it wires three tools plus one hook.

### Tools (`tools.py`)

- `search_flights(origin, destination, date)`: returns three simulated offers and records each offer id and price in an in-memory `_OFFERS` map.
- `get_weather(city)`: simulated forecast.
- `book_flight(offer_id)`: an anti-hallucination guard means only an offer id that a prior search actually returned can be booked; unknown ids return an error. Successful bookings are appended to the `_BOOKINGS` ledger.
- `query_bookings()`: not a model tool. It is called by the entrypoint and the hook to read the ledger (the ground truth).

### The business-attribute hook (`agent.py`)

`TagVipBookings` is a Strands `HookProvider` that subscribes to `AfterToolCallEvent`. After each `book_flight` call it reads the ledger, takes the most recent booking, and queues a `business_attr` event with `business.booking_amount_usd`, `business.vip_booking` (true when the price is at or above `VIP_THRESHOLD_USD` of $200), and `business.booking_id`. This is the "business observability" layer: domain attributes derived from what actually happened, not from the model's text. Queued events are surfaced through the `drain` callback passed to `stream_agent_events`.

### Ground truth

After the turn completes, the entrypoint calls `query_bookings()` and emits a `ground_truth` event with the real ledger, so the UI can compare it against whatever the agent claimed in its answer.

## Files

- `agent.py`: agent, `TagVipBookings` hook, `trace_attributes`, and the entrypoint that emits ground truth.
- `tools.py`: the travel tools plus the `_BOOKINGS` ledger and `query_bookings`.
- `requirements.txt`: `bedrock-agentcore`, `strands-agents[otel]`, `strands-agents-tools`, `aws-opentelemetry-distro`.

## Events emitted

Via `stream_agent_events`, the hook drain, and the entrypoint:

- `cycle_start`, `reasoning`, `token`, `tool_call_start`, `tool_result`, `metrics`: the standard loop events (see demo 01), which build the live trace tree and per-tool latency.
- `business_attr`: `{type, attrs}` with the VIP booking attributes from the hook.
- `ground_truth`: `{type, bookings}`, the real ledger read after the turn.
- `error` / `done`.

## Run it

Deployed as its own AgentCore Runtime (stack `StrandsDemo05Stack`). From the repo root:

```bash
python scripts/smoke_test.py observability "Find a flight from Bogota to Lima on 2026-09-01 and book the cheapest one."
```

Watch the trace tree build, a `business_attr` card appear if the booking clears the VIP threshold, and the `ground_truth` ledger confirm what was actually booked.
