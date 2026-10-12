# Reply contract

How every procedure's final reply is built. A procedure's `## Output` section names its hero forms, its sections, and its panel options; every other rule about the reply is here. Write the words per `prose-rules.md`.

## Contents

- Shape
- Hero
- Finished work and halted runs
- Sections
- Panel
- Names and placeholders
- Halted examples

## Shape

- Plain text outside any code fence, with plain bullets. No bold, never `- **Label:** ...`.
- Nothing before the hero and nothing after the last section: no recap, no sentence narrating your own edits ("I added..."), no mention of the rules you followed.
- No local paths. Name a run by its date and `<namespace>/<topic>`, and the topics root as "the research root". The one exception: `study-deps` shows its study root as `~/study/...`.
- Copy each section from the run's files; never state beyond them.

## Hero

One line that carries the result. `✓` marks finished work, `⚠` a problem, `?` a decision for the user. Copy every count from the script's output, never from your own tally, and make it equal the bullets or records it counts. `check`'s `counts` holds them: `findings`, `sources`, `carried`, `states`, `ticked`, `open_questions` (distinct open questions across the unchecked items in `index.md` and the report's `## Open questions`), and `open_items` (those plus the failed sources). Before a report exists, copy from `status`.

A hero for a failed gate or failed sources reads `⚠ Not ready: <what failed>` in every procedure, naming the failing checks or the counts by status. `release` writes `⚠ Not released: <failing checks>` when it refused to write.

`claims --reviewed` records the agent's own read of each cited line. Wherever a hero or check line reports it, write "claims reviewed by the agent", never a bare "claims reviewed" that implies an independent check.

## Finished work and halted runs

A halted run could not start or finish because it needs the user or lacks a tool. Its hero begins `? Your call:` or `⚠ Blocked:`. Print the hero as the one result sentence, then one line per thing the user must decide or do, and no sections. When it was blocked before it recorded anything (no shell, a denied tool), add the framing as plain bullets with no lead-in sentence: the question, the scope, and the primary sources you would capture with their pins. Say that nothing was saved.

A report that found problems is finished work: the checks ran and failed, or the verdict stands over a failing check. Any other `⚠` hero (`Not ready`, `Not released`, a verdict with its ship check failing) keeps its procedure's sections, with the problem in the hero and under the section that owns it.

## Sections

Print the sections in the declared order under their verbatim level-2 headings, with no invented sections. Omit a section only when the procedure says to. `## Next` names the one recommended step and carries no options.

## Panel

End with an `AskUserQuestion` panel of next steps. Skip it in plan mode. Without an interactive host, print the options as a numbered list and stop.

- Offer only options that can run now: no verify with no sources recorded, no continue while blocked on network, no release, decision, or export after a failing check.
- The panel never repeats a `## Next` bullet or a section. The procedure lists its own options.

## Names and placeholders

- A run: `<namespace>/<topic> <date>`, as in `research/sqlite-wal 2026-07-14`.
- Counts: `<n>`. A release or bag: `<hash>`. A recipient: `<who>`, a role or group.

## Halted examples

A stopped run:

```text
? Your call: "wal" matches sqlite-wal and postgres-wal.

Name the topic to continue.
```

A run blocked before it could record anything:

```text
⚠ Blocked: Write is denied, so nothing was saved.

- Allow Write, or name where run files may go.
- Question: when does a WAL reader block a writer?
- Scope: the -shm locks and checkpoint modes; not network filesystems.
- Sources to capture: src/wal.c at tag version-3.46.0.
```
