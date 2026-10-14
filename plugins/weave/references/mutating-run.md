# Weave mutating run: refinement, cleanup, and stash restore

Shared by `execute`, `prompt`, and `architecture`, the commands whose workers
write worktrees and whose result lands in the user's checkout. The calling skill
supplies what the passes target, how the winner is chosen, and the adopt
command. `<engine>` and `<session_dir>` are as in `ensemble-core.md`.

## Contents

- Shared phases
- Refinement passes
- Remove worktrees and restore the stash
- Apply gate and presentation
- Apply a recorded session

---

## Shared phases

What `execute`, `prompt`, and `architecture` do alike. Each skill states only
its own differences.

Orchestration plan. A mutating command changes the working tree, so produce an
orchestration plan before any phase. Unless the skill says otherwise, its first
two items are the task scope (what the task changes, and what it must not
touch) and the files (the code the implementations must integrate with, and
the test patterns). The rest are the quality gates (the commands from the
project's AGENTS.md / CLAUDE.md), the workers (the backend, the lanes, and the
pass count), and the apply policy: the user's uncommitted changes are stashed
before workers start and restored at the end, and nothing reaches the main
checkout until the user confirms. Without plan mode, write the plan as
numbered steps in your response. With `AskUserQuestion`, confirm once before
proceeding.
Without it (headless or one-shot runs), print the plan and continue without
asking a text question: nothing reaches the main checkout before the apply
phase, which has its own gate.

Start and dispatch. Follow `ensemble-core.md` (Start the session) with
`--mutating`; the stash holds the user's uncommitted work until the apply
phase. For `execute` and `prompt`, explore the code the task touches, then
build the context packet with snippets of code the implementations must
integrate with, the relevant file list, test patterns, and known unknowns. Their
worker prompt body is:

> Implement the following task in this codebase. Read CLAUDE.md/AGENTS.md for project conventions and follow them strictly.
>
> Task: <the task>
>
> Follow all project conventions from AGENTS.md/CLAUDE.md. Run the project's quality gates after making changes.

Dispatch with `--mutating` and close the repo guard; every participant,
including the `claude` lane under `model-clis`, works in its registered
worktree.

Capture and gates. For each participant, `capture` writes
`diffs/<participant>.patch` and snapshots of changed files to
`files/<participant>/`, and lists `changed` and `deleted` paths:

```console
$ python3 <engine> capture \
    --session "<session_dir>" \
    --pass <N> \
    --participant <participant>
```

In each participant's registered worktree, run the project's gates from
AGENTS.md / CLAUDE.md (formatter, linter, type checker, tests) and write
pass/fail per gate and participant to `pass-NNNN/quality-gates.md`. Judging
goes to the judge participant, whose brief names `files/<participant>/` and the
gate results as readable. Record the pass (`update --completed-passes <N>
--event pass_complete`), and do not render results yet: the user's stash is
still held, so presentation waits for the apply phase.

Selecting files. In file-by-file mode the best versions can come from different
participants; fix cross-file consistency when converging, and select the best version per file from the judge's scores, and
write the analysis (selected version per file, scores, deleted paths,
quality-gate failures) to `pass-NNNN/synthesis.md` per
`prose-rules.md`. Copy the chosen snapshot of each file into the main checkout
and remove each path whose selected version is a deletion; repeat `--pick` and
`--delete` per path. Snapshots, not worktrees, are the source, so this works
after worktrees are gone.

Apply. Never apply a result that fails the quality gates, and never apply one
before the user confirms. Workers are told to stay in their registered
worktrees; recorded drift stops adoption and cleanup until the user decides.
After applying, remove the worktrees and restore the user's changes (Remove
worktrees and restore the stash), checking `git diff --stat HEAD` against the
approved plan; render the results after a stash conflict too.

---

## Refinement passes

Skip when `passes` is 1. For pass N of 2 to `passes`, do not re-run the whole
task. Target only the unresolved conflicts from the prior adjudication, the
critic findings from the prior pass, any dimension scored below 5 on any
response, and the quality-gate failures; a file-by-file skill adds per-file low
scores and re-scores only affected files.

Before each pass, ask the user to confirm. Under **model-clis**, warn that each
pass spawns external agents billed to other provider accounts. Without
`AskUserQuestion`, run extra passes under **subagents** and stop after pass 1
under **model-clis**.

Create the pass and write the targeted prompt as `ensemble-core.md` (Later
passes) says. Then repeat the skill's dispatch and analysis phases with pass `<N>`. Keep
every registered worktree and redispatch its participant into the same one,
under either backend. `worktrees create` reuses valid registrations. If its
identity check fails, stop and preserve the directory; do not remove or
recreate it to retry. Use a fresh host Task agent with the same complete
`worker_instructions`; reference prior artifacts by path for host workers and
inline them for external CLI lanes.

Carry the final-pass analysis into the apply phase.

---

## Remove worktrees and restore the stash

Remove the session's worktrees and branches:

```console
$ python3 <engine> worktrees remove \
    --session "<session_dir>"
```

Both commands refuse while a guard violation is recorded. After the user
decides what to do about the drift, rerun with `--ack-drift`; without a
decision, stop and keep the worktrees and the stash.

Check `git diff --stat HEAD` against the plan or patch the user approved, then
restore the user's changes:

```console
$ python3 <engine> stash-restore \
    --session "<session_dir>"
```

On `"conflict": true` the pop (which uses `--index`, so staging returns with
it) was refused or conflicted, and the stash is intact. Tell the user, in this
order: their uncommitted changes are safe in the stash; its SHA (`stash_sha`);
the `overlap` paths that both the result and the stash changed; then each
`recover` command in order, one command per `console` fence, with `inspect`
available to read the stash first. Name `apply_fallback` with its `when`
reason: it applies without `--index`, so staged changes return unstaged. Do not
run any of them unprompted, and do not drop the stash or suggest dropping it.
Then render the results.

`restore_severed_links` in a `stash-restore` or `guard finish` result is a
note, not a halt: tell the user "these hard links were severed by the stash
restore; git cannot preserve them", and treat `"clean": true` as valid.

---

## Apply gate and presentation

Show the plan or comparison and wait for the user's confirmation before
touching the main checkout. Without `AskUserQuestion`, apply nothing: report
the plan, then remove the worktrees and restore the stash, and render the nothing-applied
opening below. A request that explicitly says to apply the result is that
confirmation for applying, never for committing.

Under either backend, run the repo guard again immediately before adoption,
or before cleanup when nothing was applied. Any drift stops the run without
changing or moving the checkout, removing worktrees, or restoring a stash over
it: `adopt`, `worktrees remove`, and `stash-restore` refuse until the user
decides, and `--ack-drift` records that decision. Preserve recovery evidence
and report the affected paths; never use the nothing-applied opening below.

`adopt` can also stop on the user's own symlink or hard link; the reason
names the path and kind. Report it and ask the user; rerun with
`--replace-aliases` only after they decide. A refusal for a worker symlink
that is absolute or resolves outside the repository is final: report it and
do not rerun.

After applying, run the project's quality gates. All must pass; fix and
rerun otherwise. Remove the worktrees and restore the stash, then render
the results: only now, so a next-step panel never runs while the user's work
is held. Before rendering, follow `ensemble-core.md` (Finish), including its
final state check. Leave the result unstaged for the user to review and never
commit it.

When nothing was applied and `guard finish` returned `"clean": true`, the
reply opens with this and nothing before it. If the session began with dirty
files, add the sentence "Your existing edits and staging are intact."
It replaces the hero, so no `Winner:` or `Best of N` line follows it; the
kind's body sections come next. Say nothing about session files, saved copies,
or unavailable choices. The last bullet names the command with the user's own
`/weave:<command>` and the recorded-session phrase:

```text
Nothing applied: your checkout is unchanged until you confirm.
- Best of 3 implementations: src/cli.py from skeptic, tests/test_cli.py from builder.
- To apply it without running the workers again, send "/weave:execute apply the latest session".
```

After a refused stash restore, put this before the hero, then the kind's
shape:

```text
Your uncommitted changes are safe in a stash (3f2a9c1) and were not restored.
- Overlap: src/cli.py
- Inspect it: git stash show --patch 3f2a9c1
- Recover: run the commands below one at a time.
```

---

## Apply a recorded session

When the arguments ask to apply the latest session ("apply the latest
session", "apply the last run") instead of giving a task, run no workers and
start no new session.

1. Find the session:

   ```console
   $ python3 <engine> latest \
       --command <command>
   ```

   On `"ok": false`, relay `error` in one sentence and stop. When `applied` is
   true, say the session was already applied and stop. When `captured` is
   empty, say that session captured no changes and a new run is needed.
2. Read `pass-NNNN/synthesis.md` (the `pass` the result names) under
   `session_dir`. Show the picks it records and wait for the user's
   confirmation; without `AskUserQuestion`, apply nothing and print the
   picks. An arguments line that asks to apply is that confirmation for
   applying, never for committing.
3. A path in `dirty` is blocked: read its `conflicts` reason. It may have
   uncommitted changes, a committed version that differs from the session's
   base, or an unsafe target. Ask whether to skip it; without a question
   tool, skip it and say which. Never overwrite it. Unrelated commits or a
   branch switch permit explicit application when the selected paths still
   match the recorded base.
4. Run the skill's `adopt` command with `--session` set to `session_dir`, the
   picks from step 2 minus the skipped paths, then the project's quality gates
   and the skill's `update --event` command. The original run already
   restored the user's stash, so do not restore again. `adopt` refuses the
   whole selection before writing if any target conflicts, and refuses an
   already-applied session. Put all approved picks and deletions in one
   invocation. On a target conflict, remove that target from the selection
   and ask before retrying.
5. Render the results as the skill's last step does.
