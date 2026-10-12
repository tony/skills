# Topic layout

The on-disk contract for research and assessment runs, and the part of it other plugins honor. `topic.py` is the only writer of the files marked *managed*; everything else is yours.

## Contents

- Where a run lives
- Inside a run
- A source row
- Reruns
- Source states
- Export
- For other plugins

## Where a run lives

```text
<root>/<YYYY-MM-DD>/<namespace>/<topic>/
```

- **root**: `--root`, else `$RESEARCH_ROOT`, else `~/Documents`. On WSL, the Windows user's `/mnt/c/Users/<user>/Documents`: service profiles are skipped, and among several users the one in `PATH` or matching the Linux user wins. When that still leaves several, `topic.py` exits 2 naming them. The default is never the temp directory, and a run never goes inside the repository or corpus being studied.
- **date**: the local calendar day of the run.
- **namespace**: who owns the topic. `research` by default; a plugin's name when a plugin writes the run (`business`, `downstream-users`).
- **topic**: a kebab-case slug. The same slug on different dates is what makes them one topic.

## Inside a run

```text
index.md                 frontmatter (managed) + Question, Scope, Since, Open questions, Log
report.md                the report, per report.md
history/                 earlier versions of report.md, kept when a resumed run rewrites it
releases/                each released report and brief, named by hash (managed)
data/*.csv               numbers behind findings and exhibits
data/<name>.log          a command run through topic.py run (managed)
charts/*.svg             drawn from data/ by topic.py chart
references/
  sources.jsonl          one row per source version (managed, append-only)
  checks.jsonl           verify results (managed, append-only)
  searches.jsonl         each search: query, where, result count, time (managed, append-only)
  conflicts.jsonl        disagreements between sources and how each was weighed (managed)
  releases.jsonl         who received which report version, resting on which sources (managed)
  exports.jsonl          each bag packed: time, file name, file count, bytes, SHA-256 (managed, append-only)
  decisions.jsonl        decisions taken on a release, by whom, and what would reopen them (managed)
  S<n>-<title>.md        a card per source: mirrored frontmatter, then your notes
  raw/<title>-<hash>.*   captures as retrieved; never edited
```

`index.md` frontmatter: `namespace`, `topic`, `subject`, `mode` (research or assessment), `audience` (private, internal, public), `date`, `prior` (the run this one carried from), and optional `redact`, a list of names `scan` flags at internal and public. A public run needs the key set: a list of names, or `[]` as the deliberate "nothing to redact"; `check` fails until it is.

## A source row

One id per URL. A row is one version of that source: new bytes, a more exact ref, or a corrected title, author, or quote append a row under the same id, and the newest row is the one in use.

- `id`: `S1`, `S2`, ... Stable across versions and runs, so `[S3]` in a report keeps meaning the same source. A ledger row that is not valid JSON stops the command with `<file> line <n> is damaged`, because a skipped row would hand its id to the next source. Repair or delete that line only with the user's say-so.
- `url`, and `ref`: the tag, commit, version, or edition the claim rests on. A measured source has `measured:<log file>` in place of a URL. Omit `ref` for an unversioned page; `retrieved` dates it. A URL with the ref in its path (a GitHub blob at a tag) is its own source. `requested_url` holds the address you asked for when `add --fetch` followed a redirect; `url` is then the final one.
- `title`, `author`.
- `retrieved`: the real UTC time the capture was taken, whatever `--date` names the run. Carrying forward never changes it.
- `sha256` and `file`: the capture's hash and path under `references/`. Null for a URL-only source.
- `capture`: `fetch` when `topic.py` downloaded it (live bytes are comparable), `file` when you saved it.
- `response`: for a fetched capture, the server's `status`, `final_url` after redirects, `content_type`, `last_modified`, `etag`, and `date`.
- `unretrieved`: why the source could not be captured. Such a source has no capture and holds no quotes; a source that has a capture cannot be marked unretrieved.
- `kind`: vendor (the subject's own), independent, or measured (your own test).
- `quotes`: the exact passages claims rest on, each present in the capture; `verify` looks for every one.
- `command`, `exit`, `wall_seconds`, `outputs`: for a measured source written by `run`, the argv, its exit status, its wall time, and the SHA-256 of each file it wrote. `run` refuses an output the command left untouched. A re-add without a new capture keeps these fields.
- `carried_from`: the run date this row came from. `replaces`: the id of a moved or vanished source this one retires.

A check row: `id`, `version` (a hash of the url, ref, capture hash, and quotes it tested), `checked`, `live`, `status` (ok, reachable, unchecked, unretrieved, vanished, moved, changed, misquoted, unreachable, unverifiable), `detail`, and `http`, `final_url`, `live_sha256` when the live check ran. A check counts only while that version is current. A measured source's check also re-hashes its outputs: a file edited after the command wrote it is `changed`.

A conflict row: `id` (`C1`, ...), `sources` (two or more source ids), `about`, and once weighed `weight` (the source that carries more), `why`, and `settle` (what evidence would end it). The newest row per id is the one in use.

A release row: `at`, `sha256` and `report` (the snapshot under `releases/`), `to`, `audience`, `live` (false for a release on an offline check), and `cites`, each cited source id mapped to a hash of its url, ref, and capture at release. A decision row: `at`, `decision`, `by`, `release` (the release's sha256), and optional `revisit`.

## Reruns

- **Same day:** `open` returns the same run and changes nothing. A `--mode` or `--audience` that differs from the run's is refused.
- **A later day:** a new dated run. Rows, captures (hard-linked where the filesystem allows), card notes, the search log, recorded conflicts, and the framing in `index.md` (question, criteria, scope, unanswered open questions) carry forward; carried sources are unverified until `verify` passes in the new run. Releases and decisions stay with the run that made them. Sources and framing carry, conclusions do not: the report stays in the earlier run, and every `data/*.csv` is copied across to be updated (an assessment's `criteria.csv` arrives with its prior ratings to re-rate), while logs and charts stay behind.
- **`--resume`:** keep writing in the latest run instead, for work that spans days in one place. A visit on a new day is logged under `## Log` as `resumed` and the report as it stood is kept under `history/`; a second visit the same day changes nothing.
- **Read-only runs:** a run is writable on the calendar day it was opened or resumed, by the clock at the time of the command rather than the run's date. Commands that add evidence or edit authored state (`add`, `run`, `searched`, `conflict`, `sources --write`, `claims --reviewed`) refuse a run last opened or resumed on an earlier day. The records about a run's report (`verify`, `check`, `release`, `decide`, `export`) still write to it; they never change its report, sources, or captures, and `verify` appends only to `checks.jsonl`.
- **The same source again:** an unchanged re-add is a no-op; new bytes or corrected metadata add a version under the same id. A re-add without a capture keeps the old capture.
- **A topic that does not exist yet but resembles one that does:** `open` exits 3 with the candidates and creates nothing, until you name one or pass `--new-topic`.

## Source states

`status` reports each current source in one state of `SOURCE_STATES` in `topic.py`:

- fresh: added this run.
- verified: a live check of its current version passed by comparing content (the fetched bytes, or a recorded quote on the live page), and no later check failed.
- intact: only an offline check passed.
- reachable: the live URL answered, and there was no capture or quote to compare.
- unchecked: no capture, and no live check.
- unretrieved: never captured.
- unverified: carried, not yet checked.
- stale: carried, and retrieved longer ago than the script's staleness window.
- vanished, moved, changed, misquoted, unreachable, unverifiable: the failed check's status.

`status` also counts cards whose notes are still the template, lists assessment criteria rated unknown or citing no source, sources pinned to something that moves, conflicts not yet weighed, and, for each reader, the latest release if it rests on a source that has since changed, failed, or been retired, with the decisions taken on it.

## Export

`export` packs a run into a zipped [BagIt](https://www.rfc-editor.org/rfc/rfc8493) bag beside it (`<topic>-<date>.zip`): every file of the run as the bag's payload, plus `bagit.txt`, `bag-info.txt` (bagging date, the `<namespace>/<topic>/<date>` identifier, payload size), and SHA-256 manifests. It refuses a bag name that exists, re-opens the bag it wrote, removes it if that check fails, and records the zip's SHA-256 in the run's `exports.jsonl` ledger and the run's log. `export --check <bag>` re-hashes the payload and lists what is missing, changed, or unlisted; with `--sha256 <digest>` it also compares the zip itself.

## For other plugins

A plugin writing dated output follows the path above and puts an `index.md` with frontmatter (`namespace`, `topic`, `date`) in each run; that is all `status` and `prior` need. The rest is optional: a plugin with its own provenance format keeps it.

Compose by invoking the `research:foray` skill with `--namespace <plugin>` and the topic. Where the research plugin is not installed, apply the path and root rules above directly.
