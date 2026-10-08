#!/usr/bin/env bash
# A committed repo so scope.py and git see the case's own directory.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

cat >retry.py <<'PY'
def fetch_with_retry(url):
    # This function fetches a URL with retries and returns the response
    MAX_RETRIES = 3  # retries up to 3 times
    for attempt in range(MAX_RETRIES):
        # try to make the request
        try:
            return requests.get(url, timeout=5)
        except requests.ConnectionError:
            # Windows CI runners see a cold DNS cache on the first call; the
            # extra attempt below absorbs it. Do not lower this without
            # testing on the windows-latest runner.
            continue
    raise TimeoutError("exhausted retries")
PY
git add -A
git commit -qm "Add retry.py"
