#!/usr/bin/env bash
# Two existing topics that both resemble the one the user names.
set -euo pipefail

for topic in sqlite-wal sqlite-wal-mode; do
  run="out/2026-01-08/research/$topic"
  mkdir -p "$run"
  cat >"$run/index.md" <<MD
---
namespace: research
topic: $topic
subject: $topic
mode: research
audience: private
date: 2026-01-08
prior: null
---

# $topic

## Log

- 2026-01-08: opened
MD
done
