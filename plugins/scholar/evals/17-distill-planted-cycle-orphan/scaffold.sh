#!/usr/bin/env bash
# Builds an extracted study whose hierarchy plants a cycle (stage <-> phase)
# and an orphan (checkpoint has no parent), so distill's gate has findings.
set -euo pipefail

d=notes/ontology/sample-lib
mkdir -p "$d/evidence"
cat >"$d/terms.jsonl" <<'JSON'
{"schema":1,"term":"role","definition":"names the doer a module plays","kind":"type","parent":"root"}
{"schema":1,"term":"stage","definition":"one ordered step of a pipeline","kind":"concept","parent":"phase","cites":[{"url":"https://github.com/example/sample-lib/blob/v1.0.0/src/pipe.py#L3-L4","locator":"src/pipe.py:3-4","quote":"each stage runs once, in order"}]}
{"schema":1,"term":"phase","definition":"a group of stages that share a gate","kind":"concept","parent":"stage","cites":[{"url":"https://github.com/example/sample-lib/blob/v1.0.0/src/pipe.py#L8-L9","locator":"src/pipe.py:8-9","quote":"stages in one phase share a gate"}]}
{"schema":1,"term":"checkpoint","definition":"a saved state a pipeline resumes from","kind":"concept","parent":"","cites":[{"url":"https://github.com/example/sample-lib/blob/v1.0.0/src/pipe.py#L12-L13","locator":"src/pipe.py:12-13","quote":"resume from the last checkpoint"}]}
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
