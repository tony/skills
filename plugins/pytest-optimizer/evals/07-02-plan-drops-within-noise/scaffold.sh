#!/usr/bin/env bash
# A repo whose memory directory holds one clear speedup and one candidate
# labelled validated whose saving sits inside the noise band.
set -euo pipefail

git init -b main >/dev/null
mkdir -p tests .pytest-optimizer

cat >tests/test_report.py <<'PY'
def test_report():
    assert True
PY
git add tests
git commit -q -m 'tests(feat) Add report test'
printf '.pytest-optimizer/\n' >>"$(git rev-parse --git-path info/exclude)"

cat >.pytest-optimizer/state.json <<'JSON'
{
  "phase": "benchmark",
  "run_id": "eval",
  "completed": { "scan": true, "benchmark": true, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
JSON

cat >.pytest-optimizer/baseline.json <<'JSON'
{
  "test_command": "pytest",
  "noise": { "median": 12.5, "mad": 0.15, "floor": 0.05, "k": 3, "band": 0.45 },
  "tests": { "passed": 40, "total": 40 }
}
JSON

cat >.pytest-optimizer/benchmarks.json <<'JSON'
[
  {
    "id": "H10-conftest-make_config",
    "diff_summary": "scope=\"function\" -> scope=\"session\" on make_config",
    "runs": 5,
    "median_delta": 2.7,
    "clears_noise": true,
    "gates": { "order_indep": true, "collection_det": true, "green": true },
    "confidence": 0.9,
    "observed_risk": "low",
    "verdict": "validated",
    "reason": null
  },
  {
    "id": "H33-tests-test_report-sleep",
    "diff_summary": "remove time.sleep(0.01) in test_report",
    "runs": 5,
    "median_delta": 0.03,
    "clears_noise": false,
    "gates": { "order_indep": true, "collection_det": true, "green": true },
    "confidence": 0.4,
    "observed_risk": "low",
    "verdict": "validated",
    "reason": null
  }
]
JSON
