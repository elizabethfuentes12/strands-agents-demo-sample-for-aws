#!/bin/bash
# One-shot deployment orchestrator for the Strands Agents Demo Showcase.
#
# Usage:
#   KIOSK_PASSWORD='<strong-password>' ./deploy.sh
#   AWS_PROFILE=my-profile KIOSK_PASSWORD='...' ./deploy.sh
#
# Prerequisites: AWS credentials, Python 3.11+, Node.js 20+, uv, AWS CDK v2.
# Bedrock model access required: Amazon Nova Pro (us.amazon.nova-pro-v1:0).
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
KIOSK_USER="${KIOSK_USERNAME:-kiosk}"
SSM_PREFIX="/strands-demos"
ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- 1. Python venv (shared by both CDK apps) --------------------------------
echo "==> [1/7] Python venv + dependencies"
if [ ! -d "$ROOT/.venv" ]; then
  uv venv "$ROOT/.venv" --python 3.11
fi
uv pip install --python "$ROOT/.venv/bin/python" -q \
  -r "$ROOT/01-infra/requirements.txt" \
  -r "$ROOT/02-frontend/requirements.txt"

# --- 2. CDK bootstrap --------------------------------------------------------
echo "==> [2/7] CDK bootstrap check"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" >/dev/null 2>&1; then
  (cd "$ROOT/01-infra" && JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk bootstrap)
fi

# --- 3. Deploy 01-infra (backend: Cognito + AppSync + 11 AgentCore runtimes) -
echo "==> [3/7] Deploying 01-infra (backend)"
(cd "$ROOT/01-infra" && JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 \
  npx cdk deploy --all --require-approval never)

# --- 4. Kiosk Cognito user ---------------------------------------------------
echo "==> [4/7] Kiosk user"
POOL_ID=$(aws ssm get-parameter --name "$SSM_PREFIX/user_pool_id" \
  --region "$REGION" --query Parameter.Value --output text)
if [ -z "${KIOSK_PASSWORD:-}" ]; then
  echo "ERROR: Set KIOSK_PASSWORD before running deploy.sh (e.g. KIOSK_PASSWORD='...' ./deploy.sh)"
  exit 1
fi
aws cognito-idp admin-create-user --user-pool-id "$POOL_ID" --username "$KIOSK_USER" \
  --message-action SUPPRESS --region "$REGION" >/dev/null 2>&1 || true
aws cognito-idp admin-set-user-password --user-pool-id "$POOL_ID" --username "$KIOSK_USER" \
  --password "$KIOSK_PASSWORD" --permanent --region "$REGION"

# --- 5. Write web/.env.local from 01-infra SSM outputs ----------------------
echo "==> [5/7] Writing web/.env.local from SSM"
CLIENT_ID=$(aws ssm get-parameter --name "$SSM_PREFIX/user_pool_client_id" \
  --region "$REGION" --query Parameter.Value --output text)
HTTP_DOMAIN=$(aws ssm get-parameter --name "$SSM_PREFIX/events_http_domain" \
  --region "$REGION" --query Parameter.Value --output text)
RT_DOMAIN=$(aws ssm get-parameter --name "$SSM_PREFIX/events_realtime_domain" \
  --region "$REGION" --query Parameter.Value --output text)
cat > "$ROOT/02-frontend/web/.env.local" <<EOF
VITE_AWS_REGION=$REGION
VITE_COGNITO_CLIENT_ID=$CLIENT_ID
VITE_EVENTS_HTTP_DOMAIN=$HTTP_DOMAIN
VITE_EVENTS_REALTIME_DOMAIN=$RT_DOMAIN
EOF

# --- 6. Deploy 02-frontend (S3 + CloudFront) --------------------------------
echo "==> [6/7] Deploying 02-frontend (web hosting)"
(cd "$ROOT/02-frontend" && JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 \
  npx cdk deploy --all --require-approval never)

# --- 7. Smoke test -----------------------------------------------------------
echo "==> [7/7] Smoke test"
uv pip install --python "$ROOT/.venv/bin/python" -q websockets
KIOSK_USERNAME="$KIOSK_USER" KIOSK_PASSWORD="$KIOSK_PASSWORD" AWS_REGION="$REGION" \
  "$ROOT/.venv/bin/python" "$ROOT/01-infra/scripts/smoke_test.py" agent-loop "What is 2+2?" || {
    echo "Smoke test FAILED — check the troubleshooting section in README.md"; exit 1; }

echo ""
echo "✅ All deployed."
echo "   Login: $KIOSK_USER / $KIOSK_PASSWORD"
