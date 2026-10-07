#!/usr/bin/env bash
# A repo whose test command is a stand-in runner (no pytest needed) that sleeps
# for DELAY seconds and prints a pytest-style summary. Scan, benchmark, and the
# memory files are pre-recorded: one validated speedup lowers DELAY.
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
echo "1 passed in ${d}s"
SH
chmod +x run_tests.sh

git add .
git -c user.email=eval@example.com -c user.name=eval commit -q -m 'tests(feat) Add slow test'
printf '.pytest-optimizer/\n.claude/\n' >>"$(git rev-parse --git-path info/exclude)"

HEAD_SHA=$(git rev-parse HEAD)
cat >.pytest-optimizer/state.json <<JSON
{
  "phase": "benchmark",
  "run_id": "eval",
  "base_head": "$HEAD_SHA",
  "hygiene": false,
  "completed": { "scan": true, "benchmark": true, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
JSON

cat >.pytest-optimizer/baseline.json <<'JSON'
{
  "test_command": "sh run_tests.sh",
  "runs": [ { "seconds": 0.8, "exit": 0, "passed": 1, "total": 1 } ],
  "noise": { "median": 0.8, "mad": 0.0, "floor": 0.05, "k": 3, "band": 0.05 },
  "tests": { "passed": 1, "total": 1 }
}
JSON

cat >.pytest-optimizer/hypotheses.json <<'JSON'
[
  {
    "id": "H33-tests-test_slow-delay",
    "heuristic": "H33",
    "evidence": "test_slow sleeps for DELAY = 0.8s; lowering DELAY to 0.05 keeps the test passing",
    "est_risk": "low",
    "est_effort": "small",
    "status": "open"
  }
]
JSON

cat >.pytest-optimizer/benchmarks.json <<'JSON'
[
  {
    "id": "H33-tests-test_slow-delay",
    "diff_summary": "DELAY = 0.8 -> DELAY = 0.05 in tests/test_slow.py",
    "runs": 5,
    "median_delta": 0.75,
    "clears_noise": true,
    "gates": { "order_indep": true, "collection_det": true, "green": true },
    "confidence": 0.9,
    "observed_risk": "low",
    "verdict": "validated",
    "reason": null
  }
]
JSON
