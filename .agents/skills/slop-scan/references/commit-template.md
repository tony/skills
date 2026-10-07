# Per-Finding Commit Templates

this skill lands each finding as one commit. Read the user's
conventions files first; where they define a subject format, follow it and
treat the shapes below as the default: `type(scope) description`, with
`cleanup` as the scope. Keep the signature id out of the subject.

## Subject templates

| Signature | Subject template |
|---|---|
| `brittle.line-numbers` | `docs(cleanup) Replace line number in <file>` |
| `low-value.todo-noise` | `chore(cleanup) Remove vague TODO from <file>` |
| `low-value.log-debris` | `chore(cleanup) Remove debug log from <file>` |
| `low-value.dead-future-code` | `chore(cleanup) Remove unused symbol from <file>` |
| `hardcoded.test-runner` | `docs(cleanup) Generalize test runner in <file>` |
| `hardcoded.os-paths` | `refactor(cleanup) Replace user path in <file>` |
| `branch-internal.*` | `docs(cleanup) Remove <description> from <file>` |

`<file>` is the repo-relative path. `<description>` is a short noun phrase
taken from the signature's `rationale`.

## Body

```
docs(cleanup) Replace line number in docs/api.md

why: "see line 42" breaks as soon as the file above it changes; a
function name stays valid.

what:
- Point the parse step at the `parse_config` function, not a line.
```

Wrap body lines at 72 characters. Keep the subject at 64 characters or
fewer: when the path makes it long, shorten the description, never the
path. Leave out exact counts, emoji, AI signatures,
and `Co-Authored-By:` lines, "Generated with" trailers, and tool
signatures; hosts add them by default, so strip them before committing.

## Advisory only

A finding never produces a commit here when it is Tier C, or when its
signature targets only `message-subject` or `message-body` (for example
`brittle.counts` and `ai-slop.signatures`). A match in
history under `--with-history` goes to `advisory.md` with a pointer to
`the `slop-deslop` skill --message-only`.
