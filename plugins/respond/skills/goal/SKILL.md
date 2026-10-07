---
name: goal
description: "Use when the review-and-CI loop should continue through bounded rounds until no new actionable feedback remains."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[<pr-number|url>] [--max-rounds=<n>] [--wait=<minutes>] [--ci-wait=<minutes>] [--push] [--reply]"
user-invocable: true
disable-model-invocation: true
---


# `/respond:goal`

Run the review loop to a stated finish: screen, fix, push (with
`--push`), wait for CI and the repository's review agents, screen what
they say, and repeat until the pull request goes quiet.

It commits and, with `--push`, pushes and holds the session open across
waits, so it runs only when invoked by name. Invoking it authorizes the
rounds and commits described below, and nothing broader; only `--push`
authorizes pushes.

Paths under `../../scripts/` resolve from this skill's directory: print the absolute path once and write it literally in each command, since shell variables do not persist between Bash calls.

## Exit condition

The round is easy; stopping is the hard part. A loop with no exit
condition either declares victory before any reviewer has looked at the
new head, or never quits, re-screening findings the last round declined
while bots re-post them on every push. State the condition before the
first round runs and measure every round against it:

> The loop is finished when a round lands no new fixes, CI is green on
> the current head, and every review agent on the roster has weighed in
> on that head — or when the round cap is reached or the loop goes
> quiet (see Stopping), whichever comes first.

When the host has a standing-goal mechanism (Claude Code: `/goal`),
register that sentence with it; otherwise restate the condition at the
top of every round.

## `$ARGUMENTS` contract

| Flag | Default | Effect |
|---|---|---|
| `<pr-number\|url>` | current branch's PR | Positional. The pull request the loop runs against. |
| `--max-rounds=<n>` | `3` | Hard cap on rounds. Reached means stop and report, not raise. |
| `--wait=<minutes>` | `10` | Cap on waiting for review agents per round. |
| `--ci-wait=<minutes>` | `30` | Cap on waiting for CI per round. |
| `--push` | off | Push after each round and run the CI and review-agent conditions. Without it, run one local round on session or pasted feedback with steps 4-6 skipped, finished when the local gates are green; the report prints the push command. |
| `--reply` | off | Post the drafted replies for declined and deferred findings once, when the loop ends, with the commands in `../action/SKILL.md` Phase 4. Confirm first; a non-interactive run treats the flag as that confirmation, for the replies shown in the report only. |

## Phase 0: Reconnaissance

1. Resolve the pull request and its head SHA:
   `gh pr view --json number,title,headRefOid,state,isDraft,reviewDecision,statusCheckRollup`.
   With `--push`, no pull request means nothing for agents to review:
   halt. Without `--push`, continue on session or pasted feedback,
   skip the roster in step 2 and push, CI, and agent steps 4 to 6 of
   the round; with no feedback either, halt.
2. Build the review-agent roster per
   `../../references/review-agents.md`: who reviews this repository,
   through which surface, and whether their arrival is observable. An
   empty roster shortens the loop to CI alone.
3. Resolve the gate buckets and the CI-coverage split per
   `../../references/verification-gates.md`.
4. Run `git rev-parse --show-toplevel` and halt when it is `$HOME` or
   contains it. Run `git fetch origin`; when it fails, go on with
   provenance marked possibly stale. Confirm a clean working tree and
   note the push state; a dirty tree halts.

## Phase 1: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

The plan covers the exit
condition, the roster, the caps in effect, the discovered gate
commands, and what the loop will never do without asking: force-push,
merge, resolve a thread, or rewrite pushed history.

Wait for approval, then exit plan mode. In a non-interactive run,
record the plan in the report and proceed.

## Phase 2: The round

**1. Collect.** Gather this round's feedback per
`../../references/feedback-sources.md`, including failing CI. Carry
forward the previous rounds' declines per the re-post rule there.

**2. Screen.** Run `/respond:check` on what collected. Its verdicts
settle what this round does.

**3. Act.** Read `../action/SKILL.md` and follow it in loop mode on the
accepted findings, which lands one gated commit each. A round with no accepted findings skips
straight to the exit test.

Both skills run in loop mode here: this loop's plan approval stands, so
neither enters plan mode or ends with its panel, and the action steps
neither push nor post replies. With `--push`, step 4 pushes; the end of
the loop posts.

**4. Push.** Only with `--push`. First print the head SHA
(`git rev-parse HEAD`) and the time (`date -u +%Y-%m-%dT%H:%M:%SZ`) and
keep the literal values, since the wait in step 6 depends on both. Push
normally; a rejected push is a halt condition, never forced.

**5. Watch CI.** The script polls until at least one check exists on
the head and none is pending, stopping at the first failure or at the
cap. It prints a JSON status and exits 0 (green), 1 (failed), 2
(timeout), or 3 (no check appeared within the grace period):

```console
$ python3 ../../scripts/wait_pr.py ci <pr> --timeout <ci-wait>
```

Exit 3 means there is nothing to wait on; say so in the report and test
the exit condition on the agents alone. A failure becomes next round's feedback, with the failing log as its
evidence. A timeout halts the loop.

**6. Wait for the agents.** The script polls reviews and comments until
every named roster login has reviewed the head SHA or commented since
the push time, bounded by `--wait`. It reads reviews and issue comments,
not inline review comments, and ignores a trailing `[bot]` on logins. It
prints the logins still missing:

```console
$ python3 ../../scripts/wait_pr.py agents <pr> --sha <head-sha> --since <push-time-utc> --agents <login> <login> --timeout <wait>
```

Report who never arrived rather than waiting past the cap; a late agent
is picked up by the next round.

Then test the exit condition. Not met and rounds remain → next round.

## Stopping

**Finished** — a round landed no new fixes, CI is green on the current
head, and the roster has weighed in on it.
Without `--push`, the local gates are green instead.

**Capped** — `--max-rounds` reached. Report what is still open and what
the next round would do.

**Quiet** — two consecutive rounds that landed no new fixes while the
exit condition stayed unmet because a roster agent never arrived.
More rounds will not change that. Report it as quiet, listing who
never weighed in.

**Halted** — stop the loop and report, without another round:

- No pull request exists with `--push`, or no pull request and no
  feedback to screen (Phase 0).
- A quality gate fails in a way no accepted fix resolves.
- A push is rejected, or the branch needs a rebase or a force-push.
- Screening returns an `ask` verdict that needs the author's intent.
- The working tree is dirty from something the loop did not do.
- CI fails for a reason outside the branch, such as a flaky job, an
  outage, or a missing secret, or is still pending after `--ci-wait`.

Halting is a result; never work around a halt condition. The loop never merges the pull request, never force-pushes, never
resolves a review thread, and never approves anything on a reviewer's
behalf.

## Phase 3: Report — the output contract

Write the report and replies per `../../references/prose-rules.md`.
Never name local absolute paths, temp files, or internal phase and step
names.

A halted run reports one result sentence naming the halt condition,
then what the user needs to do, then only the sections that have
content, headings included. It never recaps what the
loop inspected. The last example below shows it. In a non-interactive
run, state the plan in one sentence after the hero line and give no
reason for skipping approval.

1. Hero block (1–3 lines): the outcome (finished, capped, quiet, or
   halted), rounds run, and total fixed / deferred / declined.
2. `## Rounds` — per round: findings collected and from whom, verdicts,
   commits landed, CI result, and which agents weighed in.
3. `## What the fixes added` — the aggregate of every test, comment,
   code path, and dependency the loop introduced, with the finding that
   justified each.
4. `## Still open` — deferred findings with follow-up recommendations,
   declined findings with their replies, and any agent that never
   weighed in.
5. `## Verification` — the final head SHA, the CI state on it, and the
   gate commands run.
6. End with an `AskUserQuestion` panel (skip inside plan mode): run
   another round past the cap, post the drafted replies, open the
   follow-ups, or stop. When the loop halted for lack of a pull request,
   no option proposes `--push` until a pull request exists. In a
   non-interactive run, list the options in the report and default to
   stopping.

Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

```text
Finished after 2 rounds on feat/retry-after: 3 fixed, 1 deferred, 1 declined.

## Rounds

- Round 1: 4 findings from alex and lint-bot; 2 accepted, 2 not. 2 commits, CI green, both agents weighed in.
- Round 2: 1 new finding from review-bot; accepted. 1 commit, CI green on the head.

## What the fixes added

- One regression test for the non-numeric header case, justified by round 1 finding 1.

## Still open

- Deferred: split sync_all in a follow-up.
- Declined as improbable: the cache lock; the reply is drafted and not posted.

## Verification

- Head 4f2a9c1, CI green. Ran format, lint, typecheck, and tests.

1. Post the drafted replies
2. Stop
```

A halted run replies in this shape, with the same plain bullets:

```text
Halted before round 1: feat/retry-after has no pull request, and --push was passed.

Open a pull request for the branch, then run /respond:goal again.

1. Stop
```

A non-interactive run states its plan after the hero line:

```text
Finished after 1 round on feat/retry-after: 1 fixed, 0 deferred, 0 declined.

Plan: finish when a round lands no new fixes and CI is green on the head; stop on any halt condition.
```
