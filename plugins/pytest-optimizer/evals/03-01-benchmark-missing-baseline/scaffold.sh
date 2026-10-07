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
# Repo with tests and no memory directory: no scan has run.
