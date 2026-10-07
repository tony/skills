---
name: lean-trim-comments
description: >-
  Use when existing source comments or docstrings are bloated, dense,
  repetitive, AI slop, or should be trimmed, debloated, and kept light.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "AskUserQuestion"]
metadata:
  argument-hint: "[paths/globs] [--stdin] [--staged] [--all] [--diff-only]"
  source: "plugins/lean/skills/trim-comments/SKILL.md"
---

# this skill

Judge comments and docstrings against
`references/comment-policy.md`, then delete or rewrite the ones
that fail. By default only comments on lines the branch added or
changed are judged; comments it never touched are left alone. Edits in
place and prints a diff. Never commits or pushes.

The commands below run from the user's directory. Resolve `references/scope.py` against the directory of this SKILL.md (the path it was read from) and write that absolute path literally in each command; shell variables do not persist between Bash calls. Never show that path in the reply.

## Confirm before the first edit

This skill deletes code the user did not ask you to touch, and it can
be routed to from a passing remark about comments. Present the
classification and get an explicit yes through `ask-user-choice`
before any `Edit`.

No exceptions: not for a single comment, not for a file the user just
named, not under `--all`. `--diff-only` and `--stdin` edit nothing, so
they need no confirmation.

Without an interactive question tool (Codex, headless runs), act as
`--diff-only` unless the request itself says "go ahead and trim": that
authorizes the edits it names, never a commit.

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
   $ python3 references/scope.py --all
   ```

   With `--staged`:

   ```console
   $ python3 references/scope.py --staged
   ```

   Otherwise take the branch scope, which diffs against the merge base
   with the trunk ref (`origin/HEAD` as last fetched, so it may be
   stale; else `origin/main`, `origin/master`, `main`, then `master`):

   ```console
   $ python3 references/scope.py
   ```

   The script prints `path<TAB>start-end,...` per file; `--all` prints
   names only, meaning judge the whole file. A path with an empty range
   had only deletions: skip it. Paths are relative to the current
   directory, and untracked files count as added in full. Exit 2 means no
   trunk ref or no changes: report that and stop rather than widening
   the scope. Keep source files; drop lockfiles, generated output, and
   vendored trees.

2. **Load the policy and voice.** Read
   `references/comment-policy.md`, then `./AGENTS.md` and
   `./CLAUDE.md`. Where the host project sets its own comment rules,
   those govern.

3. **Classify.** Every comment and docstring in scope gets one verdict
   (keep, rewrite, or delete) and the gate that decides it: `Loss`,
   `Elite`, or `Upkeep` for a failure, the gate that protects it for a
   keep (`No gate fails` when none fails it), or `Hard keep: directive`, `Hard keep: header`, or
   `Hard keep: sole docstring` for the cases below. On branch and `--staged` runs, judge only comments inside the
   listed line ranges; for paths, `--all`, and pasted code, judge the
   whole text.
   Read the surrounding code first: a comment that looks like narration
   but pins an invariant is a keep. The policy's hard keeps override
   every other verdict: tool directives (`# noqa`, `# type: ignore`,
   `# pragma`, `// eslint-disable`, `# fmt: off`), shebang and encoding
   lines, and license or SPDX headers are never deleted or rewritten,
   and neither is a docstring that is the only statement in its block.
   Label a bloated sole-body docstring `Hard keep: sole docstring` and
   say nothing about how to shorten it.

4. **Preview and confirm.** List one verdict per comment, keeps
   included, grouped by file: old and new text for each rewrite, the
   code each deletion sat above, and the gate or hard-keep label that
   protects each keep.
   Rewrites hold to the policy's two-line ceiling. Rationale the policy
   says belongs in a commit message goes in its own list, so it is not
   lost. Confirm through `ask-user-choice`. Skip for `--diff-only` and
   `--stdin`.

5. **Apply.** Use `Edit`. Rewrites are concrete and shorter than what
   they replace. Do not touch the code itself; a comment that is wrong
   because the code is wrong is a finding to report, not to fix here.
   Never delete a directive or a sole-body docstring, whatever the
   preview said.

6. **Diff.** Print `git diff -- <targets>`; for an untracked target print
   `git diff --no-index -- /dev/null <file>` instead. Skip for `--stdin`,
   `--diff-only`, and runs that edited nothing.

7. **Report and hand off.** Write it per
   `references/prose-rules.md`. Shape by mode:

   - `--stdin` and pasted code: the hero line, the trimmed code in one
     fence, `## Verdicts`, then `## For the commit message`.
   - `--diff-only` and runs that edited nothing: the hero line,
     `## Verdicts`, then `## For the commit message`; the step 4 list
     is not printed twice.
   - Edited runs: the hero line and one line saying the verdicts are in
     the preview above, then `## For the commit message`; the verdicts
     are not repeated.
   - Next steps: a plain list after the last section, with no heading.

   The hero line is `N comments: K kept, R rewritten, D deleted`; the
   counts sum to N. Tally the verdicts before writing any reply text, so
   the first line is final; never recount or correct it inline. A
   comment you shorten or reword is rewritten, not kept; kept means
   the text is unchanged. A rewrite preserves every instruction in the
   original, such as what not to change and what to test first. A rewrite verdict names the gate the
   old text failed, not one the new text passes. The hero comes first,
   with no paragraph before it. Omit `## For the commit message` when nothing moved, and say nothing
   about it. The reply adds no sentence outside the shape, anywhere (not even to
   say nothing was edited or why); do not narrate comments you did not
   judge.

   Reply in this shape, as plain text outside any code fence, with plain bullets, no bold (never `- **Label:** ...`), and no local paths:

   ````text
   5 comments: 2 kept, 1 rewritten, 2 deleted

   ```python
   def fetch_with_retry(url):
       ...
   ```

   ## Verdicts

   - Deleted "fetches a URL with retries": fails Elite, the name says it.
   - Deleted "retries up to 3 times": fails Upkeep, repeats MAX_RETRIES.
   - Kept the monotonic-clock note: Loss protects the invariant.
   - Kept `# noqa: SIM115`: Hard keep: directive.
   - Rewrote the Windows DNS note to two lines: fails Elite, argues.

   ## For the commit message

   - The retry was added after intermittent DNS failures on Windows CI.

   Next steps:
   - Commit the edits
   - Tighten the prose too with `lean-tighten`
   - Discard with `git checkout -- <file>`
   ````

   A `--diff-only` run, with the one comment it judged:

   ````text
   1 comment: 0 kept, 0 rewritten, 1 deleted

   ## Verdicts

   - Deleted "puts the value in the store" above `store[key] = value`: fails Elite, the name says it.

   Next steps:
   - Apply the deletion by running `lean-trim-comments` again with a question tool, or by asking for "go ahead and trim"
   ````

   An edited run:

   ````text
   3 comments: 1 kept, 1 rewritten, 1 deleted

   The verdicts are in the preview above.

   ## For the commit message

   - The cache lock was added after a race on shutdown.

   Next steps:
   - Commit the edits
   - Tighten the prose too with `lean-tighten`
   - Discard with `git checkout -- <file>`
   ````

   `## For the commit message` holds only rationale moved out of a
   deleted or rewritten comment, never text still present in the code or
   in a kept or rewritten comment.

   Then offer next steps through `ask-user-choice`: commit, tighten
   the prose too with the `lean-tighten` skill, or discard. Never offer to widen
   the scope to comments the branch did not touch. Without a question
   tool, print the same options as the plain list above and stop. Offer a
   file option only for files on disk; pasted code has none and is never
   matched to a scaffold file. Review the printed diff first, since
   `git checkout -- <file>` resets a tracked file to HEAD and drops any
   other uncommitted work in it; to discard edits to an untracked file,
   restore the original text you read before editing. A commit message
   carries no `Co-Authored-By`, no "Generated with" or other tool
   trailer, and no emoji. A stopped run is one result sentence, then
   what the user needs to do.

## What this does not do

- Rewrite prose files; that is the `lean-tighten` skill.
- Add missing comments. Absence is not a finding here.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
