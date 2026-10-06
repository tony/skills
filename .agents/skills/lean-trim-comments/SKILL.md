---
name: lean-trim-comments
description: >-
  Use when existing source comments or docstrings are bloated, dense,
  repetitive, AI slop, or should be trimmed, debloated, and kept light.
allowed-tools: ["Bash", "Read", "Grep", "Glob", "Edit", "AskUserQuestion"]
metadata:
  argument-hint: "[paths/globs] [--stdin] [--staged] [--all] [--diff-only]"
  source: "plugins/lean/skills/trim-comments/SKILL.md"
---

# this skill

Judge every comment and docstring in the target files against
`references/comment-policy.md`, then delete or rewrite the ones
that fail. Edits in place and prints a diff. Never commits or pushes.

## Confirm before the first edit

This skill deletes code the user did not ask you to touch, and it can
be routed to from a passing remark about comments. Present the
classification and get an explicit yes through `ask-user-choice`
before any `Edit`.

No exceptions: not for a single comment, not for a file the user just
named, not under `--all`. `--diff-only` is the way to skip the edit,
not the confirmation. `--stdin` edits nothing, so it needs none.

Without an interactive question tool (Codex, headless runs), act as
`--diff-only`: print the classification and stop. A request that says
"go ahead and trim" authorizes the edits it names, never a commit.

## `$ARGUMENTS`

- `paths/globs` — files to audit, resolved through `git ls-files --
  <glob>` when tracked, else as literal paths.
- `--stdin` — code pasted in the message or read from stdin; print the
  trimmed code and edit nothing. Pasted code with no paths implies it.
- `--staged` — audit what is staged rather than the branch diff.
- `--all` — audit every tracked file. Expect a large diff; say so
  before confirming.
- `--diff-only` — classify and show what would change, edit nothing.

With no paths, the target set is the files this branch changed.

## Steps

1. **Resolve targets.** With `--stdin` or pasted code, the pasted text
   is the target set; skip to step 2. With paths, expand them. With `--all`, take
   `git ls-files`. With `--staged`, take the staged names:

   ```console
   $ git diff --name-only --cached --diff-filter=d
   ```

   Otherwise find the trunk ref (`git rev-parse --abbrev-ref
   origin/HEAD`, falling back to the repo's default branch) and take
   its merge base:

   ```console
   $ git merge-base HEAD origin/HEAD
   ```

   `origin/HEAD` is read as last fetched and may be stale. Then take
   the names changed since it:

   ```console
   $ git diff --name-only --diff-filter=d <merge-base>
   ```

   Keep source files; drop lockfiles, generated output, and vendored
   trees. Reject an empty target set with a clear message rather than
   widening the scope on your own.

2. **Load the policy and voice.** Read
   `references/comment-policy.md`, then `./AGENTS.md` and
   `./CLAUDE.md`. Where the host project sets its own comment rules,
   those govern.

3. **Classify.** Every comment and docstring in range gets one verdict
   — keep, rewrite, or delete — and a failing gate by name for
   anything not kept. A verdict you cannot attach to a gate is a keep.

   Read the surrounding code first: a comment that looks like narration
   but pins an invariant is a keep.

4. **Preview and confirm.** List one verdict per comment, keeps
   included, grouped by file: old and new text for each rewrite, the
   code each deletion sat above, and the gate that protects each keep.
   Rewrites hold to the policy's two-line ceiling. Rationale the policy
   says belongs in a commit message goes in its own list, so it is not
   lost. Confirm through `ask-user-choice`. Skip for `--diff-only` and
   `--stdin`; for `--stdin`, print the trimmed code instead.

5. **Apply.** Use `Edit`. Rewrites are concrete and shorter than what
   they replace. Do not touch the code itself; a comment that is wrong
   because the code is wrong is a finding to report, not to fix here.

6. **Diff.** Print `git diff -- <targets>`. Skip for `--stdin`.

7. **Report and hand off.** Write it per
   `references/prose-rules.md`. A hero line `N comments: K kept, R rewritten, D deleted` (the
   counts sum to N), `## Verdicts` with the step 4 list, then `## For
   the commit message` with the moved rationale, omitted when none.

   Reply in this shape, as plain text outside any code fence, with plain
   bullets and no bold (never `- **Label:** ...`):

   ```text
   4 comments: 1 kept, 1 rewritten, 2 deleted

   ## Verdicts

   - Deleted "fetches a URL with retries": the name says it.
   - Deleted "retries up to 3 times": repeats MAX_RETRIES.
   - Kept the monotonic-clock note: the loss gate protects it.
   - Rewrote the Windows DNS note to name MAX_RETRIES.

   ## For the commit message

   - Windows runners see a cold DNS cache on the first request.
   ```

   Then offer next steps through `ask-user-choice`: commit, tighten
   the prose too with the `lean-tighten` skill, or discard. Review the printed
   diff first, since `git checkout -- <file>` resets the whole file to
   HEAD and drops any other uncommitted work in it. A commit message
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
