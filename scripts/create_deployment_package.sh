#!/bin/bash
# Build an AgentCore code-based deployment ZIP for one agent directory.
# Usage: create_deployment_package.sh <agent_dir>
# Installs ARM64 (aarch64-manylinux2014) wheels with uv and zips deps + sources.
set -euo pipefail

AGENT_DIR="${1:?usage: create_deployment_package.sh <agent_dir>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMON_DIR="$REPO_ROOT/agents/common"

cd "$AGENT_DIR"
rm -rf deployment_package deployment_package.zip

uv pip install \
  --python-platform aarch64-manylinux2014 \
  --python-version 3.11 \
  --target deployment_package \
  --only-binary=:all: \
  -r requirements.txt

cp ./*.py deployment_package/
# Shared event protocol helpers
cp "$COMMON_DIR"/*.py deployment_package/

cd deployment_package
zip -rq ../deployment_package.zip .
cd ..
rm -rf deployment_package
echo "Built $AGENT_DIR/deployment_package.zip"
