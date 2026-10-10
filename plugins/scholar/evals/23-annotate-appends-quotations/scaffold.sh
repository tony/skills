#!/usr/bin/env bash
# Builds a study with a prose source and an earlier source's quotation row,
# so annotate has to append rather than replace.
set -euo pipefail

d=notes/ontology/style-guide
mkdir -p "$d/corpus"
cat >"$d/corpus/essay.txt" <<'TXT'
# On Boundaries
Edition: Example Press, 2026, first printing.

## 1. Ports
A port is the line a module's public surface stops at.
Every adapter answers to a port.

## 2. Adapters
The adapter hides which client answers the port.
A caller never learns the client behind an adapter.
TXT
printf '%s\n' '{"source":"corpus/essay.txt","ref":"Example Press, 2026, first printing","commit":"","scope":"sections 1 and 2","locator_kind":"section","read":true,"why":""}' >"$d/sources.jsonl"
printf '%s\n' '{"source":"older-essay","locator_kind":"section","locator":"ch.1","quote":"a seam is where behavior can change without editing in place","note":"the older author names the seam"}' >"$d/quotations.jsonl"

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
