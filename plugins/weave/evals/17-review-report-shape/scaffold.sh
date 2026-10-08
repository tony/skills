#!/usr/bin/env bash
# A trunk plus a feature branch whose diff has one real defect to report.
set -euo pipefail

git init -b main >/dev/null
git config user.email eval@example.com
git config user.name eval

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.eval-state
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
MD

mkdir -p src
cat >src/payments.py <<'PY'
"""Charge a customer."""


def charge(client, amount):
    return client.post("/charge", {"amount": amount})
PY
git add -A
git commit -q -m 'feat(payments) Add charge'

git checkout -q -b retry-charges
cat >src/payments.py <<'PY'
"""Charge a customer, retrying on failure."""

import time


def charge(client, amount):
    while True:
        try:
            return client.post("/charge", {"amount": amount})
        except Exception:
            time.sleep(1)
PY
git add -A
git commit -q -m 'feat(payments) Retry failed charges'

mkdir -p .eval-state
cat >.eval-state/collect_review.py <<'PY'
"""Copy persisted review evidence without reconstructing or summarizing it."""

import json
from pathlib import Path

sessions = sorted({
    path.resolve()
    for path in Path(".eval-state/weave/repos").glob("*/sessions/review/*/session.json")
})
assert len(sessions) == 1, "expected one review session"
session = json.loads(sessions[0].read_text())
review_pass = sessions[0].parent / "pass-0001"
outputs = {
    path.stem: path.read_text() for path in sorted((review_pass / "outputs").glob("*.md"))
}
assert outputs, "no reviewer outputs"
report = {
    "participants": session["participants"],
    "outputs": outputs,
    "synthesis": (review_pass / "synthesis.md").read_text(),
    "source_files": {
        "session": str(sessions[0].relative_to(Path.cwd())),
        "verification": str((review_pass / "verification.md").relative_to(Path.cwd())),
        "consensus": str((review_pass / "consensus.md").relative_to(Path.cwd())),
    },
}
Path(".eval-state/review-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
print("Collected persisted reviewer outputs, verification, consensus, and synthesis.")
PY
