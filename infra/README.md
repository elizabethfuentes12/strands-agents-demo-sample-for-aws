# infra: CDK app for the Strands Agents demo showcase

The AWS CDK app that deploys the backend for the demo showcase: shared authentication and messaging (Cognito, AppSync Events, a dispatcher Lambda) plus one [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) per demo.

This is one CDK app that synthesizes many CloudFormation stacks: a single `BaseStack` shared by everything, and one `DemoStack` for each entry in the `DEMOS` list. The public web hosting (S3 + CloudFront) is a separate CDK app under `../web-infra`, so the site can be deployed and torn down independently of the agent runtimes.

> This app is written with Strands Agents in mind, but the deployment pattern (one shared base stack plus one parameterized stack per unit of work) is a general CDK concept and carries over to other agent frameworks.

## What this app deploys

```
StrandsDemosBaseStack        Cognito + AppSync Events API + dispatcher Lambda (shared)
StrandsDemo01Stack           AgentCore Runtime for demo 01 (agent-loop)
StrandsDemo02Stack           AgentCore Runtime for demo 02 (structured-output)
...                          ...
StrandsDemo11Stack           AgentCore Runtime for demo 11 (chaos-resilience)
```

## One app, many stacks

The entrypoint is [`app.py`](./app.py). It creates one `BaseStack`, then loops over a `DEMOS` list and instantiates a `DemoStack` for each entry. See [`app.py:22-47`](./app.py):

- [`app.py:22`](./app.py): `base = BaseStack(app, "StrandsDemosBaseStack", env=env)` creates the single shared stack.
- [`app.py:24-36`](./app.py): `DEMOS` is a list of 11 dicts, each with `demo_id`, `slug`, and `agent_dir` (for example `{"demo_id": "01", "slug": "agent-loop", "agent_dir": "01-agent-loop"}`).
- [`app.py:38-47`](./app.py): the loop creates `DemoStack(app, f"StrandsDemo{demo['demo_id']}Stack", ...)` for each entry and calls `stack.add_dependency(base)`, so every demo stack waits for the base stack to deploy first.

The result: `cdk deploy --all` produces 12 stacks (1 base + 11 demos). Adding a demo is a one-line addition to the `DEMOS` list; no new CDK file is needed.

The `env` is built from `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION` (defaulting the region to `us-east-1`), see [`app.py:17-20`](./app.py).

## BaseStack: shared auth and messaging

Defined in [`stacks/base_stack.py`](./stacks/base_stack.py). It creates:

- **Amazon Cognito user pool** (`strands-demos`) and a web client. Self sign-up is disabled (it is meant for a single kiosk credential), password minimum length is 12, and access/id tokens are valid for 8 hours. See [`base_stack.py:31-46`](./stacks/base_stack.py).
- **Dispatcher Lambda** (`strands-demos-dispatcher`), Python 3.12, 512 MB, 5 minute timeout, code from [`lambdas/dispatcher`](./lambdas/dispatcher). Its role is granted `bedrock-agentcore:InvokeAgentRuntime` / `InvokeAgentRuntimeForUser` and `ssm:GetParameter` on `/strands-demos/*`. See [`base_stack.py:48-76`](./stacks/base_stack.py).
- **AppSync Events API** (`strands-demos-events`) with two auth providers: Cognito user pool (used for connection, publish, and subscribe defaults) and an API key (used by the dispatcher to publish to the `out` channel). See [`base_stack.py:78-108`](./stacks/base_stack.py). Note: the API key is set to expire after 365 days, so it must be rotated on redeploy.
- **Two channel namespaces**:
  - `inbox`: the browser publishes prompts here (Cognito auth). It has a direct Lambda integration to the dispatcher with `lambda_invoke_type=EVENT` (asynchronous invoke). See [`base_stack.py:112-125`](./stacks/base_stack.py).
  - `out`: the dispatcher publishes agent events here using the API key; the browser subscribes with its Cognito JWT. See [`base_stack.py:127-136`](./stacks/base_stack.py).
- **SSM parameters** under the `/strands-demos` prefix: the Events API key, the Cognito user pool id and client id, and the Events HTTP and realtime domains. These are also emitted as CloudFormation outputs so the deploy script and the web app can read them. See [`base_stack.py:137-162`](./stacks/base_stack.py).

The dispatcher receives two environment variables: `EVENTS_HTTP_DOMAIN` (the Events API HTTP DNS) and `SSM_PREFIX`. See [`base_stack.py:145-146`](./stacks/base_stack.py).

## DemoStack: one AgentCore Runtime per demo

Defined in [`stacks/demo_stack.py`](./stacks/demo_stack.py). Each instance is parameterized by `demo_id`, `slug`, and `agent_dir`, and creates:

- **An execution role** via the `AgentCoreRole` construct ([`constructs_local/agentcore_role.py`](./constructs_local/agentcore_role.py)), named `strands-demo-<demo_id>-runtime-role`. It is assumed by `bedrock-agentcore.amazonaws.com` and granted: the `AWSXRayDaemonWriteAccess` managed policy, `bedrock:InvokeModel` / `InvokeModelWithResponseStream`, CloudWatch Logs actions scoped to `/aws/bedrock-agentcore/*`, and `cloudwatch:PutMetricData` scoped to the `bedrock-agentcore` namespace.
- **An AgentCore Runtime** via the `AgentCoreRuntime` construct ([`constructs_local/agentcore_runtime.py`](./constructs_local/agentcore_runtime.py)), named `strands_demo_<demo_id>`, plus a runtime endpoint named `demo<demo_id>`. Deployment is code-based (a ZIP uploaded as an S3 asset), Python 3.11 runtime, `PUBLIC` network mode, with a lifecycle of `idle_runtime_session_timeout=900` (15 minutes) and `max_lifetime=28800` (8 hours). If the demo's `deployment_package.zip` is missing, the construct builds it at synth time by running `scripts/create_deployment_package.sh`.
- **Runtime environment variables**: `MODEL_ID` (from the `MODEL_ID` env var, defaulting to `us.amazon.nova-pro-v1:0`), `DEMO_ID`, and `DEMO_SLUG`. See [`demo_stack.py:32-36`](./stacks/demo_stack.py). Anthropic models are gated in the target account, so Nova Pro is the verified default.
- **An SSM parameter** `/strands-demos/<slug>/runtime_arn` holding the runtime ARN, plus a CloudFormation output. See [`demo_stack.py:49-55`](./stacks/demo_stack.py). The dispatcher reads this parameter at runtime to find which AgentCore Runtime to invoke.

## The dispatcher Lambda's role

The dispatcher ([`lambdas/dispatcher/lambda_function.py`](./lambdas/dispatcher/lambda_function.py)) is the bridge between the browser and the agents:

1. AppSync invokes it asynchronously when the browser publishes to `inbox/<demo>/<sessionId>`. It parses `demo` and `sessionId` from the channel path.
2. It looks up the demo's runtime ARN from SSM (`/strands-demos/<demo>/runtime_arn`, cached in memory) and calls `invoke_agent_runtime`, retrying up to 3 times with exponential backoff on cold-start / throttle / server errors (`RuntimeClientError`, `InternalServerException`, `ThrottlingException`).
3. It reads the runtime's SSE-style streamed response, parses each typed JSON event, tags it with an incrementing `seq` (AppSync fan-out does not guarantee ordering, so the client re-sorts), and publishes events in batches of up to 5 to `out/<demo>/<sessionId>` using the API key it reads from SSM (`/strands-demos/events_api_key`).
4. It sends a final `done` event, or an `error` + `done` pair if processing fails. It also forwards `interrupt_response` payloads back to the runtime for the human-in-the-loop demo.

## Deploy

Prerequisites: an AWS account with Amazon Bedrock model access (Amazon Nova Pro by default), Python 3.11+, [uv](https://docs.astral.sh/uv/), and AWS CDK v2. Dependencies are pinned in [`requirements.txt`](./requirements.txt) (`aws-cdk-lib`, `constructs`, `boto3`).

The CDK app command is `../.venv/bin/python app.py`, set in [`cdk.json`](./cdk.json), so a virtual environment at the repo root is expected.

Deploy all stacks (base + all demos):

```bash
# from the repo root
python3 -m venv .venv && source .venv/bin/activate
uv pip install -r infra/requirements.txt
cd infra && cdk deploy --all --require-approval never
```

Deploy a single stack (each demo is independent, so you can iterate on one at a time):

```bash
cd infra && cdk deploy StrandsDemo07Stack
```

Because every demo stack depends on the base stack, deploying a single demo stack will also deploy `StrandsDemosBaseStack` first if it is not already present.

Tear everything down (every resource uses `RemovalPolicy.DESTROY`, so nothing is left behind):

```bash
cd infra && cdk destroy --all
```

## How this ties into the root deploy.sh

The repository root has a `deploy.sh` that runs the full pipeline end to end. Deploying this CDK app (`cdk deploy --all`) is one step in that script; the SSM parameters and CloudFormation outputs written by `BaseStack` are what the rest of the pipeline consumes:

- After the infra deploy, `deploy.sh` creates the kiosk Cognito user in the pool this app created.
- It writes `web/.env.local` from the stack outputs (Cognito ids, Events API domains).
- It then deploys the separate web hosting app under `../web-infra` and runs a smoke test that exercises the full Cognito to AppSync to dispatcher Lambda to AgentCore path.

See the [root README](../README.md) for the one-command Quick Start and the end-to-end architecture.
