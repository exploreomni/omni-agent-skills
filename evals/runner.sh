#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT_DIR/evals/lib/benchflow_runner.py"
BENCHFLOW_PACKAGE="${BENCHFLOW_PACKAGE:-benchflow @ git+https://github.com/benchflow-ai/benchflow.git@main}"

for arg in "$@"; do
  if [[ "$arg" == "--preflight-only" ]]; then
    exec python3 "$RUNNER" "$@"
  fi
done

if command -v uv >/dev/null 2>&1; then
  exec uv run --with "$BENCHFLOW_PACKAGE" python "$RUNNER" "$@"
fi

if python3 - <<'PY' >/dev/null 2>&1
import benchflow
PY
then
  cat >&2 <<'EOF'
WARNING: uv was not found, so the runner is using the installed benchflow package.
Token telemetry requires a BenchFlow version that includes PR #289.
EOF
  exec python3 "$RUNNER" "$@"
fi

cat >&2 <<'EOF'
ERROR: benchflow is not installed and uv was not found.

Install BenchFlow first:
  uv tool install 'benchflow @ git+https://github.com/benchflow-ai/benchflow.git@main'

Or install it into your active Python environment:
  python3 -m pip install 'benchflow @ git+https://github.com/benchflow-ai/benchflow.git@main'
EOF
exit 1
