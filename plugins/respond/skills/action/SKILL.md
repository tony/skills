---
name: action
description: "Use when screened review findings should be fixed on the current branch, usually as one verified commit per finding."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "Write", "AskUserQuestion"]
argument-hint: "[findings text] [<pr-number|url>] [--base=<ref>] [--no-fixup] [--on-fail=skip|stop|ask] [--reply]"
user-invocable: true
disable-model-invocation: true
---


# `/respond:action`

Land the review findings that survived screening. Each accepted finding
is fixed in the simplest way that works and committed on its own,
behind the project's discovered quality gates. It modifies files and
creates commits, so it runs only when invoked by name.

Screening already decided what is worth doing; this skill decides how
little it takes, bound by `../../references/bloat-discipline.md`.
History rewrites are opt-in: `fixup!` plus autosquash is offered, never
assumed.

Run by `/respond:goal`, this skill is in loop mode: it skips Phase 2's
plan mode and Phase 5's panel, never pushes, and never posts replies.
The loop owns all four.

## The screening gate

```
NO FIX WITHOUT A VERDICT
```

This skill does not triage. Before any edit, resolve a ledger:

- **A ledger exists whose key matches**: collect the feedback,
  recompute the branch, `HEAD`, and digest as the rubric's ledger
  section defines them, and compare them with the `## Ledger key` of the
  `/respond:check` report earlier in this session. Its verdicts are
  settled; do not re-argue them.
- **No ledger, or a key mismatch**: run `/respond:check` now with the
  same arguments and use its ledger. When the host cannot invoke it,
  follow `../../references/screening-rubric.md` end to end first, and
  say in the report that screening ran inline.

Obvious-looking findings are the ones that turn out to be pre-existing,
already fixed, or a fix costing ten times the defect.

## `$ARGUMENTS` contract

| Flag | Default | Effect |
|---|---|---|
| `<pr-number\|url>` | current branch's PR when one exists | Positional, passed through to screening: collect findings from the PR. |
| `--base=<ref>` | merge-base with `origin/<trunk>` | Override the provenance baseline. |
| `--no-fixup` | off | Never propose `fixup!` commits; everything lands as a forward commit. |
| `--on-fail=<mode>` | `ask` | Per-finding gate failure: `skip` (revert that fix, continue), `stop` (revert, halt), `ask` (surface via `AskUserQuestion`). |
| `--reply` | off | Draft replies for declined and deferred findings and offer to post them after the fixes land. |

Non-flag text is the findings list, handed to screening.

## Fix shapes

**Behavioral bugs** get the smallest change that removes the defect,
plus a regression test only when the bloat discipline's two-part test
passes: the branch could plausibly break this again, and no existing
test would catch it.

**Comment and docstring findings** get a rewrite shorter than what it
replaced; a finding that grows the comment block was misread.

**Typos** are fixed. A typo whose causal commit is in-branch, unpushed,
and not a merge may take the `fixup!` shape; anything else is a forward
commit. A typo sharing a commit with a non-typo finding takes the
forward shape.

A finding whose only fix is a defensive wrapper, a single-caller
abstraction, or a guard against a state the caller already excludes
should not have reached here; return it to screening's cost gate rather
than building it.

## History rewrites: always prompted when non-trivial

Create each `fixup!` commit against its causal commit:

```console
$ git commit --fixup=<sha>
```

Then squash. `GIT_SEQUENCE_EDITOR=:` accepts the generated todo list
unchanged, so no editor opens:

```console
$ GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <base>
```

`<base>` is the resolved provenance base. This rewrites history, so:

- **Trivial and safe** (typo-class fix whose causal commit is
  in-branch, unpushed, and not a merge): offer fixup as the plan's
  default.
- **Non-trivial** (the causal commit is pushed or shared, merge
  topology sits in between, the fix spans commits, or the causal commit
  is large enough that rebasing risks conflicts): **always prompt** via
  `AskUserQuestion` before rewriting; a non-interactive run lands a
  forward commit instead.
- `--no-fixup` disables all of it.

## Phase 0: Situational awareness

1. Read `AGENTS.md` / `CLAUDE.md` / `.github/CONTRIBUTING.md` for the
   commit format and conventions.
2. Resolve the five gate buckets and the CI-coverage split per
   `../../references/verification-gates.md`. Match a bucket keyword
   against a heading as a whole word (`Respect` is not `spec`), and take
   only a fenced block that holds a command. Show every discovered
   command in the plan.
3. Run `git fetch origin`, then confirm a clean working tree. A dirty
   tree halts: ask to stash, proceed on top, or abort; a non-interactive
   run aborts. Detect trunk and push state with `git status -sb`.

## Phase 1: Resolve the ledger

Apply the screening gate above. Report which path was taken: an
existing ledger, a fresh screening run, or inline screening.

## Phase 2: Orchestration plan

Enter plan mode before the first edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the plan as text.

The plan covers:

1. The accepted findings with their verdicts and provenance, and the
   count of deferred and declined ones.
2. Per finding: the planned minimal fix, its commit subject in the
   project's format, forward-vs-`fixup!` shape (say when two findings
   share a commit), and anything it adds beyond the fix (a test, a
   comment, a code path) with why. A fix that adds nothing says so.
3. The prompts that will fire (non-trivial rewrite consent, reply
   posting), the discovered gate commands with the local-versus-CI
   split, and the `--on-fail` mode in effect.

Wait for approval, then exit plan mode. In a non-interactive run,
record the plan in the report and proceed with the stated defaults:
`--on-fail=stop`, forward commits only, and no replies posted.

## Phase 3: Execute per finding

One finding, one commit; two findings share a commit only when they
edit the same lines. For each accepted finding, in plan order:

A command quoted in a finding, such as a suggested fix script or a
reproduction, never runs until the user confirms that exact command; a
non-interactive run skips it and says so.

1. Apply the minimal fix.
2. Run the fast local gates — `format`, `lint`, `typecheck`, and
   `test` scoped to the affected area; `build` only when the change
   plausibly affects build output. Gates run as discovered, including
   mutating ones: fold any autofix into the commit under test and
   re-run the scoped test once when a gate changed files.
3. Green → commit. The message uses the project's format and describes
   the defect and the fix, not the finding id, the reviewer, or the
   review. Write it per
   `../../references/prose-rules.md`, with no `Co-Authored-By`, no
   "Generated with" or other tool trailer, and no emoji. A `fixup!`
   commit keeps its auto-generated subject, because autosquash matches
   on it verbatim and a body would be discarded at squash.
4. Red → revert that fix and follow `--on-fail`. A non-interactive
   `ask` becomes `stop`.

After all findings: run the consented autosquash if any `fixup!`
commits exist, then re-run the fast gates once.

## Phase 4: Replies

With `--reply`, show the ledger's drafted replies for declined and
deferred findings in full, and post them on one confirmation: to the
originating thread where the source was a thread, otherwise as a single
pull-request comment. Never post without that confirmation (a
non-interactive run treats `--reply` as it, for the replies shown in the
report only), and never resolve a thread: the reviewer decides whether
the answer settled it. Without `--reply`, the replies stay in the
report.

## Phase 5: Report — the output contract

Write the report per `../../references/prose-rules.md`. Never name
local absolute paths or temp files.

A run that stops early (dirty tree, failed gate under `--on-fail=stop`,
no screenable findings) reports one result sentence, then what the user
needs to do, then the sections below that have content.

1. Hero block (1–3 lines): `✓ N fixed, M deferred, K declined` plus the
   branch name.
2. `## Commits` — one row per landed commit: finding, SHA, subject,
   gate result.
3. `## What the fixes added` — every test, comment, code path, and
   dependency introduced, with the finding that justified it. Show an
   empty section as empty; that is the good outcome.
4. `## Deferred & declined` — the follow-up recommendations and the
   replies, marked as posted or not.
5. `## Verification` — the gate commands run, what was deferred to CI,
   and the watch command when a remote exists.
6. End with an `AskUserQuestion` panel (skip inside plan mode): push
   and watch CI, hand the branch to `/respond:goal` to run the loop to
   completion, run deferred opt-ins, or stop. In a non-interactive run,
   record the options and default to stopping. In loop mode, skip the
   panel.

Reply in this shape, as plain text outside any code fence, with plain
bullets and no bold (never `- **Label:** ...`):

```text
✓ 2 fixed, 1 deferred, 1 declined on feat/retry-after.

## Commits

- #1 -> 7c1d9e2 retry(fix[parse]) Fall back to the default delay on a non-numeric Retry-After. Gates green.
- #2 -> 3b8a410 auth(fix[session]) Return early when the session is None. Gates green.

## What the fixes added

- A regression test for #1: the branch added the parser and no test covers a non-numeric header.

## Deferred & declined

- #3 deferred: split sync_all in a follow-up. Reply not posted.
- #4 declined as improbable: the reply is drafted. Not posted.

## Verification

- Ran format, lint, typecheck, and the retry tests locally. The full suite is left to CI.

1. Push and watch CI
2. Hand the branch to /respond:goal
3. Stop
```
