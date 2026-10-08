#!/usr/bin/env bash
# A committed repo so scope.py and git see the case's own directory.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com

cat >store.py <<'PY'
# -*- coding: utf-8 -*-
import os


def load(path):
    """Load the file."""
    # open the file and read it
    data = open(path).read()  # noqa: SIM115
    return data


class NotFound(Exception):
    """Raised when the requested record does not exist in the store, which happens often."""


def parse(raw):
    # This function parses the raw value into an int by calling int on it
    return int(raw)  # type: ignore[arg-type]
PY
git add -A
git commit -qm "Add store.py"
