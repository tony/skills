# Commit message for CHANGES edits

Whether the skill commits or the user commits later, the message follows these
tiers.

1. Project convention wins. When the user's `AGENTS.md`, `CLAUDE.md`, or
   equivalent prescribes a commit format, use it exactly: subject pattern,
   body structure, line-wrap budget, component naming. Use the project's `type`
   for docs edits and its component style (for example `docs(CHANGES)`). The
   body says why the changelog changed and what it adds, wrapped to the
   prescribed width.
2. With no documented convention, use `docs(CHANGES) <description>` and no body.
3. Always:
   - No `#123` in the message. CHANGES entries reference PRs; a commit may
     predate its PR, and merge history already links commits to PRs.
   - The subject names what the changelog covers, not that one was added.
     Good: `docs(CHANGES) Help-on-empty CLI and sync --all flag`. Bad:
     `docs(CHANGES) Add changelog entry for help-on-empty CLI`.
   - No version anywhere: not in a component (`docs(CHANGES[v1.53.x])`), the
     subject, or the body ("for the 1.53 release").

Stage the changelog file by path. Never `git add -A`, and never a dirty code
file. Never push and never tag.
