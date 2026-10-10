# Report shape

Shared by `/situate:situate` and the `situational-awareness` skill.

## Contents

- Rules
- Sections
- Example
- Options

## Rules

Exactly one hero line (a missing layer goes under its section, never in
the hero), then these sections in this order, then a next-step
panel. No other headings, no bold label on every bullet, no recap ending.
An empty layer is "none", never "not available"; a lookup that could not
run is `unavailable` with the reason. Never list, count, or mention
untracked editor or shell files. Never name an absolute path or a temp
directory. Report what was found and where, never "I checked", "I read", or "I
haven't tested"; leave out what was not examined rather than narrating
it. Write in the third person: no "I", "I couldn't", or "I can't tell
you". Cite a commit by its subject, never a bare SHA. Never guess at why
someone did something or what they intended. Report only conventions a
file states, never ones inferred from commit history. Tool state (a `gh`
sign-in, a missing network) is `unavailable` with a one-clause reason,
never a finding, gap, or option. Cite a stored conversation with its date
or "undated" when none is recorded; a decision supplied in this session's
context is "earlier in this session".

The hero is `✓ <branch>: <what it does> · <n> commits · PR #<n> <state>`,
or `⚠ <what is blocking or unclear>`. Name a pull request in the hero
only when a lookup found one; an unestablished one is `PR unavailable`,
never "no PR found" or "no PR can exist". When there is nothing to measure
(no commits, or the root is the home directory) the hero is
`⚠ Nothing to measure yet: <why>`. A run that stops early gets one
result sentence, then what the user needs to do.

## Sections

1. `## Position` — branch, trunk, ahead/behind, uncommitted work,
   stashes, and when the refs were last fetched (`last_fetch`), never
   "current". Name each untracked file without saying what it usually
   means. A stale or unknown fetch age is a caveat here, never an option.
   For a pull request subject whose head differs from the checkout, one
   line names the pull request's host, owner, and repository, names the
   checkout's own repository when origin identifies one, and says local
   position does not apply; nothing else about the checkout appears.
2. `## Change` — what the branch does and how far along it is, grouped
   by area, with the commit sequence's shape.
3. `## Pull request` — state, checks by job name, unresolved review
   threads and what they ask for; or the scoped absence/unavailability
   established by the sweep.
4. `## Tickets` — each linked issue with its state and what it asks
   for; or `none is referenced`.
5. `## Conventions` — the rules that bear on this change and the gates
   it must pass.
6. `## Prior work` — only when the prior-conversations layer ran: what
   was decided earlier, when, and whether the repository agrees.
7. `## Open questions` — only blockers and decisions: what is unresolved, mid-flight, or
   contradictory, each tied to evidence in the repository; no prediction
   of what a later session would do, no guess at elapsed time, and no
   cause for a failing check unless its log was read. Anything decided in an earlier conversation and still open
   belongs here, with the provenance described above.

Mark an inference with one hedging word ("probably", "appears"); an
unmarked statement was read. State a blocker only when something is
actually blocked. An open decision that halts unfinished work (a stub
waiting on it, a question an earlier conversation stopped on) is a
blocker: name it in the hero line and in `## Open questions`.

## Example

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
⚠ feat/terse-mode: terse output works, CI is red · 4 commits · PR #12 open

## Position

- feat/terse-mode, 4 commits ahead of main, 0 behind; 2 files uncommitted; no stashes.
- The refs were last fetched 3 days ago, so ahead/behind may be stale.

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

## Options

One option per finding (a gap, failing check, unresolved thread, open
decision), each a distinct action. Never offer "keep working", "continue
the work", or "keep building on" anything. Offer a push or a pull request
only when a finding asks for one. Never propose new tests, refactors, a
merge, or any work no finding asks for.
Change reports what the goal needs, with no style nits or speculation
about future linters.

The panel is an `AskUserQuestion` offering those options (the example
above shows two). Skip it in plan mode. When the tool is absent,
end with numbered options instead, as above.
