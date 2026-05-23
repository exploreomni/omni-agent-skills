#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT_DIR/evals/lib/benchflow_runner.py"

if python3 - <<'PY' >/dev/null 2>&1
import benchflow
PY
then
  exec python3 "$RUNNER" "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run --with benchflow python "$RUNNER" "$@"
fi

cat >&2 <<'EOF'
ERROR: benchflow is not installed and uv was not found.

Install BenchFlow first:
  uv tool install benchflow

Or install it into your active Python environment:
  python3 -m pip install benchflow
EOF
exit 1
