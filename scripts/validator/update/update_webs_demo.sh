#!/usr/bin/env bash
# update_webs_demo.sh - Update webs_demo and redeploy demo webs.

set -euo pipefail
IFS=$'\n\t'

WEBS_DEMO_PATH="${WEBS_DEMO_PATH:-../autoppia_webs_demo}"

SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
DEPLOY_DEMO_WRAPPER="$REPO_ROOT/scripts/validator/demo-webs/deploy_demo_webs.sh"
if [[ "$WEBS_DEMO_PATH" != /* ]]; then
  WEBS_DEMO_PATH="$REPO_ROOT/$WEBS_DEMO_PATH"
fi

if [ ! -d "$WEBS_DEMO_PATH/.git" ]; then
  echo "[ERROR] webs_demo repo not found at ${WEBS_DEMO_PATH}" >&2
  echo "[ERROR] Set WEBS_DEMO_PATH to your autoppia_webs_demo directory." >&2
  exit 1
fi

echo "[INFO] Updating autoppia_webs_demo at $WEBS_DEMO_PATH..."
(cd "$WEBS_DEMO_PATH" && git pull origin main)

if [ ! -x "$DEPLOY_DEMO_WRAPPER" ]; then
  echo "[ERROR] Demo deploy wrapper not found or not executable: $DEPLOY_DEMO_WRAPPER" >&2
  exit 1
fi

echo "[INFO] Redeploying demo webs..."
bash "$DEPLOY_DEMO_WRAPPER"

echo "[INFO] Pruning dangling Docker images left by web builds..."
docker image prune -f

if [[ "${DOCKER_PRUNE_BUILD_CACHE:-true}" == "true" ]]; then
  BUILDER_PRUNE_UNTIL="${DOCKER_BUILDER_PRUNE_UNTIL:-168h}"
  BUILDER_PRUNE_KEEP_STORAGE="${DOCKER_BUILDER_PRUNE_KEEP_STORAGE:-20gb}"
  echo "[INFO] Pruning old Docker build cache (until=${BUILDER_PRUNE_UNTIL}, keep-storage=${BUILDER_PRUNE_KEEP_STORAGE})..."
  docker builder prune -f --filter "until=${BUILDER_PRUNE_UNTIL}" --keep-storage "${BUILDER_PRUNE_KEEP_STORAGE}" || true
fi

echo "[INFO] webs_demo update completed"
