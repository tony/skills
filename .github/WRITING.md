# Writing

How this repository writes prose, for humans and agents alike: commit
messages, pull request descriptions, Markdown, docstrings, and source
comments. It governs the skills and references plugins ship as well as the
repository's own files. The word-level rubric lives in
[shared/prose-rules.md](../shared/prose-rules.md), which every plugin vendors
so its skills can link it; this file does not restate it.

How the scripts are written is in [PYTHON.md](PYTHON.md). The gates, plugin
layout, and skill conventions are in [AGENTS.md](../AGENTS.md).

## Commits

Format commit messages as:
```
Scope(type[detail]) concise description

why: Explanation of necessity or impact.

what:
- Specific technical changes made
- Focused on a single topic
```

Keep the subject ≤64 chars (excluding any trailing `(#NN)` PR ref); wrap
body lines at ≤72 chars. Separate the `why:` and `what:` blocks with a
blank line.

Common commit types:
- **feat**: New features or enhancements
- **fix**: Bug fixes
- **refactor**: Code restructuring without functional change
- **docs**: Documentation updates
- **chore**: Maintenance (dependencies, tooling, config)
- **test**: Test-related updates
- **style**: Code style and formatting

### Component names

This repo contains Claude Code and Codex plugins built from skills. Use the
`ai(claude[...])` component pattern:

- `ai(claude[plugin])` — plugin manifest, structure, or multi-component changes
- `ai(claude[plugins])` — changes spanning multiple plugins
- `ai(claude[skill])` — a single skill
- `ai(claude[skills])` — changes spanning multiple skills
- `ai(rules)` — AGENTS.md (CLAUDE.md and GEMINI.md link to it), the
  policies it routes to in `.github/`, or other AI convention files

When a change targets a specific named component, include it:
- `ai(claude[skill{commit}])` — the `commit` skill specifically
- `ai(claude[plugin{weave}])` — the `weave` plugin specifically

Examples:
```
ai(claude[skill{commit}]) Add heredoc formatting for multi-line messages

why: Commit messages with body text need preserved newlines

what:
- Add heredoc template to commit skill prompt
- Include why/what body format in instructions
```

```
ai(claude[skill{deslop}]) Halt on a dirty tree before rewriting

why: A rebase over uncommitted edits can lose them

what:
- Check git status before any apply mode
- Name the dirty files and stop
```

```
ai(rules) Add project-specific commit component conventions

why: Claude Code plugins need distinct component prefixes

what:
- Add ai(claude[...]) naming scheme for plugins and skills
- Include examples for single and multi-component changes
```

### Release commits

Never create or push a tag on your own initiative; cutting a release is the
user's call. An explicit
instruction in the conversation is that call, including a `--tag` or
`--push-tag` flag; act on it without asking again.

Release commit subjects are plain and short: `Tag v<version>`. Put
the detailed why/what in the commit body. Don't use the
`Scope(type[detail]):` format for releases — don't bury the lede.

For multi-line commits, use a heredoc to preserve formatting:

```console
$ git commit --message "$(cat <<'EOF'
ai(claude[skill{commit}]) Add feature description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

`scripts/commit_lint.py` checks the subject, body width, and the blank line
between `why:` and `what:` over a pull request's commits in CI.

## Code blocks

Code blocks are paste-and-run units: pasting one block runs exactly one
intended action. Doctests and other executed examples are exempt — the test
suite runs them, nobody pastes them.

- **One command per block.** Multiple steps may share a block only when
  explicitly chained with `&&`, `;`, or `\` continuations — the chain is
  then one logical command.
- **Explanations go in prose above the block**, never as `#` comments inside it.
- **Command menus are per-command blocks with prose lead-ins**, not tables.
- **Shell commands use the `console` tag with a `$ ` prefix.** This separates
  interactive commands from scripts and enables prompt-aware copy.
- **Split long commands with `\`** — one flag or flag+value pair per indented
  continuation line, positional arguments last.

Good:

Show the last ten commits as a graph:

```console
$ git log \
    --max-count=10 \
    --graph \
    --oneline
```

Bad:

```console
# Show the last ten commits as a graph
$ git log --max-count=10 --graph --oneline
```

## Source comments

A comment ships only if it passes all three gates. Fail any: delete or rewrite.
Borderline: delete — borderline means the information is reconstructible, which
is what makes deletion cheap.

**Loss.** Three years from now, would losing this cost a maintainer real time
rediscovering intent, an invariant, a constraint, or a failure mode the code and
tests do not already make obvious?

**Elite.** Would SQLite, Redis, the Go standard library, or CPython write this
comment, at this length? Those projects state the constraint and stop. They do
not argue with an imagined objector.

**Upkeep.** Will it stay true without maintenance? A comment that hand-syncs a
value the code owns — a count, an offset, a line reference, a duplicated
constant — is false the first time that value moves.

### Ceiling

One or two lines. A comment reaching four is either carrying several facts, in
which case split it, or arguing, in which case cut it to the fact.

Rationale, alternatives weighed, and the story of how the code got here belong
in the commit message: timestamped, attached to the exact diff, and free to
maintain.

A comment often holds both a constraint and the deliberation that found it. Keep
the constraint, cut the deliberation. "Runs at most once per second" survives;
"this is the right trade for now" does not.

### Keep

- Why over how: upstream quirks, protocol and compatibility constraints,
  performance tradeoffs still part of the contract.
- Invariants, preconditions, ordering, lifetime, and concurrency requirements
  that types and tests cannot express.
- Code that looks wrong but is not, so a later cleanup does not reintroduce the
  bug.
- A high-level sketch of an algorithm whose local operations do not reveal the
  whole.

### Delete

- Narration of the next lines; code translated into English.
- Restated names, types, defaults, or control flow.
- Values duplicated from the code and hand-synced.
- Justification, hedging, or apology for a choice.
- Speculation about future requirements.
- History version control already holds, including commented-out code.
- Ticket and issue numbers. They say nothing to a reader without tracker access,
  and they rot when the tracker moves. Unfinished work goes in the tracker, not
  the source.
- Transient observations — "currently", "for now", "the latest release" —
  that go stale with no nearby edit.

### The upkeep gate in practice

It reaches values that track our own code. It does not reach frozen external
facts.

Bad (Delete):

```python
# There are 321 tests to complete for servers.
```

Good (Keep):

```python
# CPython < 3.11 has no ExceptionGroup, so this branch stays.
```

### Documentation exception

Doctests, minimal usage examples, and param, return, and raises lines on public
API are exempt from the loss gate — they serve the caller, not the maintainer.
They are exempt from nothing else. Ceiling: a good man page entry.

NumPy-style `Parameters`, `Returns`, and `Attributes` sections and executable
doctests fall under this exception — autodoc ships every field whether or not
you describe it, and a doctest that runs is also a test.

## Slop prevention

Treat AI slop as **review-hostile noise**, not as proof that text or
code is wrong. The goal is to maximize information density by removing
artifacts that make the repository harder to trust or navigate.

### The anti-slop rubric

Before committing, audit AI-assisted changes against the lists in
[shared/prose-rules.md](../shared/prose-rules.md) ("Cut these words", "Keep out of
the record"). That file owns the rubric; the Published-Release Test below
decides what counts as branch-internal.

### Durable source links

Link to a pinned revision, never to trunk. The rules and the commands that
resolve a pin are in [shared/source-pins.md](../shared/source-pins.md).

### Preservation and context

Subjective cleanup must never remove load-bearing rationale. Adjudicate
comments with [Source comments](#source-comments); borderline cases are
deleted, not kept.

- **Preserve the "Why":** You MUST NOT delete comments that document
  invariants, protocol constraints, platform quirks, security
  boundaries, and upstream workarounds.
- **Evidence is Immune:** Preserve exact counts, dates, and SHAs when
  they serve as evidence in benchmark results, release notes, stack
  traces, or lockfiles.
- **Behavior Over Inventory:** A useful description explains what
  changed for the *system or user*; it does not provide an inventory
  of files or functions the diff already shows.

### The Published-Release Test

Long-running branches accumulate tactical decisions — renames,
refactors, attempts-then-reverts. When deciding what counts as
branch-internal, use trunk or the parent branch as the baseline — not
intermediate states inside the current branch. Ask:

> Did users of the most recently published release ever experience
> this old name, old behavior, or bug?

If the answer is **no**, it is branch-internal narrative. Move it to
the commit message and describe only the final state in the artifact.

**Keep in shipped artifacts:**
- Deprecations and migration guides for symbols that actually shipped.
- `### Fixes` entries for bugs that affected users of a published
  release.
- Comments explaining *why the current code looks this way*
  (invariants, platform quirks) that make sense to a reader who never
  saw the previous version.

### Cleanup in hindsight

When applying these rules retroactively from inside a feature branch,
first establish scope by diffing against the parent branch (or trunk)
to identify which commits this branch actually introduced. Then:

- **In-branch commits:** Prompt the user with two options: `fixup!`
  commits with `git rebase --autosquash` to address each causal commit
  at its source, or a single cleanup commit at branch tip.
- **Trunk/Parent commits:** Default to leaving them alone. Act only on
  explicit user instruction. If the user opts in, fold the cleanup
  into a single commit at branch tip; do not rewrite shared history.
- **Scope guard:** If cleaning prior slop would touch a colleague's
  work or expand the branch beyond its stated goal, stay in lane:
  protect the current goal and leave prior slop alone.

## Formatting

- **Prefer prose and nested sections over tables** — reach for a table
  only when the data is genuinely matrix-shaped and stable. Repeated
  semantic headings (e.g., "Use when / Avoid when / Tradeoff") diff,
  wrap, and edit more cleanly than a table.
