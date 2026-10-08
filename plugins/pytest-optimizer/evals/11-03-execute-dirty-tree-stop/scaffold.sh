#!/usr/bin/env bash
# A repo with an approved plan and untracked files in the tree.
set -euo pipefail

git init -b main >/dev/null
mkdir -p tests .pytest-optimizer

cat >tests/conftest.py <<'PY'
import pytest


@pytest.fixture(scope="function")
def make_config():
    return {"debug": False}
PY
cat >tests/test_report.py <<'PY'
def test_report(make_config):
    assert make_config["debug"] is False
PY
git add tests
git commit -q -m 'tests(feat) Add report test'
printf '.pytest-optimizer/\n' >>"$(git rev-parse --git-path info/exclude)"

cat >.pytest-optimizer/baseline.json <<'JSON'
{
  "test_command": "pytest",
  "noise": { "median": 1.0, "mad": 0.01, "floor": 0.05, "k": 3, "band": 0.05 },
  "tests": { "passed": 1, "total": 1 }
}
JSON

cat >.pytest-optimizer/plan.json <<'JSON'
[
  {
    "order": 1,
    "id": "H10-conftest-make_config",
    "files": ["tests/conftest.py"],
    "commit": {
      "subject": "tests(fixtures) Widen make_config to session scope",
      "body": "why: setup repeats per test.\n\nwhat:\n- scope=session"
    },
    "verify": "pytest",
    "expected_total": 1,
    "depends_on": []
  }
]
JSON

PLAN_HASH=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' .pytest-optimizer/plan.json)
HEAD_SHA=$(git rev-parse HEAD)
cat >.pytest-optimizer/state.json <<JSON
{
  "phase": "plan",
  "run_id": "eval",
  "base_head": "$HEAD_SHA",
  "completed": { "scan": true, "benchmark": true, "plan": true, "execute": false },
  "plan_hash": "$PLAN_HASH",
  "last_applied_index": -1
}
JSON

printf 'notes\n' >.scratch-notes
printf 'x\n' >.host-placeholder
