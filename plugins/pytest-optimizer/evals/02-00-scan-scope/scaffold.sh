#!/usr/bin/env bash
# A tiny pytest project in its own git repository, with pytest installed into a
# case-local directory. When pip cannot reach an index, a stub `pytest` that
# answers the three invocations a scan makes stands in for it.
set -euo pipefail

git init -b main >/dev/null
mkdir -p tests

cat >tests/conftest.py <<'PY'
import time

import pytest


@pytest.fixture
def db_session():
    time.sleep(0.05)
    return {"rows": []}
PY

cat >tests/test_reports.py <<'PY'
def test_export_large(db_session):
    assert db_session["rows"] == []


def test_export_small(db_session):
    assert db_session["rows"] == []


def test_export_empty(db_session):
    assert db_session["rows"] == []
PY

cat >pyproject.toml <<'TOML'
[tool.pytest.ini_options]
testpaths = ["tests"]
TOML

cat >AGENTS.md <<'MD'
# Project

Run the tests with `bin/pytest`.
MD

# The sandbox cannot read a virtualenv's interpreter symlink, so pytest installs
# into .pylib and runs under the system interpreter through bin/pytest.
PY=/usr/bin/python3
[ -x "$PY" ] || PY=$(command -v python3)
mkdir -p bin
if timeout 120 "$PY" -m pip install --quiet --target .pylib pytest >/dev/null 2>&1 \
  || timeout 120 uv pip install --quiet --target .pylib --python "$PY" pytest >/dev/null 2>&1; then
  cat >bin/pytest <<SH
#!/bin/sh
here=\$(cd "\$(dirname "\$0")/.." && pwd)
PYTHONPATH="\$here/.pylib" exec $PY -m pytest "\$@"
SH
else
  cat >bin/pytest <<'SH'
#!/bin/sh
case "$*" in
  *--collect-only*)
    for t in test_export_large test_export_small test_export_empty; do
      echo "tests/test_reports.py::$t"
    done
    echo "3 tests collected in 0.01s" ;;
  *--durations*)
    sleep 0.15
    echo "0.05s setup    tests/test_reports.py::test_export_large"
    echo "0.05s setup    tests/test_reports.py::test_export_small"
    echo "0.05s setup    tests/test_reports.py::test_export_empty"
    echo "3 passed in 0.15s" ;;
  *)
    sleep 0.15
    echo "3 passed in 0.15s" ;;
esac
SH
fi
chmod +x bin/pytest

printf '/.pylib/\n' >>"$(git rev-parse --git-path info/exclude)"
git add .
git -c user.email=eval@example.com -c user.name=eval commit -q -m 'tests(feat) Add report tests'
