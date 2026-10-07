# Commit message for CHANGES edits

Whether the skill commits or the user commits later, the message follows these
tiers.

1. Project convention wins, read again from `AGENTS.md` / `CLAUDE.md` when
   writing the reply, not recalled from earlier. When the user's `AGENTS.md`, `CLAUDE.md`, or
   equivalent prescribes a commit format, use it exactly: subject pattern,
   body structure, line-wrap budget, component naming. Use the project's `type`
   for docs edits and its component style (for example `docs(CHANGES)`). The
   body says why the changelog changed and what it adds, wrapped to the
   prescribed width.
2. With no documented convention, use `docs(CHANGES) <description>` and no
   body. Leave `#123` out: CHANGES entries reference PRs, a commit may predate
   its PR, and merge history already links commits to PRs.
3. Always:
   - No `Co-Authored-By` or other trailer naming a tool, no "Generated with"
     footer, no emoji. Hosts add them by default; leave them out.
   - The subject names what the changelog covers, not that one was added.
     Good: `docs(CHANGES) Help-on-empty CLI and sync --all flag`. Bad:
     `docs(CHANGES) Add changelog entry for help-on-empty CLI`.
   - No version anywhere: not in a component (`docs(CHANGES[v1.53.x])`), the
     subject, or the body ("for the 1.53 release").

Before the edit, run `git status --porcelain -- <changelog-file>`. Output
means the user already has uncommitted changes there, and a commit would sweep
them in: do not commit, leave the edit uncommitted, and say why. Before
advising `git checkout -- <changelog-file>` to clear it, confirm with
`git diff --stat -- <changelog-file>` that only the file mode changed; a
checkout discards real edits.

Commit the changelog file by path, which leaves other staged files out:

```console
$ git commit \
    --message "<message>" \
    -- <changelog-file>
```

A new, untracked changelog file needs `git add -- <changelog-file>` first.
Never `git add -A`, never a dirty code file, never push, never tag.
