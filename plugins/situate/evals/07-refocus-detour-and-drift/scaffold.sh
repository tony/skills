#!/usr/bin/env bash
# A branch with one on-goal commit, one load-bearing detour (an injectable
# clock the throttle test needs), and one off-goal commit (an unrelated formatter rewrite).
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

mkdir -p src
cat >src/mailer.py <<'PY'
def send_reset(address: str) -> None:
    print(f"reset email to {address}")
PY
cat >src/format.py <<'PY'
def fmt(name):
    return "hello " + name
PY
git add -A
git commit -q -m 'Add reset mailer and formatter'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/reset-throttle

cat >src/mailer.py <<'PY'
import time

_LAST: dict[str, float] = {}
WINDOW_SECONDS = 60.0


def send_reset(address: str) -> bool:
    now = time.monotonic()
    if now - _LAST.get(address, -WINDOW_SECONDS) < WINDOW_SECONDS:
        return False
    _LAST[address] = now
    print(f"reset email to {address}")
    return True
PY
git commit -qam 'Throttle password-reset emails per address'

cat >src/mailer.py <<'PY'
import time

_LAST: dict[str, float] = {}
WINDOW_SECONDS = 60.0


def send_reset(address: str, clock=time.monotonic) -> bool:
    now = clock()
    if now - _LAST.get(address, -WINDOW_SECONDS) < WINDOW_SECONDS:
        return False
    _LAST[address] = now
    print(f"reset email to {address}")
    return True
PY
git commit -qam 'Pass the clock into send_reset so a test can control time'

cat >src/format.py <<'PY'
def fmt(name: str) -> str:
    return f"hello {name}"
PY
git commit -qam 'Rewrite formatter with f-strings and type hints'
