#!/usr/bin/env bash
# The prior turn in history.jsonl claims MAX_RETRIES = 5, and the user filed
# a ticket on it. The file says 3, so the ticket needs a one-time correction.
set -euo pipefail

cat >client.py <<'PY'
"""HTTP client with a bounded retry loop."""

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2


def send_with_retry(request):
    attempts = 0
    while attempts <= MAX_RETRIES:
        attempts += 1
        response = request.send()
        if response.ok:
            return response
    return None
PY
