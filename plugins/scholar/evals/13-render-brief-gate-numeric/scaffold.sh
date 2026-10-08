#!/usr/bin/env bash
# Builds a study whose hand-written brief carries a URL and bare numbers,
# so the render gate has real findings to report.
set -euo pipefail

d=notes/ontology/sample-lib
mkdir -p "$d/evidence"
cat >"$d/terms.jsonl" <<'JSON'
{"schema":1,"term":"adapter","definition":"wraps a client behind a port","parent":"root","kind":"role","cites":[{"source":"https://github.com/example/sample-lib","quote":"every client enters through a port","locator":"src/ports.py:12-18"}]}
JSON
cat >"$d/sources.jsonl" <<'JSON'
{"source":"https://github.com/example/sample-lib","ref":"v1.0.0","commit":"0000000000000000000000000000000000000000","scope":"src/","read":true,"why":""}
JSON
cat >"$d/brief.md" <<'MD'
# sample-lib vocabulary

The library names its seams ports and adapters.

1. Ports are the interface. See https://github.com/example/sample-lib/blob/v1.0.0/src/ports.py#L12 for the definition.
2. Adapters wrap 14 third-party clients, a 0.62 overlap with the older glossary.
MD
for f in hierarchy vocabulary metrics contested corrections; do : >"$d/evidence/$f.md"; done

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
