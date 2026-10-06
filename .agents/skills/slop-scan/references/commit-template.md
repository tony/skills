# Per-Finding Commit Templates

this skill lands each finding as one commit, using the project's
`Scope(type[detail]) description` subject convention. Read the user's
conventions files first; where they define a different format, follow it
and treat the shapes below as the default. Type and scope derive from the
signature prefix.

## Subject templates

| Signature | Subject template |
|---|---|
| `brittle.line-numbers` | `docs(slop[<id>]) Replace line number in <file>` |
| `low-value.todo-noise` | `chore(slop[<id>]) Remove vague TODO from <file>` |
| `low-value.log-debris` | `chore(slop[<id>]) Remove debug log from <file>` |
| `low-value.dead-future-code` | `chore(slop[<id>]) Remove unused symbol from <file>` |
| `hardcoded.test-runner` | `docs(slop[<id>]) Generalize test runner in <file>` |
| `hardcoded.os-paths` | `refactor(slop[<id>]) Replace user path in <file>` |
| `branch-internal.*` | `docs(slop[<id>]) Remove <description> from <file>` |

`<id>` is the signature id from `signatures.yml`, verbatim. `<file>` is
the repo-relative path. `<description>` is a short noun phrase taken
from the signature's `rationale`.

## Body

```
docs(slop[brittle.line-numbers]) Replace line number in docs/api.md

why: "see line 42" breaks as soon as the file above it changes; a
function name stays valid.

what:
- Point the parse step at the `parse_config` function, not a line.
```

Wrap body lines at 72 characters. Keep the subject at 64 characters or
fewer: when the id and path make it long, shorten `<description>`,
never the id or the path. Leave out exact counts, emoji, AI signatures,
and `Co-Authored-By:` lines, "Generated with" trailers, and tool
signatures; hosts add them by default, so strip them before committing.

## Advisory only

A finding never produces a commit here when it is Tier C, or when its
signature targets only `message-subject` or `message-body`. A match in
history under `--with-history` goes to `advisory.md` with a pointer to
`the `slop-deslop` skill --message-only`.
