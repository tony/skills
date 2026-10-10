#!/usr/bin/env bash
# A repo whose memory directory holds one clear speedup and one candidate
# labelled validated whose saving sits inside the noise band.
set -euo pipefail

ISOLATE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../scripts" && pwd)/isolate.py"

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
printf '/.*\n' >>"$(git rev-parse --git-path info/exclude)"

HEAD_SHA=$(git rev-parse HEAD)
DIGEST=$(python3 "$ISOLATE" inputs --cwd . | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])')
sha256() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }
mkdir -p .pytest-optimizer/patches

sed -i.bak 's/function/session/' tests/conftest.py && rm tests/conftest.py.bak
git diff --binary >.pytest-optimizer/patches/H10.patch
git checkout -q -- tests/conftest.py
printf '# no sleep to remove\n' >>tests/test_report.py
git diff --binary >.pytest-optimizer/patches/H33.patch
git checkout -q -- tests/test_report.py
SHA10=$(sha256 .pytest-optimizer/patches/H10.patch)
SHA33=$(sha256 .pytest-optimizer/patches/H33.patch)

cat >.pytest-optimizer/state.json <<JSON
{
  "phase": "benchmark",
  "run_id": "eval",
  "env_token": "eval-token",
  "base_head": "$HEAD_SHA",
  "inputs_digest": "$DIGEST",
  "dirty": false,
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

cat >.pytest-optimizer/benchmarks.json <<JSON
[
  {
    "id": "H10-conftest-make_config",
    "env_token": "eval-token",
    "base_head": "$HEAD_SHA",
    "patch": "patches/H10.patch",
    "patch_sha256": "$SHA10",
    "files": ["tests/conftest.py"],
    "cache": "disabled",
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
    "env_token": "eval-token",
    "base_head": "$HEAD_SHA",
    "patch": "patches/H33.patch",
    "patch_sha256": "$SHA33",
    "files": ["tests/test_report.py"],
    "cache": "disabled",
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
