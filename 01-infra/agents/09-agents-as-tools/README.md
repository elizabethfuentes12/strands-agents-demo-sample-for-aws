# 09 · Agents as Tools

A front-desk concierge orchestrator delegates each question to a specialist agent that is wrapped and called like a function. One agent owns the conversation; the others are its tools.

## What it shows

Hierarchical orchestration. Unlike a Swarm (peer agents hand off to each other) or a Graph (a fixed pipeline), here a single orchestrator decides which specialist to call for a given question and synthesizes the reply. This maps to a support desk with specialized departments: the caller talks to one front desk, which routes to the right expert behind the scenes.

## Strands SDK feature

- `agent.as_tool(description=...)`: turns a whole `Agent` into a callable tool that the orchestrator can invoke like any other tool.
- Standard agent streaming via the shared `stream_agent_events` helper.

## How it works

`agent.py` defines three specialist agents, each a plain `Agent` with its own system prompt:

- **aws_expert**: AWS and cloud architecture questions.
- **agents_expert**: AI-agent and Strands framework questions.
- **event_guide**: questions about this booth, its demos, or the event.

Each specialist is passed to the orchestrator via `as_tool(...)` with a routing description. The orchestrator's system prompt instructs it to delegate every question to the right specialist and always use at least one before answering briefly in the user's language. The agent is cached per session (`_get_agent` rebuilds it when the `session_id` changes) so a conversation keeps its memory, and a new session starts fresh.

## Files

- `agent.py`: builds the specialists, wraps them as tools, orchestrates, and streams.
- `requirements.txt`: `bedrock-agentcore`, `strands-agents[otel]`, `strands-agents-tools`, `aws-opentelemetry-distro`.

## Events emitted

This demo streams through the shared `stream_agent_events` helper, so it emits the standard protocol:

- `cycle_start`: each reasoning cycle of the orchestrator.
- `tool_call_start` (`{tool, input}`): when the orchestrator calls a specialist, the tool name is the specialist's name (for example `aws_expert`), so the delegation is visible.
- `tool_result` (`{tool, output, duration_ms}`): the specialist's answer coming back.
- `reasoning`: model thinking captured from `<thinking>` blocks or native reasoning events.
- `token`: the orchestrator's synthesized answer, rendered in the chat pane.
- `metrics`: the final metrics summary (cycles, tokens, per-tool call stats).
- `error`, `done`: standard lifecycle events.

## What the user sees

The chat pane shows one concise answer from the concierge. The insights pane shows the orchestrator calling one or more named specialists as tools, with each specialist's returned answer and latency, making the routing visible.

## Run it

Deployed as its own AgentCore Runtime via the CDK app at the repository root (`StrandsDemo09Stack`). To exercise the full pipeline from the repo root:

```bash
python scripts/smoke_test.py agents-as-tools "What is Amazon Bedrock AgentCore?"
```
