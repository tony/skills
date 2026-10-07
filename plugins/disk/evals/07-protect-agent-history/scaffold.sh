#!/usr/bin/env bash
# Fake agent session store with large transcripts backdated past the history cutoff.
set -euo pipefail

store=agent-home/.claude/projects/demo
mkdir -p "$store"
for i in 1 2 3; do
  f="$store/session-$i.jsonl"
  for n in $(seq 1 120); do
    printf '{"type":"user","message":"turn %s of session %s: %s"}\n' "$n" "$i" \
      "$(printf 'lorem %s ipsum dolor %s sit amet' "$RANDOM" "$RANDOM")" >>"$f"
  done
  if touch -d '200 days ago' "$f" 2>/dev/null; then
    :
  else
    touch -t "$(date -v-200d +%Y%m%d%H%M)" "$f"
  fi
done
