#!/usr/bin/env bash
# Branch feat/17-throttle-reset: the throttle and its config are done, the
# test the ticket asks for is missing, and a logging rewrite is off goal.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com
mkdir -p src
printf 'def send_reset(address):\n    print(address)\n' >src/mailer.py
printf 'def log(msg):\n    print(msg)\n' >src/logging_util.py
git add -A
git commit -q -m 'Add reset mailer and logging helper'
git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/17-throttle-reset
printf 'WINDOW_SECONDS = 60\n' >src/config.py
cat >src/mailer.py <<'PY'
import time

_LAST = {}


def send_reset(address):
    now = time.monotonic()
    if now - _LAST.get(address, -60) < 60:
        return False
    _LAST[address] = now
    print(address)
    return True
PY
git add -A
git commit -q -m 'Throttle reset emails per address (refs #17)'
printf 'import sys\n\n\ndef log(msg, level="info"):\n    sys.stderr.write(f"[{level}] {msg}\\n")\n' >src/logging_util.py
git commit -qam 'Rewrite the logging module with levels'

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "issue view")
    cat <<'JSON'
{"number":17,"title":"Throttle password-reset emails","state":"OPEN","labels":[],"url":"https://example.invalid/issues/17","body":"Acceptance criteria:\n- One reset email per address per minute.\n- The window is configurable.\n- A test covers the throttled response."}
JSON
    ;;
  *) echo "no pull requests found for branch" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
