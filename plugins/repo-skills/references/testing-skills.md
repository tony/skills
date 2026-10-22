# Testing skills

Every skill `/repo-skills:derive` writes is run without itself first and
with itself after, on the same task, by a sub-agent that starts fresh.

## Contents

- The task
- The baseline
- The review fixture
- The with-skill run
- Fixing what leaks
- When to stop

## The task

One realistic request a user would type, chosen to tempt the failure the
skill exists to prevent: a dependency update with a release inside the
cooldown, a gate that a document calls failing, a dev server on a port
the docs get wrong. Ask for a plan or a report under a word limit, with
read-only tool use, so the run is cheap and its claims are checkable.

Before the baseline, verify the facts the answer depends on yourself.
Without them a confident wrong answer reads as a pass.

## The baseline

Brief the sub-agent with the repository path and the task. Forbid the
skill tool and reading `.agents/` and `.claude/`, so it sees only what
any agent sees. A smaller model is a fair proxy. Record each miss:
stale claims it repeated, steps it skipped, mechanisms it bypassed.

A baseline that gets everything right means the skill is not needed.

## The review fixture

A review baseline needs a diff. Build one outside the repository: copy
the files to touch into two trees, edit the second, and diff them:

```console
$ git diff --no-index a b
```

Plant defects only this repository would catch: code in a forbidden
location, a write that bypasses an existing mechanism, a broken house
rule, a behaviour bug with a nameable failing input, an unrelated edit,
a missing test, an export nothing imports. Keep the answer key out of
the prompt.

## The with-skill run

Repeat the task word for word, adding one line: read
`.agents/skills/<name>/SKILL.md` and follow it. Compare against the
baseline's misses and the facts you verified.

## Fixing what leaks

- A fact the agent missed because it lived in another skill: state it
  inline at the step where the miss happens.
- Output with the wrong shape: give the stray content a place in the
  shape (a count, a section) instead of forbidding it.
- A claim the agent checked by outcome when the doc names a mechanism:
  say to check the named tool itself.
- A stale claim in an always-loaded file that the skill contradicts and
  the agent still repeats: report it under stale claims; only fixing
  that file stops it.

## When to stop

Rerun after each fix, at most three rounds per skill. Report the rounds
and anything that still varies between runs.
