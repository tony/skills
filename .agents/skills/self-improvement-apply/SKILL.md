---
name: self-improvement-apply
description: >-
  Use when applying accepted self-improvement sweep findings to skills as
  individually gated edits and commits.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion", "Task"]
metadata:
  argument-hint: "[<finding id>...] [--dry-run]"
  source: "plugins/self-improvement/skills/apply/SKILL.md"
---

# this skill

Land what the sweep proved. The ledger already carries the evidence
and the change class per finding; this skill turns each one into the
smallest edit that removes the gap, behind the gates that catch a bad
one.

## The rule that makes this safe

```
NO EDIT WITHOUT A LEDGER ENTRY
```

Every edit traces to a finding with a ratio, a spread, a window, and a
verdict. An improvement noticed while working here is out of scope: it
has no usage evidence.

Recompute the ledger key the sweep recorded — the catalog's `HEAD` and
the finding-set digest. A mismatch means the catalog moved since the
sweep: sweep again rather than apply a picture that no longer holds.

## `$ARGUMENTS` contract

Non-flag text selects finding ids; empty takes every accepted finding
in the ledger, in the order the ledger ranked them.

| Flag | Default | Effect |
|---|---|---|
| `--dry-run` | off | Show the edits and the gates each would run, and stop before the first write. |

## Phase 0: Situational awareness

Read the project's conventions files for its commit format and its
quality checks, and confirm the tree is clean. A dirty tree halts:
mixing a catalog edit with unrelated work is how an unreviewable
commit gets made.

## Phase 1: Orchestration plan

Enter plan mode if the host supports it (Claude Code: `EnterPlanMode`;
Cursor / Codex / Gemini: `/plan` or `Shift+Tab`) and present, per
finding: the id, the smallest edit that removes the gap, the files it
touches, and the gate it must clear. Then the commit sequence.

Say which findings you are **not** applying and why. A sweep proposes
more than a catalog should absorb at once.

Wait for approval, then exit plan mode.

## Phase 2: Edit, one finding at a time

Match the edit to the verdict the sweep recorded, not to the
reviewer's instinct:

- A **capability gap** grows behavior the skill did not have.
- A **trust gap** echoes behavior it already performs, so the reader
  can see it fired. This is usually one line and never a new mechanism.
- A **present but not binding** finding never gets another sentence
  restating the rule that already failed. It gets a checked output
  gate, a resolved-and-echoed value, or an argument.

Prefer the smallest shape that works: a default over an argument, an
argument over a new skill. A new skill is the last resort and needs its
marketplace entry, README row, and a description that survives the
collision check.

Strip evidence before it lands: the ledger may quote absolute paths,
hostnames, and client names; a `SKILL.md`, commit, pull request body, or
issue may not.

## Phase 3: Gate each edit

Gate any edit that touches a `description` on the catalog's routing
checks (collision ceiling, description limits) before committing; a
description that reads better while colliding with a sibling makes both
worse. When the catalog ships a router or eval command, feed a redacted
mined prompt through it to confirm the ranking moved as the finding
predicted.

Then run the project's own gates as its conventions define them, plus
whatever regenerates derived manifests. A red gate stops the run at
that finding; report and hand back.

## Phase 4: Commit

One finding, one commit, each behind its own green gate, in the
project's commit format. Describe the defect and the fix in the
project's own terms and do not cite the finding id or the sweep; the
ledger holds that mapping. Write the message per
`references/prose-rules.md`.

## Phase 5: Verify what you wrote

Gates cannot see contradictions in skill prose: a phase that promises
what another forbids, a flag documented as absolute that a panel
overrides, a handoff to a skill that cannot accept the input. Re-read
the edits against the skills they landed in, as an independent
adversarial pass when the host supports sub-agents.

Fix what it finds before handing back. While the branch is unpushed,
amend the commit that introduced the defect; once pushed, the fix lands
as its own commit.

## Output contract

Write the report per `references/prose-rules.md`.

1. Hero block (1–3 lines): `N applied, M skipped` plus the branch.
2. `## Applied` — per finding: the edit, the gates it cleared, and its
   commit subject.
3. `## Skipped` — findings not applied and why, including any the plan
   deliberately held back.
4. `## Verification` — gate commands run and their results, and what
   the adversarial pass found and fixed.
5. End with an `ask-user-choice` panel: open a pull request, sweep
   again, or stop. In a non-interactive run, record the options and
   stop.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
