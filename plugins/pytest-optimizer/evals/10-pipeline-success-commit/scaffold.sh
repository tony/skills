#!/usr/bin/env bash
# A repo whose test command is a stand-in runner (no pytest needed) that sleeps
# for DELAY seconds and prints a pytest-style summary. Scan and benchmark are
# recorded: one validated speedup lowers DELAY, kept as a hash-bound patch.
set -euo pipefail

ISOLATE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../scripts" && pwd)/isolate.py"
git init -b main >/dev/null
mkdir -p tests .pytest-optimizer/patches

cat >tests/test_slow.py <<'PY'
import time

DELAY = 0.8


def test_slow():
    time.sleep(DELAY)
PY

cat >run_tests.sh <<'SH'
#!/bin/sh
case " $* " in
  *" --collect-only "*)
    echo "tests/test_slow.py::test_slow"
    echo "1 test collected in 0.01s"
    exit 0
    ;;
esac
d=$(sed -n 's/^DELAY = //p' tests/test_slow.py)
sleep "$d"
echo "1 passed in ${d}s"
SH
chmod +x run_tests.sh

git add .
git -c user.email=eval@example.com -c user.name=eval commit -q -m 'tests(feat) Add slow test'
printf '/.*\n' >>"$(git rev-parse --git-path info/exclude)"

HEAD_SHA=$(git rev-parse HEAD)
DIGEST=$(python3 "$ISOLATE" inputs --cwd . | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])')
sha256() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

python3 - <<'PY'
import pathlib
p = pathlib.Path("tests/test_slow.py")
p.write_text(p.read_text().replace("DELAY = 0.8", "DELAY = 0.05"))
PY
git diff --binary >.pytest-optimizer/patches/H33-tests-test_slow-delay.patch
git checkout -q -- tests/test_slow.py
PATCH_SHA=$(sha256 .pytest-optimizer/patches/H33-tests-test_slow-delay.patch)

cat >.pytest-optimizer/baseline.json <<'JSON'
{
  "test_command": "sh run_tests.sh",
  "runs": [
    { "wall_seconds": 0.8 }, { "wall_seconds": 0.8 }, { "wall_seconds": 0.8 },
    { "wall_seconds": 0.8 }, { "wall_seconds": 0.8 }
  ],
  "noise": { "median": 0.8, "mad": 0.0, "floor": 0.05, "k": 3, "band": 0.05 },
  "tests": { "passed": 1, "total": 1 }
}
JSON

cat >.pytest-optimizer/control.json <<'JSON'
{
  "valid": true,
  "runs": [
    { "wall_seconds": 0.8 }, { "wall_seconds": 0.8 }, { "wall_seconds": 0.8 },
    { "wall_seconds": 0.8 }, { "wall_seconds": 0.8 }
  ],
  "noise": { "median": 0.8, "mad": 0.0, "floor": 0.05, "k": 3, "band": 0.05 },
  "tests": { "passed": 1, "total": 1 }
}
JSON

printf 'tests/test_slow.py::test_slow\n' >.pytest-optimizer/collection.txt

cat >.pytest-optimizer/hypotheses.json <<'JSON'
[
  {
    "id": "H33-tests-test_slow-delay",
    "heuristic": "H33",
    "evidence": "test_slow sleeps for DELAY = 0.8s; lowering DELAY keeps the test passing",
    "est_risk": "low",
    "est_effort": "small",
    "status": "open"
  }
]
JSON

cat >.pytest-optimizer/benchmarks.json <<JSON
[
  {
    "id": "H33-tests-test_slow-delay",
    "env_token": "eval-token",
    "base_head": "$HEAD_SHA",
    "patch": "patches/H33-tests-test_slow-delay.patch",
    "patch_sha256": "$PATCH_SHA",
    "files": ["tests/test_slow.py"],
    "cache": "disabled",
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

cat >.pytest-optimizer/state.json <<JSON
{
  "phase": "benchmark",
  "run_id": "eval",
  "env_token": "eval-token",
  "base_head": "$HEAD_SHA",
  "inputs_digest": "$DIGEST",
  "dirty": false,
  "hygiene": false,
  "completed": { "scan": true, "benchmark": true, "plan": false, "execute": false },
  "plan_hash": null,
  "last_applied_index": -1
}
JSON
