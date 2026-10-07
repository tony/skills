# Weave mutating run: refinement, cleanup, and stash restore

Shared by `execute`, `prompt`, and `architecture`, the commands whose workers
write worktrees and whose result lands in the user's checkout. The calling skill
supplies what the passes target, how the winner is chosen, and the adopt
command. `<engine>` and `<session_dir>` are as in `ensemble-core.md`.

## Contents

- Refinement passes
- Reset the main checkout
- Remove worktrees and restore the stash

---

## Refinement passes

Skip when `passes` is 1. For pass N of 2 to `passes`, do not re-run the whole
task. Target only the unresolved conflicts from the prior adjudication, the
critic findings from the prior pass, any dimension scored below 5 on any
response, and the quality-gate failures; the skill adds per-file low scores
where it judges file by file.

Before each pass, ask the user to confirm. Under **model-clis**, warn that each
pass spawns external agents billed to other provider accounts. Without
`AskUserQuestion`, run extra passes under **subagents** and stop after pass 1
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

Then repeat the skill's dispatch and analysis phases with pass `<N>`, reusing
each participant's work:

- **subagents**: keep every worktree and redispatch a fresh role-matched
  sub-agent into the same one.
- **model-clis**: discard the main-tree changes and rebuild the external
  worktrees with fresh branches. Run both commands, then create the worktrees
  again as in the skill's dispatch phase. Reference prior artifacts by path for
  `claude` and inline them for external lanes.

  ```console
  $ python3 <engine> reset-main \
      --session "<session_dir>"
  ```

  ```console
  $ python3 <engine> worktrees remove \
      --session "<session_dir>"
  ```

Re-score only affected dimensions. Stop early when no score moved by more than
1 and no new conflict appeared. Carry the final-pass analysis into the apply
phase.

---

## Reset the main checkout

Under **model-clis**, the `claude` lane's agent wrote the main checkout. Discard
its changes before applying a result. The command refuses unless the user's
stash is recorded and still present:

```console
$ python3 <engine> reset-main \
    --session "<session_dir>"
```

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
