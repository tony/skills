#!/usr/bin/env bash
# A repo with an approved one-item plan whose patch turns the stand-in test
# runner red: the runner exits 1 when DELAY drops below the 0.1s the test needs.
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

HEAD_SHA=$(git rev-parse HEAD)
DIGEST=$(python3 "$ISOLATE" inputs --cwd . | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])')
sha256() { python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }

python3 - <<'PY'
import pathlib
p = pathlib.Path("tests/test_slow.py")
p.write_text(p.read_text().replace("DELAY = 0.8", "DELAY = 0.01"))
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

cat >.pytest-optimizer/plan.json <<JSON
[
  {
    "order": 1,
    "id": "H33-tests-test_slow-delay",
    "env_token": "eval-token",
    "patch": "patches/H33-tests-test_slow-delay.patch",
    "patch_sha256": "$PATCH_SHA",
    "files": ["tests/test_slow.py"],
    "cache": "disabled",
    "removed_ids": [],
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

PLAN_HASH=$(sha256 .pytest-optimizer/plan.json)
cat >.pytest-optimizer/state.json <<JSON
{
  "phase": "plan",
  "run_id": "eval",
  "env_token": "eval-token",
  "base_head": "$HEAD_SHA",
  "inputs_digest": "$DIGEST",
  "dirty": false,
  "hygiene": false,
  "completed": { "scan": true, "benchmark": true, "plan": true, "execute": false },
  "plan_hash": "$PLAN_HASH",
  "last_applied_index": -1
}
JSON
