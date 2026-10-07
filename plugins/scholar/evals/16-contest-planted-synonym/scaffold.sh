#!/usr/bin/env bash
# Builds a distilled study whose table plants a synonym pair (two siblings with
# near-identical definitions) and a circular citation, so contest has real
# analyzer findings to judge.
set -euo pipefail

d=notes/ontology/sample-lib
mkdir -p "$d/evidence"
cat >"$d/terms.jsonl" <<'JSON'
{"schema":1,"term":"role","definition":"names the doer a module plays","kind":"type","parent":"root"}
{"schema":1,"term":"update-action","definition":"update one named action to its current version","kind":"verb","parent":"role","cites":[{"url":"https://github.com/example/sample-lib/blob/v1.0.0/src/ops.py#L3-L4","locator":"src/ops.py:3-4","quote":"bump the pinned action"}]}
{"schema":1,"term":"update-actions","definition":"update every named action to its current version","kind":"verb","parent":"role","cites":[{"url":"https://github.com/example/sample-lib/blob/v1.0.0/src/ops.py#L8-L9","locator":"src/ops.py:8-9","quote":"bump every pinned action"}]}
{"schema":1,"term":"ratchet","definition":"a loop that only advances","kind":"concept","parent":"role","cites":[{"url":"https://github.com/example/sample-lib/blob/v1.0.0/src/loop.py#L1-L2","locator":"src/loop.py:1-2","quote":"the ratchet only advances"}]}
JSON
cat >"$d/sources.jsonl" <<'JSON'
{"source":"https://github.com/example/sample-lib","ref":"v1.0.0","commit":"0000000000000000000000000000000000000000","scope":"src/","locator_kind":"line-range","read":true,"why":""}
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
