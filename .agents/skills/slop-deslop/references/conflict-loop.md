# Conflict Loop

The rebase-pause handler for `this skill --apply-rebase`. It runs when
the autosquash rebase, started with `rerere` enabled, stops on a
conflict.

Three rules shape it:

- Run touched-file gates after each pause; the full gate set runs once
  at final verification. This avoids `N × gate-runtime` on a long rebase.
- Skip `TEST_CMD` unless `--run-tests` was passed. Per-pick test runs on
  a long rebase are slow by default.
- Inspect staged files as well as unmerged ones. `rerere.autoupdate=true`
  resolves and stages previously seen conflicts and removes their
  markers, so a loop that reads only unmerged files never gates
  `rerere`'s output.

---

## The loop

1. Inspect unmerged and staged files:

   ```bash
   git diff --name-only --diff-filter=U
   ```

   ```bash
   git diff --name-only --cached
   ```

   The first list holds unresolved conflicts. The second holds manual
   and `rerere` resolutions.

2. For each unmerged file, read it and resolve the markers
   (`<<<<<<<` / `=======` / `>>>>>>>`). Prefer the incoming (fixup) side
   for the targeted lines and keep other structural changes from the
   trunk side. When uncertain, ask through `ask-user-choice` rather than
   guess.

3. Stage explicit paths only; never `git add -A` or `git add .`:

   ```bash
   git add -- <file>
   ```

4. Run the gates on the union of both lists, limited to those files
   where the tool takes a path argument and project-wide otherwise.
   Skip empty buckets:

   ```bash
   ${FORMAT_CMD}
   ```

   ```bash
   ${LINT_CMD}
   ```

   ```bash
   ${TYPECHECK_CMD}
   ```

   If `--run-tests` was passed:

   ```bash
   ${TEST_CMD}
   ```

   - The formatter applies its changes; re-stage what it touched.
   - A linter with `--fix` applies fixes; re-stage. A hard error goes
     to the user through `ask-user-choice`: **Edit and continue**,
     **Skip this fixup** (`git rebase --skip`), or **Abort**
     (`git rebase --abort`).
   - A type checker never modifies files; its errors are hard errors.
   - Test failures get the same triage.

5. Continue:

   ```bash
   git rebase --continue
   ```

6. If the next pick conflicts, or `rerere` resolves another, loop from
   step 1.

7. When recovery is impossible:

   ```bash
   git rebase --abort
   ```

   Report the failing pick and remind the user that the backup branch
   still exists; `git reset --hard <backup>` returns to the pre-run
   state.
