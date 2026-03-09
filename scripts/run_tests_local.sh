#!/usr/bin/env bash
# Run tests with coverage locally (same command as CI).
# Usage: from repo root, ./scripts/run_tests_local.sh
# Requires: venv with deps (pip install -r requirements.txt bittensor==9.9.0; pip install -e .)
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Use venv python if present
if [ -x "./venv/bin/python" ]; then
  PYTHON="./venv/bin/python"
else
  PYTHON="python"
fi

export VALIDATOR_NAME="${VALIDATOR_NAME:-local}"
export VALIDATOR_IMAGE="${VALIDATOR_IMAGE:-local}"

"$PYTHON" -m pytest tests/ \
  --cov=autoppia_web_agents_subnet \
  --cov-report=term \
  --cov-report=xml \
  -q

echo "Coverage report: coverage.xml (for Sonar) and term above."
