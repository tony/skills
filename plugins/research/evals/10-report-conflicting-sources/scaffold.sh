#!/usr/bin/env bash
# The 2026-01-15 run holds two captured sources that disagree on one default.
set -euo pipefail

day=2026-01-15
run="out/$day/research/wal-threshold"
mkdir -p "$run/references/raw"

cat >docs.md <<'MD'
# Write-Ahead Logging

By default, SQLite runs a checkpoint when the WAL file reaches 1000 pages.
Applications can change this threshold with wal_autocheckpoint.
MD
cat >blog.md <<'MD'
# Tuning SQLite WAL on our servers

On our distribution's build the automatic checkpoint ran every 100 pages,
which surprised us until we found the packager's patch.
MD

row() {
  local id=$1 file=$2 slug=$3 title=$4 author=$5 kind=$6 url=$7 ref=$8 quote=$9
  local sha
  sha=$(sha256sum "$file" | cut -d' ' -f1)
  local raw="raw/$slug-${sha:0:8}.md"
  mv "$file" "$run/references/$raw"
  printf '{"added": "%s", "author": "%s", "capture": "file", "card": "%s-%s.md", "carried_from": null, "file": "%s", "id": "%s", "kind": "%s", "quotes": ["%s"], "ref": "%s", "replaces": null, "retrieved": "%sT09:00:00Z", "sha256": "%s", "title": "%s", "url": "%s"}\n' \
    "$day" "$author" "$id" "$slug" "$raw" "$id" "$kind" "$quote" "$ref" "$day" "$sha" "$title" "$url" \
    >>"$run/references/sources.jsonl"
  printf -- '---\nid: %s\ntitle: %s\n---\n\n# %s\n\nDefault checkpoint threshold.\n' "$id" "$title" "$title" \
    >"$run/references/$id-$slug.md"
}

row S1 docs.md wal-docs "Write-Ahead Logging" SQLite vendor \
  https://sqlite.org/wal.html "" "checkpoint when the WAL file reaches 1000 pages"
row S2 blog.md wal-blog "Tuning SQLite WAL on our servers" "An operator" independent \
  https://blog.example.org/sqlite-wal-tuning 2026-05-01 "the automatic checkpoint ran every 100 pages"

cat >"$run/index.md" <<MD
---
namespace: research
topic: wal-threshold
subject: SQLite WAL checkpoint threshold
mode: research
audience: private
date: $day
prior: null
---

# SQLite WAL checkpoint threshold

## Question

At what WAL size does SQLite checkpoint by default?

## Log

- $day: opened
MD
