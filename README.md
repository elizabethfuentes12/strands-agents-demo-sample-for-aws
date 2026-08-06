# Strands Agents Demo Showcase

An interactive, event-booth-ready web app that shows off the [Strands Agents](https://strandsagents.com/) framework: a chat on the left, and a live **"under the hood" panel** on the right that visualizes what the agent is actually doing — cycles, tool calls, blocked actions, handoffs, and token usage — in real time.

Every demo runs on its own [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html), deployed with AWS CDK. The browser talks to the agents through [AWS AppSync Events](https://docs.aws.amazon.com/appsync/latest/eventapi/event-api-welcome.html) (serverless WebSockets) secured with Amazon Cognito.

> 💡 This sample uses Strands Agents. The same patterns are general agent concepts and carry over to other agent frameworks.
>
> ⚠️ This guide assumes familiarity with AWS CDK, Python, and TypeScript/React basics.

## Demos

| Demo | What you see | Strands feature |
|------|--------------|-----------------|
| [01 · Live Agent Loop](./agents/01-agent-loop/) | The Reason → Tool → Respond loop animating in real time, with per-tool latency and token metrics | Tools, streaming, `result.metrics` |
| [02 · Structured Output](./agents/02-structured-output/) | Free text becomes a validated, typed record — field by field | `structured_output_model` + Pydantic |
| [03 · Hooks: the Guardian](./agents/03-hooks-guardian/) | Visitors try to talk the agent into dangerous actions; hooks block them with visible 🔴 cards | `BeforeToolCallEvent`, `cancel_tool` |
| [06 · Live Swarm](./agents/06-swarm/) | Researcher → analyst → writer collaborating, with animated handoffs and per-agent token cost | `Swarm`, multi-agent streaming |
| [07 · Stop Wasting Tokens](./agents/07-token-optimization/) | The same question, two agents: 27k tokens vs 1.4k (−95%) on live meters | `agent.state`, `@tool(context=True)` |

Planned: 04 · Human-in-the-loop (interrupts) and 05 · Agent X-Ray (OpenTelemetry traces).

## Architecture

```
Browser (React SPA, Cognito JWT)
   │  publish prompt ──────────────► AppSync Events  inbox/<demo>/<session>
   │                                      │ direct Lambda integration (async)
   │                                      ▼
   │                              Dispatcher Lambda
   │                                      │ invoke_agent_runtime (session ≥33 chars,
   │                                      │ retries 424/429/500, read_timeout 900s)
   │                                      ▼
   │                              AgentCore Runtime (one per demo)
   │                                      │ typed JSON events (SSE)
   │  subscribe ◄────────────────  AppSync Events  out/<demo>/<session>
   ▼
Chat renders `token` events · Insights panel renders everything else
```

Key design decisions:

- **One runtime per demo** — fault isolation: if one demo breaks, the others keep working.
- **Typed event protocol** (`token`, `tool_call_start`, `hook_blocked`, `handoff`, `metrics`, …) with sequence numbers — AppSync fan-out doesn't guarantee ordering, the client reorders.
- **Code-based (ZIP on S3) runtimes** — no Docker builds; a full demo deploys in ~75 seconds.
- **Everything is `RemovalPolicy.DESTROY`** — `cdk destroy` leaves nothing behind.

## Quick Start

Prerequisites: an AWS account with Amazon Bedrock model access (Amazon Nova Pro by default), Python 3.11+, Node.js 20+, [uv](https://docs.astral.sh/uv/), AWS CDK v2.

```bash
# 1. Infra (all stacks: Cognito + AppSync Events + one stack per demo)
python3 -m venv .venv && source .venv/bin/activate
uv pip install -r infra/requirements.txt
cd infra && cdk deploy --all --require-approval never

# 2. Create the kiosk user
aws cognito-idp admin-create-user --user-pool-id <pool-id> --username kiosk --message-action SUPPRESS
aws cognito-idp admin-set-user-password --user-pool-id <pool-id> --username kiosk --password '<password>' --permanent

# 3. Web app (fill .env.local with the stack outputs)
cd ../web && npm install && npm run dev

# 4. Smoke test the full pipeline
python scripts/smoke_test.py agent-loop "What is 23*47?"
```

✅ If the smoke test prints `SMOKE TEST OK`, the whole pipeline (Cognito → AppSync → Lambda → AgentCore → back) works.

## Troubleshooting

- **Only `done` arrives, no agent text** → check the AgentCore runtime logs (`/aws/bedrock-agentcore/runtimes/...`). The most common cause is missing Bedrock model access in the account/region.
- **`RuntimeClientError` (424)** → cold microVM; the dispatcher retries with backoff automatically. After redeploying an agent, wait ~15 min or start a new session.
- **Events arrive out of order** → expected; the web client reorders by `seq` and skips gaps after 1.2 s.
- **UI shows "disconnected"** → the Cognito token expired (8 h validity); sign in again.

## Project layout

```
infra/     CDK app: base stack (Cognito, AppSync Events, dispatcher) + one stack per demo
agents/    One directory per demo + common/ (event protocol, streaming helpers)
web/       React + Vite SPA (chat, insights panel, EN/ES, Strands dark theme)
scripts/   deployment package builder + end-to-end smoke test
```

## Author

**Elizabeth Fuentes** — [LinkedIn](https://www.linkedin.com/in/lizfue/) · [GitHub](https://github.com/elizabethfuentes12)

---

## Contributing

Contributions are welcome! See [CONTRIBUTING](CONTRIBUTING.md) for more information.

---

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file for details.
