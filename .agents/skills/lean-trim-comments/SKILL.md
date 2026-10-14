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

The commands below run from the user's directory. Resolve `references/scope.py` and `references/tally.py` against the directory of this SKILL.md (the path it was read from) and write that absolute path literally in each command; shell variables do not persist between Bash calls. Never show that path in the reply.

## Confirm before the first edit

This skill deletes code the user did not ask you to touch, and it can
be routed to from a passing remark about comments. Present the
classification and get an explicit yes through `ask-user-choice`
before any `Edit`.

No exceptions: not for a single comment, not for a file the user just
named, not under `--all`. `--diff-only` and `--stdin` edit nothing, so
they need no confirmation.

Without a question tool, act as
`--diff-only` unless the request itself says "go ahead and trim": that
authorizes the edits it names, never a commit.

## `$ARGUMENTS`

- `paths/globs` — files to audit in full, resolved by `scope.py --paths`.
- `--stdin` — code pasted in the message or read from stdin; print the
  trimmed code and edit nothing. Pasted code with no paths implies it.
- `--staged` — judge comments on staged lines rather than the branch diff.
- `--all` — audit every tracked file in full. Expect a large diff; say
  so before confirming.
- `--diff-only` — classify and show what would change, edit nothing.

With no paths, the scope is the lines this branch added or changed.

## Steps

1. **Resolve targets.** With `--stdin` or pasted code, the pasted text
   is the target set; skip to step 2. With paths, resolve them; a path that
   matches no file exits 2: report it and stop:

   ```console
   $ python3 references/scope.py --paths <paths/globs>
   ```

   With `--all`, take every tracked file:

   ```console
   $ python3 references/scope.py --all
   ```

   With `--staged`:

   ```console
   $ python3 references/scope.py --staged
   ```

   Otherwise take the branch scope, which diffs against the merge base
   with the first trunk ref that resolves among `origin/HEAD` (as last
   fetched, so it may be stale), `origin/main`, `origin/master`, `main`,
   and `master`:

   ```console
   $ python3 references/scope.py
   ```

   The script prints `path<TAB>start-end,...` per file; `--all` prints
   names only, meaning judge the whole file; `--paths` prints
   `path<TAB>tracked|untracked|deleted`, also meaning the whole file. A path with an empty range
   had only deletions: skip it. Paths are relative to the current
   directory, and untracked files count as added in full. Exit 2 means not a git
   repository, no trunk ref, no merge base with it, or no changes; the
   script prints which on stderr: report it and stop rather than widening
   the scope. A `--paths` row marked `deleted` has no text to judge: skip it. The script already leaves out lockfiles, vendored trees, and
   generated files, and names any untracked file it skipped on stderr;
   do not judge a skipped file.

2. **Load the policy and voice.** Read
   `references/comment-policy.md`, then `./AGENTS.md` and
   `./CLAUDE.md`. Where the host project sets its own comment rules,
   those govern.

3. **Classify.** Every comment and docstring in scope gets one verdict
   (keep, rewrite, or delete) and the gate that decides it: `Loss`,
   `Elite`, or `Upkeep` for a failure, the gate that protects it for a
   keep (`No gate fails` when none fails it), or the policy's hard-keep
   label (`Hard keep: directive`, `Hard keep: header`, or
   `Hard keep: sole docstring`). On branch and `--staged` runs, judge only comments inside the
   listed line ranges; for paths, `--all`, and pasted code, judge the
   whole text.
   Read the surrounding code first: a comment that looks like narration
   but pins an invariant is a keep. The policy's hard keeps override
   every other verdict and are never deleted or rewritten. Label a
   bloated sole-body docstring `Hard keep: sole docstring` and say
   nothing about how to shorten it.

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

6. **Diff.** For a tracked target print `git diff -- <file>`; for an
   untracked one print `git diff --no-index -- /dev/null <file>`. Skip for `--stdin`,
   `--diff-only`, and runs that edited nothing.

7. **Report and hand off.** Write it per
   `references/prose-rules.md`. Reply as plain text outside any
   code fence, with plain bullets, no bold (never `- **Label:** ...`),
   and no local paths. The reply adds no sentence outside the shape,
   anywhere (not even to say nothing was edited or why); do not narrate
   comments you did not judge. A stopped run is one result sentence,
   then what the user needs to do. Build the reply in these parts.

   **7a. Verdict bullets and hero.** Draft one bullet per comment first,
   each starting `Kept`, `Rewrote`, or `Deleted`. A comment you shorten
   or reword is rewritten, not kept; kept means the text is unchanged. A
   rewrite preserves every instruction in the original, such as what not
   to change and what to test first, adds no fact the original lacks,
   and names the gate the old text failed, not one the new text passes.
   Pipe the bullets to the tally and paste its line as the hero, first,
   with no paragraph before it; never recount or correct it inline:

   ```console
   $ python3 references/tally.py
   ```

   The hero line reads `N comments: K kept, R rewritten, D deleted`.

   **7b. Commit-message section.** `## For the commit message` holds only
   rationale moved out of a deleted or rewritten comment, never text
   still present in the code or in a kept or rewritten comment. Omit it,
   and say nothing about it, when nothing moved.

   **7c. Shape for `--stdin` and pasted code.** Hero, the trimmed code in
   one fence, `## Verdicts`, then `## For the commit message`. Pasted
   code has no file: never offer a file option or match it to a scaffold
   file.

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
   - Tighten the prose too with `lean-tighten`
   ````

   **7d. Shape for `--diff-only` and runs that edited nothing.** Hero,
   `## Verdicts`, then `## For the commit message`, with no fenced code
   (the step 4 list is not printed twice).

   ````text
   2 comments: 0 kept, 0 rewritten, 2 deleted

   ## Verdicts

   - Deleted "fetches a URL with retries": fails Elite, the name says it.
   - Deleted "retries up to 3 times": fails Upkeep, repeats MAX_RETRIES.

   Next steps:
   - Apply the deletions
   ````

   **7e. Shape for edited runs.** Hero, the line "The verdicts are in
   the preview above." in place of `## Verdicts`, then
   `## For the commit message`.

   ````text
   3 comments: 1 kept, 1 rewritten, 1 deleted

   The verdicts are in the preview above.

   ## For the commit message

   - The retry was added after intermittent DNS failures on Windows CI.

   Next steps:
   - Commit the edits
   - Tighten the prose too with `lean-tighten`
   - Discard with `git checkout -- <file>`
   ````

   **7f. Next steps.** Follow `references/handoff.md`: commit,
   tighten the prose too with the `lean-tighten` skill, or discard. Never offer to
   widen the scope to comments the branch did not touch.

## What this does not do

- Rewrite prose files; that is the `lean-tighten` skill.
- Add missing comments. Absence is not a finding here.


## Portability notes

- `ask-user-choice` — present the listed options and wait for the user to pick one. Hosts with a structured multiple-choice tool (Claude Code's `AskUserQuestion`) should use it; otherwise print a numbered list and wait for a numbered reply. Never proceed on an assumed answer.
- `$ARGUMENTS` — the text the user passed when invoking this skill. If your host does not substitute it, read it as the user's request in the current turn, and ask when there is none.
- Bundled files — every relative path in this skill points at a file shipped inside this skill directory. Read them from here, not from the host's plugin tree.
