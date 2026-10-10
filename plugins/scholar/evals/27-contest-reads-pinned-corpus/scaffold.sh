#!/usr/bin/env bash
# Builds a pinned local corpus and a distilled study whose hierarchy asserts
# a subtype relation by a stored quotation the pinned corpus does not contain.
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
mkdir -p "$d/evidence"
printf '{"source":"tiny-lib","ref":"main","commit":"%s","scope":"src/","locator_kind":"line-range","read":true,"why":""}\n' "$commit" >"$d/sources.jsonl"
cat >"$d/terms.jsonl" <<'JSON'
{"schema":1,"term":"PortAdapter","definition":"wraps a third-party client behind the port interface","kind":"type","parent":"root","cites":[{"source":"tiny-lib","locator":"src/ports.py:1-2","quote":"Wraps a third-party client behind the port interface."}]}
{"schema":1,"term":"EventBus","definition":"a port adapter that publishes domain events to subscribed handlers","kind":"type","parent":"PortAdapter","cites":[{"source":"tiny-lib","locator":"src/ports.py:5-6","quote":"class EventBus(PortAdapter): Publishes domain events to subscribed handlers."}]}
JSON
cat >"$d/evidence/hierarchy.md" <<'MD'
# Hierarchy

PortAdapter is a type declared at src/ports.py:1-2.

EventBus is a PortAdapter. Support: src/ports.py:5-6 at the pinned commit: "class EventBus(PortAdapter): Publishes domain events to subscribed handlers."
MD
cat >"$d/evidence/vocabulary.md" <<'MD'
# Vocabulary

PortAdapter wraps a third-party client behind the port interface.

EventBus publishes domain events to subscribed handlers.
MD

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
