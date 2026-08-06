# 04 · Human-in-the-loop

The agent searches flights on its own but freezes before booking; you approve or reject.

## What it shows

This safety and control demo puts a human checkpoint inside the agent loop. The travel agent searches flights on its own, then freezes right before the irreversible action (booking) and waits for a person to approve or reject. The teaching point: a tool can pause the entire agent, hand control to a human, and then resume exactly where it stopped once the decision comes back.

## How it works

A single Strands `Agent` (see `agent.py`) runs on AgentCore Runtime with a `BedrockModel` (default `us.amazon.nova-pro-v1:0`, overridable via `MODEL_ID`) and two tools from `tools.py`:

- `search_flights(origin, destination, date)`: returns three simulated offers.
- `book_flight(offer_id, price_usd, tool_context)`: declared with `@tool(context=True)` so it receives the Strands `tool_context`. Instead of booking immediately, it calls `tool_context.interrupt("booking-approval", reason={...})`. This pauses the whole agent loop and surfaces an interrupt with the offer id and price.

### The pause and resume flow

The system prompt tells the agent to book the cheapest option without asking for permission itself, because the booking tool has the human-approval step built in.

The entrypoint (`agent.py`) handles two kinds of turn:

- A fresh `prompt`: normal search-then-book attempt. If the run ends with `stop_reason == "interrupt"`, the entrypoint emits one `interrupt` event per pending interrupt (`_interrupt_events` reads `result.interrupts` for `id`, `name`, and `reason`) and the UI shows Approve/Reject buttons.
- An `interrupt_response` (id plus response) sent on the same AgentCore session. The entrypoint wraps it as a Strands `interruptResponse` message and streams it into the cached agent, which resumes from where `book_flight` paused. Inside the tool, an approval keyword (`y`, `yes`, `approve`, `approved`) confirms the booking; anything else returns a rejection.

Because the agent is cached per `session_id`, the resumed invocation reuses the exact loop state that was frozen.

This entrypoint streams the loop events inline (a small local translator) rather than through the shared `stream_agent_events` helper, so it can inspect `stop_reason` and route between metrics and interrupts.

## Files

- `agent.py`: agent, interrupt-aware entrypoint, and the resume path.
- `tools.py`: `search_flights` and the interrupt-raising `book_flight`.
- `requirements.txt`: `bedrock-agentcore`, `strands-agents[otel]`, `strands-agents-tools`, `aws-opentelemetry-distro`.

## Events emitted

- `cycle_start`: a new loop iteration.
- `token`: chat text.
- `tool_call_start`: a tool invocation with input.
- `tool_result`: tool output with `duration_ms`.
- `interrupt`: `{type, id, name, reason}`, the freeze that drives the Approve/Reject buttons.
- `metrics`: final tally when the turn completes without an interrupt.
- `error` / `done`.

## Run it

Deployed as its own AgentCore Runtime (stack `StrandsDemo04Stack`). From the repo root:

```bash
python scripts/smoke_test.py human-in-the-loop "Book me a flight from Madrid to Lisbon on 2026-09-01."
```

The agent searches, freezes at `book_flight`, and waits. Approve or reject in the UI to see it resume and either confirm or cancel the booking.
