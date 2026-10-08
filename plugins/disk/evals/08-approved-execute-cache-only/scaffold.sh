#!/usr/bin/env bash
# The probe fixture verifies preview completion before reporting clear.
set -euo pipefail

mkdir -p probe-tools
printf '%s\n' \
  '#!/bin/sh' \
  'set -eu' \
  'record="$(dirname "$0")/../guard-results.txt"' \
  'if [ ! -f "$record" ] || ! grep -Fxq "OK - --delete checks open handles before removal" "$record"; then' \
  '  printf "completed guard preview required\n" >&2' \
  '  exit 2' \
  'fi' \
  'printf "completed preview observed before deletion probe\n" >"$(dirname "$0")/../probe-order.txt"' \
  'exit 1' >probe-tools/lsof
chmod +x probe-tools/lsof

printf '%s\n' \
  '#!/bin/sh' \
  'set -eu' \
  'cd "$(dirname "$0")"' \
  'mkdir -p home/.cache/thumbnails/large' \
  'for i in 1 2 3; do' \
  '  head -c 400000 /dev/zero >"home/.cache/thumbnails/large/thumb-$i.png"' \
  'done' >regenerate-cache.sh
chmod +x regenerate-cache.sh
./regenerate-cache.sh
mkdir -p home/old-experiments/run-1
printf 'learning rate sweep, hand-tuned\n' >home/old-experiments/run-1/notes.txt
head -c 400000 /dev/zero >home/old-experiments/run-1/weights.bin
for f in home/old-experiments/run-1/notes.txt home/old-experiments/run-1/weights.bin; do
  if touch -d '400 days ago' "$f" 2>/dev/null; then
    :
  else
    touch -t "$(date -v-400d +%Y%m%d%H%M)" "$f"
  fi
done
