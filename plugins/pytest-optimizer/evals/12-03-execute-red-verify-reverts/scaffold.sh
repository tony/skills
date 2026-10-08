#!/usr/bin/env bash
# A repo with an approved one-item plan whose change turns the stand-in test
# runner red: the runner exits 1 when DELAY drops below the 0.1s the test needs.
set -euo pipefail

git init -b main >/dev/null
mkdir -p tests .pytest-optimizer

cat >tests/test_slow.py <<'PY'
import time

DELAY = 0.8


def test_slow():
    time.sleep(DELAY)
PY

cat >run_tests.sh <<'SH'
#!/bin/sh
d=$(sed -n 's/^DELAY = //p' tests/test_slow.py)
sleep "$d"
if awk -v d="$d" 'BEGIN { exit !(d >= 0.1) }'; then
  echo "1 passed in ${d}s"
else
  echo "1 failed in ${d}s"
  exit 1
fi
SH
chmod +x run_tests.sh

git add .
git -c user.email=eval@example.com -c user.name=eval commit -q -m 'tests(feat) Add slow test'
printf '/.*\n' >>"$(git rev-parse --git-path info/exclude)"

cat >.pytest-optimizer/baseline.json <<'JSON'
{
  "test_command": "sh run_tests.sh",
  "runs": [ { "seconds": 0.8, "exit": 0, "passed": 1, "total": 1 } ],
  "noise": { "median": 0.8, "mad": 0.0, "floor": 0.05, "k": 3, "band": 0.05 },
  "tests": { "passed": 1, "total": 1 }
}
JSON

cat >.pytest-optimizer/plan.json <<'JSON'
[
  {
    "order": 1,
    "id": "H33-tests-test_slow-delay",
    "files": ["tests/test_slow.py"],
    "commit": {
      "subject": "tests(slow) Lower DELAY in test_slow",
      "body": "why: the sleep dominates the suite.\n\nwhat:\n- DELAY = 0.8 -> DELAY = 0.01"
    },
    "verify": "sh run_tests.sh",
    "expected_total": 1,
    "depends_on": []
  }
]
JSON

HEAD_SHA=$(git rev-parse HEAD)
PLAN_HASH=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' .pytest-optimizer/plan.json)
cat >.pytest-optimizer/state.json <<JSON
{
  "phase": "plan",
  "run_id": "eval",
  "base_head": "$HEAD_SHA",
  "hygiene": false,
  "completed": { "scan": true, "benchmark": true, "plan": true, "execute": false },
  "plan_hash": "$PLAN_HASH",
  "last_applied_index": -1
}
JSON
