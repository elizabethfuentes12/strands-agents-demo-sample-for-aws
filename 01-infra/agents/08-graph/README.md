# 08 · Graph Pipeline

A deterministic multi-agent DAG: a brainstormer feeds a fact-checker and a critic in parallel, and both feed an editor that writes the final paragraph. The UI animates the graph as each node runs.

## What it shows

A Graph fixes the execution path up front, unlike a Swarm where the agents decide their own handoffs. The topology is code, not a model decision, so the order is reproducible: useful for a content pipeline where the steps must happen in a set sequence. The parallel branch (fact-checker and critic both consuming the brainstormer's output) shows that independent nodes can run at the same time before their results converge on the editor.

## Strands SDK feature

- `strands.multiagent.GraphBuilder`: `add_node`, `add_edge`, `set_entry_point`, `build`.
- `graph.stream_async(prompt)`, which yields multi-agent lifecycle events (`multiagent_node_start`, `multiagent_node_stream`, `multiagent_node_stop`, `multiagent_result`).
- Per-node token usage read from each node result's `metrics.accumulated_usage`.

## How it works

`agent.py` builds four `Agent` instances, each with its own system prompt:

- **brainstormer**: generates 3 short creative angles on the topic (entry point).
- **fact_checker**: flags anything factually doubtful, one line each.
- **critic**: says which idea is strongest and why, in 2 lines.
- **editor**: receives the ideas, the fact-check notes, and the critique, and writes the final 3-4 sentence paragraph in the user's language.

The edges are `brainstormer -> fact_checker`, `brainstormer -> critic`, `fact_checker -> editor`, `critic -> editor`. The entrypoint streams the graph and forwards node lifecycle events to the UI. Only the editor's streamed text is surfaced as chat `token` events; the upstream nodes are shown as graph activity, not chat.

## Files

- `agent.py`: builds the graph, streams it, and translates multi-agent events to the demo protocol.
- `requirements.txt`: `bedrock-agentcore`, `strands-agents[otel]`, `strands-agents-tools`, `aws-opentelemetry-distro`.

## Events emitted

- `graph_topology` (`{edges}`): sent first so the UI can draw the DAG before anything runs.
- `node_start` (`{node}`): a node began executing.
- `node_stop` (`{node}`): a node finished.
- `token`: streamed text, emitted only for the editor node so the chat shows just the final paragraph.
- `swarm_metrics` (`{nodes, node_history, status}`): per-node total token counts and the overall graph status, sent when the graph result arrives.
- `error`, `done`: standard lifecycle events.

## What the user sees

The insights pane draws the four-node graph and lights nodes up as they start and stop, including the two parallel middle nodes. The chat pane fills in only with the editor's final paragraph. Per-node token counts appear when the run completes.

## Run it

Deployed as its own AgentCore Runtime via the CDK app at the repository root (`StrandsDemo08Stack`). To exercise the full pipeline from the repo root:

```bash
python scripts/smoke_test.py graph "Write a short paragraph about serverless agents."
```
