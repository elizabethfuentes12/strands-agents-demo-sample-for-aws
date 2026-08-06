# Strands Demos Web Hosting (CDK)

A standalone AWS CDK app that hosts the static [Strands Agents](https://strandsagents.com/) demo showcase SPA on a private Amazon S3 bucket fronted by Amazon CloudFront with Origin Access Control (OAC).

This is a separate CDK app from the agents infra in [`../infra/`](../infra/). Keeping the public site in its own app means you can deploy and tear down the hosting independently of the agent runtimes: the site can be rebuilt and redeployed without touching the AgentCore stacks, and either side can be destroyed on its own.

> For the agents, the shared base stack (Cognito + AppSync Events + dispatcher), and the one-command deploy of the whole showcase, see the [root README](../README.md). For the front-end code, see [`../web/`](../web/).

## What it deploys

A single stack, `StrandsDemosWebStack` (see [`stacks/web_stack.py`](./stacks/web_stack.py)):

- **Private S3 bucket:** `BlockPublicAccess.BLOCK_ALL`, `enforce_ssl=True`. Not publicly readable; CloudFront reaches it through OAC.
- **CloudFront distribution:** origin is the S3 bucket via `S3BucketOrigin.with_origin_access_control` (OAC), viewer protocol policy redirects HTTP to HTTPS, default root object `index.html`. SPA routing is handled by mapping 403 and 404 responses to `/index.html` with a 200 status, so client-side routes resolve.
- **Bucket deployment:** uploads `web/dist/` to the bucket and invalidates the distribution (`/*`) on each deploy.
- **Outputs:** `WebUrl` (the CloudFront URL) and `BucketName`.

Both the bucket and its objects use `RemovalPolicy.DESTROY` with `auto_delete_objects=True`, so `cdk destroy` leaves nothing behind.

### Build at synth time

The stack builds the SPA during synthesis: it runs `npm install` and `npm run build` in [`../web/`](../web/) so `dist/` always reflects the current `web/.env.local`. Because of that, the stack requires `web/.env.local` to exist and raises a clear `FileNotFoundError` if it is missing.

## Prerequisites

- The agents base stack is deployed and `web/.env.local` exists with the Cognito + AppSync outputs. The repo's [`deploy.sh`](../deploy.sh) writes this file (step 5); if you deploy manually, create it first (see the [web README](../web/README.md#configuration)).
- Node.js 20+ (for the synth-time `npm` build) and Python 3.11+.
- AWS CDK v2 and AWS credentials for the target account/region.
- Dependencies from [`requirements.txt`](./requirements.txt): `aws-cdk-lib>=2.220.0`, `constructs>=10.0.0`.

The account and region come from `CDK_DEFAULT_ACCOUNT` and `CDK_DEFAULT_REGION` (defaulting to `us-east-1`), set in [`app.py`](./app.py). Note that [`cdk.json`](./cdk.json) runs the app via `../.venv/bin/python app.py`, so it expects the repo-root virtual environment described below.

## Deploy

```bash
# From the repo root: create/activate the venv and install CDK deps.
python3 -m venv .venv && source .venv/bin/activate
uv pip install -r web-infra/requirements.txt

# Deploy the hosting stack (web/.env.local must already exist).
cd web-infra && cdk deploy
```

CDK builds the SPA at synth time, uploads `dist/` to the private bucket, and prints the `WebUrl` output (the CloudFront URL) when it finishes.

## Tear down

```bash
cd web-infra && cdk destroy
```

Because every resource is `RemovalPolicy.DESTROY` and `auto_delete_objects=True`, this removes the bucket (including its objects) and the distribution, leaving no standing cost. It does not touch the agent runtimes in [`../infra/`](../infra/).

## Layout

```
web-infra/
  app.py                CDK app entry: instantiates StrandsDemosWebStack
  cdk.json              CDK config (runs ../.venv/bin/python app.py)
  requirements.txt      aws-cdk-lib, constructs
  stacks/
    web_stack.py        WebStack: private S3 + CloudFront (OAC), synth-time SPA build
```
