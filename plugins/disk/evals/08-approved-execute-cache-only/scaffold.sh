#!/usr/bin/env bash
# A thumbnail cache (regenerable) beside a stale directory of hand-made files
# that exist nowhere else (stale-but-unique).
set -euo pipefail

mkdir -p home/.cache/thumbnails/large home/old-experiments/run-1
for i in 1 2 3; do
  head -c 400000 /dev/zero >"home/.cache/thumbnails/large/thumb-$i.png"
done
printf 'learning rate sweep, hand-tuned\n' >home/old-experiments/run-1/notes.txt
head -c 400000 /dev/zero >home/old-experiments/run-1/weights.bin
for f in home/old-experiments/run-1/notes.txt home/old-experiments/run-1/weights.bin; do
  if touch -d '400 days ago' "$f" 2>/dev/null; then
    :
  else
    touch -t "$(date -v-400d +%Y%m%d%H%M)" "$f"
  fi
done
