#!/usr/bin/env bash
# Builds a tiny checked-out corpus and a study whose sources.jsonl pins it,
# so extract has something real to harvest and write.
set -euo pipefail

git init --quiet

mkdir -p tiny-lib/src
cat >tiny-lib/src/ports.py <<'PY'
class PortAdapter:
    """Wraps a third-party client behind the port interface."""


class EventBus:
    """Publishes domain events to subscribed handlers."""


class EventHandler:
    """Receives one domain event and acts on it."""
PY
git -C tiny-lib init --quiet
git -C tiny-lib add .
git -C tiny-lib -c user.name=eval -c user.email=eval@example.com commit --quiet -m "Add ports"
git -C tiny-lib tag v1.0.0
commit=$(git -C tiny-lib rev-parse HEAD)

d=notes/ontology/tiny-lib
mkdir -p "$d"
printf '{"source":"https://github.com/example/tiny-lib","ref":"v1.0.0","commit":"%s","scope":"src/","locator_kind":"line-range","read":true,"why":""}\n' "$commit" >"$d/sources.jsonl"

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
