#!/bin/bash
# One-shot deployment orchestrator for the Strands Agents Demo Showcase.
#
# Usage:
#   ./deploy.sh                    # deploy everything (infra + kiosk user + web config)
#   KIOSK_PASSWORD=... ./deploy.sh # set your own kiosk password (recommended)
#   AWS_PROFILE=my-profile ./deploy.sh
#
# Prerequisites: AWS credentials, Python 3.11+, Node.js 20+, uv, AWS CDK v2.
# Bedrock model access required: Amazon Nova Pro (us.amazon.nova-pro-v1:0) or
# set MODEL_ID to any Bedrock model your account can invoke.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
KIOSK_USER="${KIOSK_USERNAME:-kiosk}"
SSM_PREFIX="/strands-demos"
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> [1/7] Python venv + CDK dependencies"
if [ ! -d "$ROOT/.venv" ]; then
  uv venv "$ROOT/.venv" --python 3.11
fi
uv pip install --python "$ROOT/.venv/bin/python" -q -r "$ROOT/infra/requirements.txt"

echo "==> [2/7] CDK bootstrap check"
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" >/dev/null 2>&1; then
  (cd "$ROOT/infra" && npx cdk bootstrap)
fi

echo "==> [3/7] Deploying all stacks (base + one per demo)"
(cd "$ROOT/infra" && JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy --all --require-approval never)

echo "==> [4/7] Kiosk user"
POOL_ID=$(aws ssm get-parameter --name "$SSM_PREFIX/user_pool_id" --region "$REGION" --query Parameter.Value --output text)
if [ -z "${KIOSK_PASSWORD:-}" ]; then
  KIOSK_PASSWORD="Demo-$(openssl rand -hex 8)!"
  echo "    Generated kiosk password: $KIOSK_PASSWORD  (save it!)"
fi
aws cognito-idp admin-create-user --user-pool-id "$POOL_ID" --username "$KIOSK_USER" \
  --message-action SUPPRESS --region "$REGION" >/dev/null 2>&1 || true
aws cognito-idp admin-set-user-password --user-pool-id "$POOL_ID" --username "$KIOSK_USER" \
  --password "$KIOSK_PASSWORD" --permanent --region "$REGION"

echo "==> [5/7] Web app config (.env.local from SSM)"
CLIENT_ID=$(aws ssm get-parameter --name "$SSM_PREFIX/user_pool_client_id" --region "$REGION" --query Parameter.Value --output text)
HTTP_DOMAIN=$(aws ssm get-parameter --name "$SSM_PREFIX/events_http_domain" --region "$REGION" --query Parameter.Value --output text)
RT_DOMAIN=$(aws ssm get-parameter --name "$SSM_PREFIX/events_realtime_domain" --region "$REGION" --query Parameter.Value --output text)
cat > "$ROOT/web/.env.local" <<EOF
VITE_AWS_REGION=$REGION
VITE_COGNITO_CLIENT_ID=$CLIENT_ID
VITE_EVENTS_HTTP_DOMAIN=$HTTP_DOMAIN
VITE_EVENTS_REALTIME_DOMAIN=$RT_DOMAIN
EOF

echo "==> [6/7] Web hosting (S3 + CloudFront)"
(cd "$ROOT/infra" && JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx cdk deploy StrandsDemosWebStack -c deploy_web=true --require-approval never)

echo "==> [7/7] Smoke test (agent-loop, end to end)"
uv pip install --python "$ROOT/.venv/bin/python" -q websockets
KIOSK_USERNAME="$KIOSK_USER" KIOSK_PASSWORD="$KIOSK_PASSWORD" AWS_REGION="$REGION" \
  "$ROOT/.venv/bin/python" "$ROOT/scripts/smoke_test.py" agent-loop "What is 2+2?" || {
    echo "Smoke test FAILED — check the troubleshooting section in README.md"; exit 1; }

echo ""
echo "✅ All deployed. Run the web app:"
echo "   cd web && npm install && npm run dev"
echo "   Login: $KIOSK_USER / $KIOSK_PASSWORD"
