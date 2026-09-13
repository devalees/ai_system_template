#!/usr/bin/env bash
# =============================================================================
# Sovereign Autonomous Agent Platform - Golden Benchmark Evaluation Runner
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "====================================================================="
echo "  Sovereign AI Workforce: Golden Benchmark Evaluation Runner"
echo "====================================================================="
echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Workspace: ${WORKSPACE_DIR}"
echo "---------------------------------------------------------------------"

if command -v docker &> /dev/null && docker ps --filter "name=hermes-template-agent" --filter "status=running" -q | grep -q . ; then
    echo "[INFO] Running benchmark suite inside container 'hermes-template-agent'..."
    docker exec -e PYTHONSAFEPATH=1 -e PYTHONPATH=/ hermes-template-agent pytest /workspace/evals/ -v --durations=5
else
    echo "[INFO] Running benchmark suite locally with Python..."
    export PYTHONSAFEPATH=1
    export PYTHONPATH="${WORKSPACE_DIR}/..:${WORKSPACE_DIR}"
    pytest "${SCRIPT_DIR}" -v --durations=5
fi

echo "---------------------------------------------------------------------"
echo "✓ Benchmark Evaluation completed successfully. 100% Pass Rate."
echo "====================================================================="
