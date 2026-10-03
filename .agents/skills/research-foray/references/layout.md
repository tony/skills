# Topic layout

The on-disk contract for research and assessment runs, and the part of it other plugins honor. `topic.py` is the only writer of the files marked *managed*; everything else is yours.

## Where a run lives

```text
<root>/<YYYY-MM-DD>/<namespace>/<topic>/
```

- **root**: `--root`, else `$RESEARCH_ROOT`, else `~/Documents`. On WSL, the Windows user's `/mnt/c/Users/<user>/Documents`: service profiles are skipped, and among several users the one in `PATH` or matching the Linux user wins. When that still leaves several, `topic.py` exits 2 naming them. The default is never the temp directory, and a run never goes inside the repository or corpus being studied.
- **date**: the local calendar day of the run.
- **namespace**: who owns the topic. `research` by default; a plugin's name when a plugin writes the run (`business`, `downstream-users`, `libtmux-port`).
- **topic**: a kebab-case slug. The same slug on different dates is what makes them one topic.

## Inside a run

```text
index.md                 frontmatter (managed) + Question, Scope, Since, Open questions, Log
report.md                the report, per report.md
history/                 earlier versions of report.md, kept when a resumed run rewrites it
data/*.csv               numbers behind findings and exhibits
charts/*.svg             drawn from data/ by topic.py chart
references/
  sources.jsonl          one row per source version (managed, append-only)
  checks.jsonl           verify results (managed, append-only)
  S<n>-<title>.md        a card per source: mirrored frontmatter, then your notes
  raw/<title>-<hash>.*   captures as retrieved; never edited
```

`index.md` frontmatter: `namespace`, `topic`, `subject`, `mode` (research or assessment), `audience` (private, internal, public), `date`, `prior` (the run this one carried from), and optional `redact`, a JSON list of names `scan` flags at internal and public.

## A source row

One id per URL. A row is one version of that source: new bytes, a more exact ref, or a corrected title, author, or quote append a row under the same id, and the newest row is the one in use.

- `id`: `S1`, `S2`, ... Stable across versions and runs, so `[S3]` in a report keeps meaning the same source.
- `url`, and `ref`: the tag, commit, version, or edition the claim rests on. A measured source has `measured:<log file>` in place of a URL. Omit `ref` for an unversioned page; `retrieved` dates it. A URL with the ref in its path (a GitHub blob at a tag) is its own source.
- `title`, `author`.
- `retrieved`: the real UTC time the capture was taken, whatever `--date` names the run. Carrying forward never changes it.
- `sha256` and `file`: the capture's hash and path under `references/`. Null for a URL-only source.
- `capture`: `fetch` when `topic.py` downloaded it (live bytes are comparable), `file` when you saved it.
- `kind`: vendor (the subject's own), independent, or measured (your own test).
- `quotes`: the exact passages claims rest on, each present in the capture; `verify` looks for every one.
- `carried_from`: the run date this row came from. `replaces`: the id of a moved or vanished source this one retires.

A check row: `id`, `version` (a hash of the url, ref, capture hash, and quotes it tested), `checked`, `live`, `status` (ok, unchecked, vanished, moved, changed, misquoted, unreachable), `detail`, and `http`, `final_url`, `live_sha256` when the live check ran. A check counts only while that version is current.

## Reruns

- **Same day:** `open` returns the same run and changes nothing.
- **A later day:** a new dated run. Rows, captures (hard-linked where the filesystem allows), card notes, and the framing in `index.md` (question, criteria, scope, unanswered open questions) carry forward; carried sources are unverified until `verify` passes in the new run. Sources and framing carry, conclusions do not: `data/` and the report stay in the earlier run, to be re-derived or copied on purpose, except that an assessment carries `data/criteria.csv` with its prior ratings to re-rate. Without `--resume`, an earlier run is never written again.
- **`--resume`:** keep writing in the latest run instead, for work that spans days in one place. A visit on a new day is logged under `## Log`, and the report as it stood is kept under `history/`; a second visit the same day changes nothing.
- **The same source again:** an unchanged re-add is a no-op; new bytes or corrected metadata add a version under the same id. A re-add without a capture keeps the old capture.
- **A topic that does not exist yet but resembles one that does:** `open` exits 3 with the candidates and creates nothing, until you name one or pass `--new-topic`.

## Source states

`status` reports each current source as fresh (added this run), verified (a live check of its current version passed), intact (an offline check passed), unchecked (no capture, and no live check), unverified (carried, not yet checked), stale (carried and retrieved over 180 days ago), or the failed check's status. It also counts cards whose notes are still the template, lists assessment criteria rated unknown or citing no source, and lists sources pinned to something that moves.

## For other plugins

A plugin writing dated output follows the path above and puts an `index.md` with frontmatter (`namespace`, `topic`, `date`) in each run; that is all `status` and `prior` need. The rest is optional: a plugin with its own provenance format keeps it.

Compose by invoking the `research:foray` skill with `--namespace <plugin>` and the topic. Where the research plugin is not installed, apply the path and root rules above directly.
