#!/usr/bin/env bash
# Run SonarCloud/SonarQube analysis locally (same as CI) to fix issues before pushing.
#
# Prerequisites:
#   1. SonarCloud project created and project key known (e.g. org_autoppia-web-agents-subnet).
#   2. Token: SonarCloud → My Account → Security → Generate Token.
#   3. In sonar-project.properties set sonar.organization (or export SONAR_ORGANIZATION).
#
# Usage (from repo root):
#   export SONAR_TOKEN=your_token
#   export SONAR_ORGANIZATION=your_org   # if not set in sonar-project.properties
#   ./scripts/run_sonar_local.sh
#
# The script installs project deps (bittensor, requirements.txt, pytest-cov, pysonar) if needed.
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Validator config validates at import time; set dummy env so test collection succeeds
export VALIDATOR_NAME="${VALIDATOR_NAME:-sonar-local}"
export VALIDATOR_IMAGE="${VALIDATOR_IMAGE:-sonar-local}"

# Ensure project and test dependencies are installed (idempotent)
#echo "Ensuring dependencies (bittensor, project, pytest-cov, pysonar)..."
#pip install -q "bittensor==9.9.0"
#pip install -q -e .
#pip install -q pytest-cov pysonar

# Generate coverage so Sonar can use it
echo "Running tests with coverage..."
python -m pytest tests/ \
  --cov=autoppia_web_agents_subnet \
  --cov-report=xml \
  --cov-report=term \
  -q

if [ ! -f coverage.xml ]; then
  echo "No coverage.xml produced; creating minimal file for Sonar."
  printf '%s\n' '<?xml version="1.0" ?>' \
    '<coverage line-rate="0" branch-rate="0" lines-covered="0" lines-valid="1" branches-covered="0" branches-valid="0" version="1.9" timestamp="0">' \
    '<sources><source>.</source></sources>' '<packages/>' '</coverage>' > coverage.xml
fi

if [ -z "${SONAR_TOKEN:-}" ]; then
  echo "SONAR_TOKEN is not set. Set it to upload to SonarCloud: https://sonarcloud.io/account/security" >&2
  echo "Tests and coverage completed; skipping Sonar upload." >&2
  exit 0
fi

echo "Running Sonar scanner (pysonar)..."
python -m pysonar

echo "Done. Check results at https://sonarcloud.io (or your Sonar server)."
