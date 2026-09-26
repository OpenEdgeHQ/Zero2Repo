#!/usr/bin/env bash
# Run cbrun agent smoke tests using local gitignored env files.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec python3 local_agents/smoke.py "${1:-all}"
