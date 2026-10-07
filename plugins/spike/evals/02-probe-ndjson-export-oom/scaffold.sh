#!/usr/bin/env bash
# A repository with no commits and an untracked exporter, so a probe has code
# to change but nothing to branch from.
set -euo pipefail

git init -b main >/dev/null
mkdir -p src
cat >src/export.py <<'PY'
"""Export rows as one JSON document."""
import json


def export(rows):
    return json.dumps(list(rows))
PY
