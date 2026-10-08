#!/usr/bin/env bash
set -euo pipefail

cat >client.py <<'PY'
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2
PY
