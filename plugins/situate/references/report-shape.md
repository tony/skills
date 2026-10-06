# Report shape

Shared by `/situate` and the `situational-awareness` skill.

One hero line, then these sections in this order, then a next-step
panel. No other headings, no bold label on every bullet, no recap ending.
An empty layer is "none", never "not available".

The hero is `✓ <branch>: <what it does> · <n> commits · PR #<n> <state>`,
or `⚠ <what is blocking or unclear>`. A run that stops early gets one
result sentence, then what the user needs to do.

1. `## Position` — branch, trunk, ahead/behind, uncommitted work,
   stashes, and how stale the trunk ref is.
2. `## Change` — what the branch does and how far along it is, grouped
   by area, with the commit sequence's shape.
3. `## Pull request` — state, checks by job name, unresolved review
   threads and what they ask for; or `none is open`.
4. `## Tickets` — each linked issue with its state and what it asks
   for; or `none is referenced`.
5. `## Conventions` — the rules that bear on this change and the gates
   it must pass.
6. `## Prior work` — only when the prior-conversations layer ran: what
   was decided earlier, when, and whether the repository agrees.
7. `## Open questions` — what is unresolved, mid-flight, or
   contradictory, and what a resumed session would most likely get
   wrong. Anything decided in an earlier conversation and still open
   belongs here, with its date.

Mark an inference with one hedging word ("probably", "appears"); an
unmarked statement was read. State a blocker only when something is
actually blocked. An open decision that halts unfinished work (a stub
waiting on it, a question an earlier conversation stopped on) is a
blocker: name it in the hero line and in `## Open questions`.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
⚠ feat/terse-mode: terse output works, CI is red · 4 commits · PR #12 open

## Position

- feat/terse-mode, 4 commits ahead of main, 0 behind; 2 files uncommitted; no stashes.
- The main ref was last updated 3 days ago, so ahead/behind may be stale.

## Change

- Adds a terse output mode to the formatter and wires it to `--terse`.
- The last commit starts a type cleanup that is unfinished.

## Pull request

- Open, ready for review. The type-check job fails on three files the branch added.
- One unresolved thread asks for a test of the `--terse --json` combination.

## Tickets

- #88 is open and asks for a terse mode; the branch covers it.

## Conventions

- Commit subjects use `scope(type[detail])`; the gates are lint, typecheck, and the unit tests.

## Open questions

- Whether the unfinished type cleanup belongs on this branch.

1. Fix the three type errors and push
2. Address the unresolved review thread
```

The panel is an `AskUserQuestion` offering next steps (continue the
work, address the review threads, open a pull request, widen the sweep
to prior conversations). Skip it in plan mode. When the tool is absent,
end with numbered options instead, as above.
