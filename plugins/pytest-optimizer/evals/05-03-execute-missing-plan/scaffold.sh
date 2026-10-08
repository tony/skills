#!/usr/bin/env bash
set -euo pipefail

git init -b main >/dev/null
mkdir -p tests
cat >tests/test_report.py <<'PY'
def test_report():
    assert True
PY
git add tests
git commit -q -m 'tests(feat) Add report test'
# Benchmarks are on record; no plan.json exists.
mkdir -p .pytest-optimizer
printf '.pytest-optimizer/\n' >>"$(git rev-parse --git-path info/exclude)"
cat >.pytest-optimizer/state.json <<'JSON'
{ "phase": "benchmark", "run_id": "eval", "completed": { "scan": true, "benchmark": true, "plan": false, "execute": false }, "plan_hash": null, "last_applied_index": -1 }
JSON
cat >.pytest-optimizer/baseline.json <<'JSON'
{ "test_command": "pytest", "noise": { "median": 1.0, "mad": 0.01, "floor": 0.05, "k": 3, "band": 0.05 }, "tests": { "passed": 1, "total": 1 } }
JSON
printf '[]\n' >.pytest-optimizer/benchmarks.json
