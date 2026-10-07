#!/usr/bin/env bash
# One directory per tier: a node_modules (regenerable), an agent session
# store (protected), and a stale directory of unique files.
set -euo pipefail

mkdir -p proj/node_modules/left-pad agent-home/.claude/projects/demo notes-2023/drafts
printf '{"name":"proj","version":"1.0.0","dependencies":{"left-pad":"1.3.0"}}\n' >proj/package.json
printf '{"name":"proj","lockfileVersion":3,"packages":{"node_modules/left-pad":{"version":"1.3.0"}}}\n' >proj/package-lock.json
printf '{"name":"left-pad","version":"1.3.0"}\n' >proj/node_modules/left-pad/package.json
head -c 3000000 /dev/zero >proj/node_modules/left-pad/blob.bin
head -c 2000000 /dev/zero >agent-home/.claude/projects/demo/session-1.jsonl
head -c 1500000 /dev/zero >notes-2023/drafts/thesis-draft.md
if touch -d '500 days ago' notes-2023/drafts/thesis-draft.md 2>/dev/null; then
  :
else
  touch -t "$(date -v-500d +%Y%m%d%H%M)" notes-2023/drafts/thesis-draft.md
fi
