# Weave mutating run: refinement, cleanup, and stash restore

Shared by `execute`, `prompt`, and `architecture`, the commands whose workers
write worktrees and whose result lands in the user's checkout. The calling skill
supplies what the passes target, how the winner is chosen, and the adopt
command. `<engine>` and `<session_dir>` are as in `ensemble-core.md`.

## Contents

- Refinement passes
- Remove worktrees and restore the stash
- Apply gate and presentation
- Apply a recorded session

---

## Refinement passes

Skip when `passes` is 1. For pass N of 2 to `passes`, do not re-run the whole
task. Target only the unresolved conflicts from the prior adjudication, the
critic findings from the prior pass, any dimension scored below 5 on any
response, and the quality-gate failures; the skill adds per-file low scores
where it judges file by file.

Before each pass, ask the user to confirm. Under **model-clis**, warn that each
pass spawns external agents billed to other provider accounts. Without
`ask-user-choice`, run extra passes under **subagents** and stop after pass 1
under **model-clis**.

Create the pass and write the targeted prompt to `pass-<N>/prompt.md`:

```console
$ python3 <engine> pass-dir \
    --session "<session_dir>" \
    --pass <N>
```

> The following issues remain from the prior pass. Address ONLY these items:
>
> **Unresolved conflicts**: [from prior adjudication]
> **Critic findings**: [from prior critic.md]
> **Low-confidence areas**: [dimensions and responses scored below 5]
>
> For each item, give your resolution with evidence (file paths, line numbers, code references).

Then repeat the skill's dispatch and analysis phases with pass `<N>`. Keep
every registered worktree and redispatch its participant into the same one,
under either backend. Use a fresh host Task agent with the same complete
`worker_instructions`; reference prior artifacts by path for host workers and
inline them for external CLI lanes.

Re-score only affected dimensions. Stop early when no score moved by more than
1 and no new conflict appeared. Carry the final-pass analysis into the apply
phase.

---

## Remove worktrees and restore the stash

Remove the session's worktrees and branches:

```console
$ python3 <engine> worktrees remove \
    --session "<session_dir>"
```

Check `git diff --stat HEAD` against the plan or patch the user approved, then
restore the user's changes:

```console
$ python3 <engine> stash-restore \
    --session "<session_dir>"
```

On `"conflict": true` the pop was refused or conflicted, and the stash is
intact. Tell the user, in this order: their uncommitted changes are safe in the
stash; its SHA (`stash_sha`); the `overlap` paths that both the result and the
stash changed; then each `recover` command in order, one command per `console`
fence, with `inspect` available to read the stash first. Do not run them
unprompted, and do not drop the stash or suggest dropping it. Then render the
results.

---

## Apply gate and presentation

Show the plan or comparison and wait for the user's confirmation before
touching the main checkout. Without `ask-user-choice`, apply nothing: report
the plan, then remove the worktrees and restore the stash, and render the nothing-applied
opening below. A request that explicitly says to apply the result is that
confirmation for applying, never for committing.

Under either backend, run the repo guard again immediately before adoption,
or before cleanup when nothing was applied. Any drift stops the run without changing or moving the checkout,
removing worktrees, or restoring a stash over it. Preserve recovery evidence
and report the affected paths; never use the nothing-applied opening below.

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
- To apply it without running the workers again, send "weave-execute apply the latest session".
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
   confirmation; without `ask-user-choice`, apply nothing and print the
   picks. An arguments line that asks to apply is that confirmation for
   applying, never for committing.
3. A path in `dirty` has uncommitted changes made after the session. Ask
   whether to skip it; without a question tool, skip it and say which. Never
   overwrite it.
4. Run the skill's `adopt` command with `--session` set to `session_dir`, the
   picks from step 2 minus the skipped paths, then the project's quality gates
   and the skill's `update --event` command. The original run already
   restored the user's stash, so do not restore again. `adopt` refuses the
   whole selection before writing if any target is dirty or has a symlinked
   parent; remove that target from the selection and ask before retrying.
5. Render the results as the skill's last step does.
