---
name: trim-comments
description: "Use when existing source comments or docstrings are bloated, dense, repetitive, AI slop, or should be trimmed, debloated, and kept light."
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
argument-hint: "[paths/globs] [--stdin] [--staged] [--all] [--diff-only]"
user-invocable: true
---


# `/lean:trim-comments`

Judge comments and docstrings against
`../../references/comment-policy.md`, then delete or rewrite the ones
that fail. By default only comments on lines the branch added or
changed are judged; comments it never touched are left alone. Edits in
place and prints a diff. Never commits or pushes.

## Confirm before the first edit

This skill deletes code the user did not ask you to touch, and it can
be routed to from a passing remark about comments. Present the
classification and get an explicit yes through `AskUserQuestion`
before any `Edit`.

No exceptions: not for a single comment, not for a file the user just
named, not under `--all`. `--diff-only` is the way to skip the edit,
not the confirmation. `--stdin` edits nothing, so it needs none.

Without an interactive question tool (Codex, headless runs), act as
`--diff-only`: print the classification and stop. A request that says
"go ahead and trim" authorizes the edits it names, never a commit.

## `$ARGUMENTS`

- `paths/globs` — files to audit in full, resolved through `git ls-files --
  <glob>` when tracked, else as literal paths.
- `--stdin` — code pasted in the message or read from stdin; print the
  trimmed code and edit nothing. Pasted code with no paths implies it.
- `--staged` — judge comments on staged lines rather than the branch diff.
- `--all` — audit every tracked file in full. Expect a large diff; say
  so before confirming.
- `--diff-only` — classify and show what would change, edit nothing.

With no paths, the scope is the lines this branch added or changed.

## Steps

1. **Resolve targets.** With `--stdin` or pasted code, the pasted text
   is the target set; skip to step 2. With paths, expand them. With
   `--all`, take every tracked file:

   ```console
   $ python3 ../../scripts/scope.py --all
   ```

   With `--staged`:

   ```console
   $ python3 ../../scripts/scope.py --staged
   ```

   Otherwise take the branch scope, which diffs against the merge base
   with the trunk ref (`origin/HEAD` as last fetched, so it may be
   stale; else `main` or `master`):

   ```console
   $ python3 ../../scripts/scope.py
   ```

   The script prints `path<TAB>start-end,...` per file. Exit 2 means no
   trunk ref or no changes: report that and stop rather than widening
   the scope. Keep source files; drop lockfiles, generated output, and
   vendored trees.

2. **Load the policy and voice.** Read
   `../../references/comment-policy.md`, then `./AGENTS.md` and
   `./CLAUDE.md`. Where the host project sets its own comment rules,
   those govern.

3. **Classify.** Every comment and docstring in scope gets one verdict
   (keep, rewrite, or delete) and the gate that decides it: `Loss`,
   `Elite`, or `Upkeep` for a failure, the gate that protects it for a
   keep. On branch and `--staged` runs, judge only comments inside the
   listed line ranges; for paths, `--all`, and pasted code, judge the
   whole text. A verdict you cannot attach to a gate is a keep.

   Read the surrounding code first: a comment that looks like narration
   but pins an invariant is a keep.

4. **Preview and confirm.** List one verdict per comment, keeps
   included, grouped by file: old and new text for each rewrite, the
   code each deletion sat above, and the gate that protects each keep.
   Rewrites hold to the policy's two-line ceiling. Rationale the policy
   says belongs in a commit message goes in its own list, so it is not
   lost. Confirm through `AskUserQuestion`. Skip for `--diff-only` and
   `--stdin`.

5. **Apply.** Use `Edit`. Rewrites are concrete and shorter than what
   they replace. Do not touch the code itself; a comment that is wrong
   because the code is wrong is a finding to report, not to fix here.

6. **Diff.** Print `git diff -- <targets>`. Skip for `--stdin`.

7. **Report and hand off.** Write it per
   `../../references/prose-rules.md`. Shape by mode:

   - `--stdin` and pasted code: the hero line, the trimmed code in one
     fence, `## Verdicts`, then `## For the commit message`.
   - `--diff-only` and runs without a question tool: the hero line,
     `## Verdicts`, then `## For the commit message`; the step 4 list
     is not printed twice.
   - Edited runs: the hero line and one line saying the verdicts are in
     the preview above, then `## For the commit message`.

   The hero line is `N comments: K kept, R rewritten, D deleted`; the
   counts sum to N. Omit `## For the commit message` when nothing moved.

   Reply in this shape, as plain text outside any code fence, with plain
   bullets and no bold (never `- **Label:** ...`):

   ````text
   4 comments: 1 kept, 1 rewritten, 2 deleted

   ```python
   def fetch_with_retry(url):
       ...
   ```

   ## Verdicts

   - Deleted "fetches a URL with retries": fails Elite, the name says it.
   - Deleted "retries up to 3 times": fails Upkeep, repeats MAX_RETRIES.
   - Kept the monotonic-clock note: Loss protects the invariant.
   - Rewrote the Windows DNS note to two lines: fails Elite, argues.

   ## For the commit message

   - Windows runners see a cold DNS cache on the first request.
   ````

   Then offer next steps through `AskUserQuestion`: commit, tighten
   the prose too with `/lean:tighten`, or discard. Without a question
   tool, print the options as a plain list and stop. Review the printed
   diff first, since `git checkout -- <file>` resets the whole file to
   HEAD and drops any other uncommitted work in it. A commit message
   carries no `Co-Authored-By`, no "Generated with" or other tool
   trailer, and no emoji. A stopped run is one result sentence, then
   what the user needs to do.

## What this does not do

- Rewrite prose files; that is `/lean:tighten`.
- Add missing comments. Absence is not a finding here.
