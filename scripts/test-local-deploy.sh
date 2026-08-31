#!/usr/bin/env bash
# =============================================================================
# Local test harness for the Lerian Platform deployer (helm.yaml).
# Validates each module's rendered values against the REAL OCI chart via
# `helm template` — no cluster, no CloudFormation. See scripts/test-local-deploy.py.
#
#   scripts/test-local-deploy.sh                 # all modules
#   scripts/test-local-deploy.sh --apps ledger,access_manager
#   scripts/test-local-deploy.sh --no-helm       # offline render+secret only
#   scripts/test-local-deploy.sh --gitops        # also dry-render the GitOps seed
#
# Private charts (flowker = helm-internal) need `helm registry login ghcr.io` first;
# a pull failure is reported as SKIP, not a hard failure.
# =============================================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }
python3 -c "import yaml" 2>/dev/null || { echo "PyYAML required: pip install pyyaml"; exit 1; }
command -v helm >/dev/null 2>&1 || echo "WARN: helm not found — chart validation will SKIP (use --no-helm to silence)"

exec python3 "$SCRIPT_DIR/test-local-deploy.py" "$@"
