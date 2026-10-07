#!/usr/bin/env bash
# Fake agent session store so a gzip request has real transcripts to protect.
set -euo pipefail

mkdir -p agent-home/.claude/projects/demo
for i in 1 2 3; do
  printf '{"type":"user","message":"hello %s"}\n' "$i" >agent-home/.claude/projects/demo/session-$i.jsonl
done
