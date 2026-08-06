# 01 · Live Agent Loop

The Reason to Tool to Respond loop animating in real time, with per-tool latency and token metrics.

## What it shows

This is the fundamentals demo. It makes the core Strands agent loop visible: the agent reasons, decides to call a tool, gets a result, and either loops again or answers. Each pass through the loop is a "cycle", and the Insights panel draws one card per cycle so visitors can watch the model think, act, and respond step by step.

## How it works

A single Strands `Agent` (see `agent.py`) runs on Amazon Bedrock AgentCore Runtime. It is built with a `BedrockModel` whose id comes from the `MODEL_ID` environment variable. When deployed by this stack that variable is set to `us.amazon.nova-pro-v1:0` (see `infra/stacks/demo_stack.py`), the same model every demo uses. The agent has three tools:

- `calculator` (built-in, from `strands_tools`)
- `current_time` (built-in, from `strands_tools`)
- `aws_service_lookup` (custom, defined in `tools.py`)

The agent is cached per AgentCore `session_id` inside the microVM (`_get_agent`), so the same conversation keeps its message history across turns. A new session starts a fresh agent with empty memory.

The entrypoint (`@app.entrypoint invoke`) calls the shared helper `stream_agent_events(agent, prompt)` from `agents/common/streaming.py`. That helper consumes `agent.stream_async(...)` and translates raw Strands stream events into the typed demo event protocol (`agents/common/demo_events.py`). It also runs a `_ThinkingSplitter` that separates any inline `<thinking>...</thinking>` content from user-facing text, emitting the former as `reasoning` events attached to the current cycle.

### The custom tool

`aws_service_lookup(service_name)` is a tiny offline catalog (`tools.py`). It normalizes the input (lowercase, strips `amazon`/`aws` prefixes) and returns a one-line description for a known service such as `bedrock`, `agentcore`, `lambda`, `s3`, `dynamodb`, `appsync`, or `amplify`. It needs no network call, so the demo stays fast and self-contained.

## Files

- `agent.py`: the Strands agent, system prompt, tool wiring, and AgentCore entrypoint.
- `tools.py`: the `aws_service_lookup` custom tool and its static catalog.
- `requirements.txt`: `bedrock-agentcore`, `strands-agents[otel]`, `strands-agents-tools`, `aws-opentelemetry-distro`.

## Events emitted

Via `stream_agent_events` and `demo_events.py`:

- `cycle_start`: a new loop iteration begins (`start_event_loop`).
- `reasoning`: model thinking, attached to the current cycle.
- `token`: user-facing chat text (rendered in the chat pane).
- `tool_call_start`: a tool is invoked, with its name and input.
- `tool_result`: the tool returned, with truncated output and `duration_ms`.
- `metrics`: final tally (cycles, input/output/total tokens, duration, per-tool call counts) built from the Strands `AgentResult.metrics`.
- `error` / `done`: failure message and end-of-stream marker.

## Run it

Deployed as its own AgentCore Runtime by the CDK app (stack `StrandsDemo01Stack`). To exercise it end to end from the repo root:

```bash
python scripts/smoke_test.py agent-loop "What is 23*47?"
```

Try prompts like "What is Amazon Bedrock?", "What time is it?", or a mix that forces multiple tool calls in one turn to watch several cycles animate.
