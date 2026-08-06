# Agents

One directory per demo, each a self-contained [Strands Agents](https://strandsagents.com/) app that runs on its own [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html).

Every numbered folder (`01-agent-loop` through `11-chaos-resilience`) is a single demo with its own runtime, deployed as its own CloudFormation stack by the CDK app in [`infra/`](../infra/). This gives each demo fault isolation: if one breaks, the others keep working (see the [root README](../README.md)). The `common/` folder holds the shared event protocol every agent speaks.

## The 11 demos

| Demo | Category | What you see | Strands feature |
|------|----------|--------------|-----------------|
| [01 · Live Agent Loop](./01-agent-loop/) | Fundamentals | The Reason to Tool to Respond loop animating in real time, with per-tool latency and token metrics | Tools, streaming, `result.metrics` |
| [02 · Structured Output](./02-structured-output/) | Fundamentals | Free text becomes a validated, typed record, field by field | `structured_output_model` + Pydantic |
| [03 · Hooks: the Guardian](./03-hooks-guardian/) | Safety & Control | Visitors try to talk the agent into dangerous actions; hooks block them with visible cards | `BeforeToolCallEvent`, `cancel_tool` |
| [04 · Human-in-the-loop](./04-human-in-the-loop/) | Safety & Control | The agent searches flights alone but freezes before booking; you approve or reject | `tool_context.interrupt()` |
| [05 · Agent X-Ray](./05-observability/) | Observability | A travel agent instrumented to the bone: business attributes, per-tool latency, ground-truth ledger | OTEL traces, `trace_attributes`, hooks |
| [06 · Live Swarm](./06-swarm/) | Multi-agent | Researcher to analyst to writer collaborating, with animated handoffs and per-agent token cost | `Swarm`, multi-agent streaming |
| [07 · Stop Wasting Tokens](./07-token-optimization/) | Context engineering | The same question, two agents: ~27k tokens vs ~1.4k on live meters | `agent.state`, `@tool(context=True)` |
| [08 · Graph Pipeline](./08-graph/) | Multi-agent | A deterministic DAG: brainstormer to (fact-checker + critic) to editor | `GraphBuilder`, parallel nodes |
| [09 · Agents as Tools](./09-agents-as-tools/) | Multi-agent | A concierge delegates to specialist agents called like functions | `agent.as_tool()` |
| [10 · Memory Poisoning](./10-memory-poisoning/) | Safety & Control | Plant a malicious note in turn 1, trigger it in turn 2; the tool boundary blocks exfiltration | `agent.state`, pure-function gate |
| [11 · Chaos Testing](./11-chaos-resilience/) | Safety & Control | The same question runs twice under injected chaos; a hook catches the impossible value and retries | `AfterToolCallEvent`, `event.retry` |

## Common shape of an agent folder

Every demo directory contains at least:

- `agent.py`: the entrypoint. Present in all 11 demos.
- `requirements.txt`: the agent's dependencies, installed as ARM64 wheels into the deployment package. Present in all 11 demos.

Most, but not all, demos also include:

- `tools.py`: the demo's tool functions. Present in 01, 03, 04, 05, 07, 10, 11.
- `hooks.py`: hook classes for demos built around hooks. Present in 03 and 11.

A few demos add their own local tests: `test_gate.py` (demo 10) and `test_hooks.py` (demo 11). Demos 02, 06, 08, and 09 define their logic entirely in `agent.py` and need no `tools.py`. Each folder also has a built `deployment_package.zip` (produced by [`scripts/create_deployment_package.sh`](../scripts/create_deployment_package.sh)) and a `__pycache__`.

### What `agent.py` looks like

Every entrypoint follows the same shape. Taking [`03-hooks-guardian/agent.py`](./03-hooks-guardian/agent.py) as the reference:

- It creates a `BedrockAgentCoreApp()` and decorates an async `invoke(payload, context=None)` function with `@app.entrypoint`.
- It reads the model id from `MODEL_ID` (default `us.amazon.nova-pro-v1:0`) and builds a Strands `Agent` with a `system_prompt` and `tools`.
- The agent is cached per session and rebuilt when `context.session_id` changes, so multi-turn conversations reuse the same AgentCore session and keep their memory.
- It reads `prompt` from the payload, streams demo-protocol events by delegating to `stream_agent_events(...)` from [`common/streaming.py`](./common/), and JSON-encodes each event before yielding it.
- It emits an `error` event on failure and always ends with a `done` event.

## The shared protocol

The typed event protocol and the Strands-to-protocol streaming translator live in [`common/`](./common/). Those two files (`demo_events.py` and `streaming.py`) are copied into every agent's deployment package at build time, which is why agents import them by module name. See [`common/README.md`](./common/README.md) for the full list of event types and how streaming works.
