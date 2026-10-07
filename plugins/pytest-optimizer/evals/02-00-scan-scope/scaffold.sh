#!/usr/bin/env bash
# A minimal pytest project in its own git repository, so git commands in the
# run resolve here and never to an enclosing repository.
set -euo pipefail

git init -b main >/dev/null
mkdir -p tests

cat >tests/conftest.py <<'PY'
import pytest


@pytest.fixture
def db_session():
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

git add .
git -c user.email=eval@example.com -c user.name=eval commit -q -m 'tests(feat) Add report tests'
