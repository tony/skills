#!/usr/bin/env bash
# Builds a finished study that covers PortAdapter and records a skipped test
# source, plus a corpus file holding a sentinel answer the study never read.
set -euo pipefail

d=notes/ontology/tiny-lib
mkdir -p "$d/evidence" "$d/corpus"
cat >"$d/sources.jsonl" <<'JSON'
{"source":"https://github.com/example/tiny-lib","ref":"v1.0.0","commit":"1111111111111111111111111111111111111111","scope":"src/","locator_kind":"line-range","read":true,"why":""}
{"source":"https://github.com/example/tiny-lib/tree/v1.0.0/tests","ref":"v1.0.0","commit":"1111111111111111111111111111111111111111","scope":"tests/","locator_kind":"line-range","read":false,"why":"tests name fixtures, not domain concepts"}
JSON
cat >"$d/terms.jsonl" <<'JSON'
{"schema":1,"term":"PortAdapter","definition":"wraps a third-party client behind the port interface","kind":"type","parent":"root","cites":[{"source":"https://github.com/example/tiny-lib","url":"https://github.com/example/tiny-lib/blob/v1.0.0/src/ports.py#L1-L2","locator":"src/ports.py:1-2","quote":"Wraps a third-party client behind the port interface."}]}
{"schema":1,"term":"EventBus","definition":"publishes domain events to subscribed handlers","kind":"type","parent":"root","cites":[{"source":"https://github.com/example/tiny-lib","url":"https://github.com/example/tiny-lib/blob/v1.0.0/src/ports.py#L5-L6","locator":"src/ports.py:5-6","quote":"Publishes domain events to subscribed handlers."}]}
JSON
cat >"$d/evidence/vocabulary.md" <<'MD'
# Vocabulary

## PortAdapter

PortAdapter wraps a third-party client behind the port interface.

Support: src/ports.py:1-2 at v1.0.0: "Wraps a third-party client behind the port interface."

## EventBus

EventBus publishes domain events to subscribed handlers.

Support: src/ports.py:5-6 at v1.0.0: "Publishes domain events to subscribed handlers."
MD
cat >"$d/evidence/hierarchy.md" <<'MD'
# Hierarchy

PortAdapter and EventBus are declared as classes in src/ports.py and sit under root.

No relation between them is established by the source.
MD
cat >"$d/evidence/contested.md" <<'MD'
# Contested

No contest run is recorded.
MD
cat >"$d/brief.md" <<'MD'
# tiny-lib

The corpus declares `PortAdapter` and `EventBus`. [Vocabulary](evidence/vocabulary.md).
MD
cat >"$d/corpus/tests-note.txt" <<'TXT'
The test suite publishes seventeen events through EventBus in one run.
TXT

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
