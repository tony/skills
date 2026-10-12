# Continue, fill, or expand a topic

## 1. Pick the topic

Use the topic the user names. If the name matches more than one topic, ask which one; without an interactive host, stop and list the candidates. If none is named, run `status.md` and ask; without an interactive host, take `recent` from `status` and say so.

## 2. Open today's run

Follow `start.md` step 2 with the topic's existing slug and no `--subject`, `--mode`, or `--audience`, so the prior ones stay. A new date gives a new run that carries the sources, the framing (question, criteria, scope, unanswered open questions), and every `data/*.csv`; `--resume` keeps writing in the latest run instead. Then read the prior run's `index.md` and `report.md`.

## 3. Re-verify what you carried

```console
$ python3 <topic.py> verify --run <run_dir>
```

Handle failures per `verify.md` step 1 before relying on any carried source.

## 4. Do the work the user asked for

The `flags` from `route` (`foray` SKILL.md) say which mode applies:

- **Continue**, with neither `--fill` nor `--expand`: work the open questions and the prior report's weakest findings, in that order.
- **Fill gaps** (`--fill`): work only the `- [ ]` items under `## Open questions`. Tick each one you settle and cite the source that settled it.
- **Expand** (`--expand=<scope>`): add the new scope to `## Scope` and its questions to `## Open questions` before collecting, then collect per `start.md` step 4.

Record what changed under `## Since <prior date>` as you go: new findings, rating changes, sources that failed or were replaced, conflicts weighed. When `status` listed a released report this run corrects, name it in the reply and offer `release` in the panel. Release only when the user names it.

## 5. Update the report

Write the run's `report.md` per `report.md`, building on the prior report rather than appending to it. Run `check` per `start.md` step 6.

## Output

Open with a one-line hero, `✓ <namespace>/<topic> <date>: carried <n>, verified <n>, ticked <n> open questions`, then exactly these sections. Copy `carried`, `verified` (`states.verified`), and `ticked` from `check`'s `counts`.

1. `## Since <prior date>`: new findings, replaced or failed sources, and rating changes.
2. `## Open`: what is still unanswered.
3. `## Run`: date, `<namespace>/<topic>`, and mode; no path.

Write the reply per `reply-contract.md`.

```text
✓ research/sqlite-wal 2026-07-21: carried 6, verified 6, ticked 1 open questions

## Since 2026-07-14

- Added S7, a postmortem measuring checkpoint latency; it answers the latency question.
- S3 moved to a new URL and was replaced by S8.

## Open

- Whether WAL holds up on network filesystems.

## Run

- 2026-07-21, research/sqlite-wal, research mode.
```

Panel options: keep going, write the report, release the corrected report (only when `status` listed an affected release), stop.
