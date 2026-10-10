# Ticket Detection, Branch Naming & Worktree Placement

How `/action:worktree` and `/action:worktrees` resolve tickets into
branch names and worktree paths. Linear and GitHub have dedicated steps;
other trackers use the generic fallback.

Contents:

- The read-only invariant (zero ticket write-back)
- Detection source ladder
- Ticket systems
- Branch-name precedence ladder
- Worktree placement & path sanitization
- Server-side linking (how zero write-back still links)

## The read-only invariant (zero ticket write-back)

```text
TICKETS ARE READ-ONLY
```

Neither command assigns, comments, transitions, labels, estimates, or
otherwise mutates a ticket, in any tracker through any tool. Every
ticket operation is a read. A branch that goes nowhere unwinds with the
teardown steps in `worktree-setup.md`; linking happens server-side from
naming (see § Server-side linking).

Forbidden (non-exhaustive): tracker MCP mutation tools (comment, state
change, assignee change), `gh issue edit`, `gh issue comment`,
`gh issue close`, and `gh issue develop`, which *writes a linked-branch
record to the issue*; construct the same branch name locally. Jira and
GitLab equivalents are equally off-limits.

## Detection source ladder

The first source that yields a concrete ticket wins:

1. **Explicit URL or ID in the prompt**: `TEA-123`, `#45`, a full issue
   URL, `owner/repo#45`.
2. **Conversation context**: pasted issue text, a link shared earlier,
   the item the user just agreed to work.
3. **Available MCP tools**: a tracker MCP server whose read tools can
   fetch or search issues.
4. **CLIs**: `gh` preferred (`gh issue view`, `gh issue list`); other
   tracker CLIs, read-only subcommands only.
5. **Repo remote heuristics**: an `origin` on github.com suggests GitHub
   issues; a tracker ID pattern in recent branch names or commit
   trailers suggests that tracker.

When no source yields a ticket, ask — never invent an ID or fetch a
guessed one.

## Ticket systems

| System | ID pattern | Examples | Disambiguation |
|---|---|---|---|
| Linear | `[A-Z][A-Z0-9]*-\d+` | `TEA-123`, `OPS2-7` | Linear MCP tools present, or a linear.app URL |
| GitHub | `#\d+`, issue URL | `#482` | `gh` CLI + GitHub remote |
| Jira | `[A-Z][A-Z0-9]*-\d+` | `PROJ-42` | Jira CLI/MCP present, or an atlassian.net URL |
| GitLab | `#\d+`, `!\d+`, issue URL | `#17` | GitLab remote |
| Other | whatever the tool exposes | — | generic fallback below |

Linear and Jira share the `KEY-123` shape. With both integrations
present and no URL, try Linear first; if the ID is unknown there, try
the other; if both claim it, ask.

### Linear

- **ID pattern**: per the table above; match case-insensitively, display
  uppercased.
- **Fetch**: the Linear MCP read tools: title, description, acceptance
  criteria, and `gitBranchName`.
- **Branch name**: prefer `gitBranchName`. Without MCP, use the
  lowercased ID plus a kebab slug of the title
  (`tea-123-fix-login-redirect`), subject to the observed-norms
  adjustment below.

### GitHub

- **References**: `#123`, bare issue numbers in context, full issue
  URLs, `owner/repo#123`.
- **Fetch**:

```console
$ gh issue view <num> --json number,title,body,labels,url
```

  Add `--repo <owner>/<repo>` for cross-repo references.

- **Branch name default**: `<number>-<kebab-title-slug>`, e.g.
  `123-fix-login-redirect`.

### Generic fallback (Jira, GitLab, others)

- **ID patterns**: `[A-Z]+-\d+` (Jira-style), `#\d+` (GitLab issues),
  or whatever pattern the conversation supplies.
- **Fetch**: whatever CLI or MCP server is present (`jira`, `glab`),
  read-only subcommands only. When none exists, ask the user to paste
  the ticket body.
- **Branch name**: generic kebab slug, `<id-lowercased>-<kebab-title>`.

### Kebab-slug algorithm

Wherever a `<kebab-title-slug>` is called for, run the helper. Ticket
titles are untrusted, so write the title to a file (from `mktemp
"${TMPDIR:-/tmp}/action-title.XXXXXX"`, with the host's file-writing
tool) and never pass it as an argument. Resolve
`../scripts/worktree_paths.py` from this file's directory to an absolute
path and write it literally:

```console
$ python3 /abs/path/to/scripts/worktree_paths.py slug \
    --file /tmp/action-title.AbC123 \
    --prefix tea-123
```

It prints the whole branch name: the prefix (omit `--prefix` for a bare
slug), then the lowercased title with non-alphanumeric runs collapsed to
`-`, truncated at a word boundary to at most 60 characters in all.

## Branch-name precedence ladder

Resolve the branch name by the first rung that yields one:

1. **Explicit user prompt**: `--branch=<name>` or a name stated in the
   request. Verbatim, no adjustment.
2. **User/project instructions**: branch-naming conventions in the
   project's AGENTS.md / CLAUDE.md / CONTRIBUTING first, then the user's
   global norms.
3. **Ticket-system default**: Linear's `gitBranchName`; GitHub's
   `<number>-<kebab-title-slug>`. *Skipped for multi-ticket branches.*
4. **Observed repo norms**: mine the team's actual pattern:

```console
$ git branch -r
```

```console
$ git log --merges --oneline -50
```

   Look for prefix families (`feat/`, `fix/`, `username/`), where the
   ticket ID sits, and slug style. Norms also **adjust** rung 3: with
   no `username/` prefixes in history, trim the prefix from the Linear
   name; with a `feat/`-style prefix on every branch, add one to the
   ticket default. Name the adjustment in the plan.
5. **Kebab-slug fallback**: a kebab slug of the goal, when no ticket,
   convention, or norms exist.

Whatever rung wins, validate the name before any command uses it. A
tracker field, `--branch` or a remote ref can carry shell syntax, so write
the candidate to a file with the file tool, never through the shell, then
check it (the script path resolves as above):

```console
$ python3 /abs/path/to/scripts/worktree_paths.py check --file <name-file>
```

It prints the name when it is safe (letters, digits, `.`, `_`, `/`, `-`, no
leading `-`, and `git check-ref-format --branch` accepts it); only that
printed name enters later commands. A refused name from a slugged title is
re-slugged and re-checked; a refused explicit name (rung 1) is a question
back to the user, never a silent rewrite (non-interactive: report
`⚠ blocked`, change nothing).

**Multi-ticket (crosscutting) branches** skip rung 3. Propose a
**theme slug** (e.g. `auth-error-handling`) and confirm it at the plan
gate. Ticket IDs still ride in commit messages and the PR title/body,
so server-side linking fires for every ticket.

## Worktree placement & path sanitization

Two placements, the placement axis:

- **`--local` (default)**: a visible sibling of the repo:

```text
{repo_path}-{sanitized_branch}/
```

  The helper derives it from the **main checkout**, the first
  `worktree` line of `git worktree list --porcelain` (not
  `git rev-parse --show-toplevel`, which returns the linked worktree
  inside one), plus the branch name with every `/` flattened to `-`.
  The git branch keeps its slashes:

```console
$ python3 /abs/path/to/scripts/worktree_paths.py path \
    --branch 'feat/tea-123-login'
```

  Example: repo at `/work/shop`, branch `feat/tea-123-login` →
  worktree `/work/shop-feat-tea-123-login/`, branch still
  `feat/tea-123-login`.

- **`--temp`**: the host's native temp-worktree mechanism when one
  exists, **but only if it can put the work on the computed branch
  name** (Linear auto-attaches by name). Otherwise a temp root outside
  the repo:

```text
${TMPDIR:-/tmp}/action-worktrees/<repo-name>-<hash>/<sanitized-branch>/
```

  `<repo-name>` is the basename of the main checkout and `<hash>` the
  POSIX `cksum` of its absolute path, so same-named repos do not
  collide. The helper prints the whole path with `path --temp`; it is
  deterministic, so `--temp` re-runs resume the same worktree.

Branch names are git-valid by here, so `/` is the only character to
flatten.

## Server-side linking (how zero write-back still links)

| Tracker | Carrier | Effect |
|---|---|---|
| Linear | ticket ID in the branch name and PR title | Linear auto-attaches the branch/PR to the issue |
| GitHub | closing keyword in the PR body (`Fixes #123`) | issue links immediately, closes when a human merges |
| Generic | ID in the branch name, PR title, and commit bodies | whatever the tracker's own git integration picks up |

Both carriers are vendor behavior; verify them in the tracker's docs
before relying on them: Linear's GitHub integration
(https://linear.app/docs/github-integration) and GitHub's "Linking a
pull request to an issue"
(https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue).

Commit bodies name the ticket ID(s) they advance, in the project's
form. Closing keywords belong in the PR body, never in commit
subjects.
