#!/usr/bin/env bash
# A branch whose first commit refactors the login rate limiter and whose
# second adds the password-reset throttle the goal asks for.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

mkdir -p src
printf 'def allow_login(user):\n    return True\n' >src/limiter.py
printf 'def send_reset(address):\n    print(address)\n' >src/mailer.py
git add -A
git commit -q -m 'Add login limiter and reset mailer'

git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c feat/reset-throttle

cat >src/limiter.py <<'PY'
from collections import deque


class LoginLimiter:
    def __init__(self, limit: int = 5) -> None:
        self.limit = limit
        self.hits: dict[str, deque[float]] = {}

    def allow(self, user: str) -> bool:
        return len(self.hits.get(user, ())) < self.limit
PY
git commit -qam 'Refactor the login rate limiter into a class'

cat >src/mailer.py <<'PY'
import time

_LAST: dict[str, float] = {}


def send_reset(address: str) -> bool:
    now = time.monotonic()
    if now - _LAST.get(address, -60.0) < 60.0:
        return False
    _LAST[address] = now
    print(address)
    return True
PY
git commit -qam 'Throttle password-reset emails per address'
