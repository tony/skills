---
name: respond-goal
description: >-
  Use when the review-and-CI loop should continue through bounded rounds
  until no new actionable feedback remains.
disable-model-invocation: true
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
metadata:
  argument-hint: "[--pr=<num>] [--max-rounds=<n>] [--wait=<minutes>] [--ci-wait=<minutes>] [--no-push] [--reply]"
  source: "plugins/respond/skills/goal/SKILL.md"
---

# this skill

Run the review loop to a stated finish: screen, fix, push, wait for CI
and the repository's review agents, screen what they say, and repeat
until the pull request goes quiet.

Invoked by name, never routed to on the model's initiative: it commits,
pushes, and holds the session open across waits. Invoking it authorizes
the rounds, commits, and pushes described below, and nothing broader.

## Core thesis

The round is easy; stopping is the hard part.

A review loop with no exit condition either quits early, pushing and
declaring victory before any reviewer has looked at the new head, or
never quits at all, re-screening findings the last round already
declined while bots re-post them on every push. Both look like
progress.

So the exit condition is stated **first**, before the first round runs,
and every round is measured against it:

> The loop is finished when a round lands no new fixes, CI is green on
> the current head, and every review agent on the roster has weighed in
> on that head — or when the round cap is reached or the loop goes
> quiet (see Stopping), whichever comes first.

When the host has a standing-goal or stop-condition mechanism, register
that sentence with it so the session cannot quietly stop halfway
(Claude Code: `/goal`). Where there is no such mechanism, restate the
condition at the top of every round; it is the only thing keeping the
loop honest.

## `$ARGUMENTS` contract

| Flag | Default | Effect |
|---|---|---|
| `--pr=<num>` | current branch's PR | The pull request the loop runs against. |
| `--max-rounds=<n>` | `3` | Hard cap on rounds. Reached means stop and report, not raise. |
| `--wait=<minutes>` | `10` | Cap on waiting for review agents per round. |
| `--ci-wait=<minutes>` | `30` | Cap on waiting for CI per round. |
| `--no-push` | off | Run rounds locally; never push. The loop ends after one round, finished when the local gates are green; the CI and review-agent conditions do not apply. |
| `--reply` | off | Post the drafted replies for declined and deferred findings once, when the loop ends. Confirm first; a non-interactive run treats the flag as that confirmation, for the replies shown in the report only. |

## Phase 0: Reconnaissance

1. Resolve the pull request and its head SHA:
   `gh pr view --json number,title,headRefOid,state,isDraft,reviewDecision,statusCheckRollup`.
   No pull request means there is nothing for agents to review: halt
   (see Stopping).
2. Build the review-agent roster per
   `references/review-agents.md`: who reviews this repository,
   through which surface, and whether their arrival is observable. An
   empty roster shortens the loop to CI alone; it is a finding, not an
   error.
3. Resolve the gate buckets and the CI-coverage split per
   `references/verification-gates.md`.
4. Run `git fetch origin`, confirm a clean working tree, and note the
   push state.

## Phase 1: Orchestration plan

Enter plan mode if the host supports it (Claude Code: `EnterPlanMode`;
Cursor / Codex / Gemini: `/plan` or `Shift+Tab`) and present the exit
condition, the roster, the caps in effect, the discovered gate
commands, and what the loop will never do without asking: force-push,
merge, resolve a thread, or rewrite pushed history.

Wait for approval, then exit plan mode. Without plan mode, present the
same inline and proceed on confirmation. In a non-interactive run,
record the plan in the report and proceed.

## Phase 2: The round

Each round is the same six steps.

**1. Collect.** Gather this round's feedback per
`references/feedback-sources.md` — the pull request's reviews,
inline comments, and threads, plus any failing CI. Carry forward the
previous rounds' declines per the re-post rule there.

**2. Screen.** Run the `respond-check` skill on what collected. Its verdicts
settle what this round does.

**3. Act.** Run the `respond-action` skill on the accepted findings, which lands
one gated commit each. A round with no accepted findings skips
straight to the exit test.

Both skills run in loop mode here: this loop's plan approval stands, so
neither enters plan mode or ends with its panel, and the `respond-action` skill
neither pushes nor posts replies. Step 4 pushes and the end of the loop
posts.

**4. Push.** Print the head SHA and the time first and keep the literal
values, since the wait in step 6 depends on both. Push normally; a
rejected push means the remote moved, which is a halt condition, not
something to force through.

**5. Watch CI.** Poll at a steady interval until no check is pending or
`--ci-wait` elapses; stop at the first failure:

```console
$ gh pr checks --json name,bucket,state
```

A failure becomes next round's feedback, with the failing log as its
evidence. Checks still pending at the cap halt the loop.

**6. Wait for the agents.** Poll for reviews and comments against the
new head, bounded by `--wait`, stopping early once every roster agent
has weighed in. Report who never arrived rather than waiting past the
cap — a late agent is picked up by the next round, or by re-entering
the loop later.

Then test the exit condition. Not met and rounds remain → next round.

## Stopping

**Finished** — a round landed no new fixes, CI is green on the current
head, and the roster has weighed in on it.
Under `--no-push`, the local gates are green instead.

**Capped** — `--max-rounds` reached. Report what is still open and what
the next round would do.

**Quiet** — two consecutive rounds that landed no new fixes while the
exit condition stayed unmet because a roster agent never arrived.
More rounds will not change that. Report it as quiet, listing who
never weighed in.

**Halted** — stop the loop and report, without another round:

- No pull request exists (Phase 0). The report offers one local round
  as its first next step.
- A quality gate fails in a way no accepted fix resolves.
- A push is rejected, or the branch needs a rebase or a force-push.
- Screening returns an `ask` verdict that needs the author's intent.
- The working tree is dirty from something the loop did not do.
- CI fails for a reason outside the branch, such as a flaky job, an
  outage, or a missing secret, or is still pending after `--ci-wait`.

Halting is a result. A loop that works around its own halt conditions
is the failure mode this section exists to prevent.

The loop never merges the pull request, never force-pushes, never
resolves a review thread, and never approves anything on a reviewer's
behalf.

## Phase 3: Report — the output contract

Write the report and replies per `references/prose-rules.md`.
Never name local absolute paths or temp files.

A halted run reports one result sentence naming the halt condition,
then what the user needs to do, then `## Still open`; the other
sections appear only when they have content.

1. Hero block (1–3 lines): the outcome (finished, capped, quiet, or
   halted), rounds run, and total fixed / deferred / declined.
2. `## Rounds` — per round: findings collected and from whom, verdicts,
   commits landed, CI result, and which agents weighed in.
3. `## What the fixes added` — the aggregate of every test, comment,
   code path, and dependency the loop introduced, with the finding that
   justified each. This is the number that grows quietly across rounds,
   which is why it is reported across rounds.
4. `## Still open` — deferred findings with follow-up recommendations,
   declined findings with their replies, and any agent that never
   weighed in.
5. `## Verification` — the final head SHA, the CI state on it, and the
   gate commands run.
6. End with an `ask-user-choice` panel (skip inside plan mode): run
   another round past the cap, post the drafted replies, open the
   follow-ups, or stop. When the loop halted for lack of a pull request,
   the first option is one local round with `--no-push`. In a
   non-interactive run, list the options in the report and default to
   stopping.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
