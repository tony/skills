#!/usr/bin/env bash
# Builds a local corpus clone and a study with two cites into it: one whose
# lines still hold the quote, one whose line range has moved off it.
set -euo pipefail

git init --quiet

mkdir -p tiny-lib/src
cat >tiny-lib/src/ports.py <<'PY'
class PortAdapter:
    """Wraps a third-party client behind the port interface."""


class EventBus:
    """Publishes domain events to subscribed handlers."""
PY
git -C tiny-lib init --quiet -b main
git -C tiny-lib add .
git -C tiny-lib -c user.name=eval -c user.email=eval@example.com commit --quiet -m "Add ports"
commit=$(git -C tiny-lib rev-parse HEAD)

d=notes/ontology/tiny-lib
mkdir -p "$d"
printf '{"source":"tiny-lib","ref":"main","commit":"%s","scope":"src/","locator_kind":"line-range","read":true,"why":""}\n' "$commit" >"$d/sources.jsonl"
cat >"$d/terms.jsonl" <<'JSON'
{"schema":1,"term":"PortAdapter","definition":"wraps a client behind a port","kind":"class","parent":"root","cites":[{"source":"tiny-lib","locator":"src/ports.py:5-6","quote":"Wraps a third-party client behind the port interface."}]}
{"schema":1,"term":"EventBus","definition":"publishes domain events to handlers","kind":"class","parent":"root","cites":[{"source":"tiny-lib","locator":"src/ports.py:5-6","quote":"Publishes domain events to subscribed handlers."}]}
JSON

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.profile
.zprofile
.zshrc
MD
