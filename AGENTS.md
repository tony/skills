# AGENTS.md — skills

Project conventions and standards for AI-assisted development.

## Project Identity

This is a **public, third-party [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)**
providing language-agnostic AI / agentic workflow plugins for DX efficiency. Hosted
on GitHub ([tony/skills](https://github.com/tony/skills)), not affiliated with or
endorsed by Anthropic or OpenAI.

## Official Documentation References

These docs are the canonical references for the two plugin systems this
marketplace targets. Consult them when authoring or reviewing plugin
components.

Codex:

- [Package your plugin](https://developers.openai.com/plugins/build/plugins.md) — `.codex-plugin/plugin.json`, marketplace format, local and repo marketplaces, bundled MCP servers and hooks
- [Build skills](https://developers.openai.com/plugins/build/skills) — SKILL.md authoring for Codex

Claude Code:

- [Plugins overview](https://code.claude.com/docs/en/plugins.md) — plugin lifecycle, installation, discovery
- [Plugin reference](https://code.claude.com/docs/en/plugins-reference.md) — component types, frontmatter schemas, directory structure
- [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces.md) — marketplace.json schema, source types, publishing
- [Skills](https://code.claude.com/docs/en/skills.md) — skill authoring, SKILL.md format, `$ARGUMENTS`
- [Settings](https://code.claude.com/docs/en/settings.md) — plugin settings, permissions, scopes
- [Sub-agents](https://code.claude.com/docs/en/sub-agents.md) — agent frontmatter, delegation patterns, tool restrictions

## Quality gates

CI runs each check below on every pull request; run them before committing.

### Format

```console
$ uv run ruff format
```

### Lint

```console
$ uv run ruff check
```

### Type check

```console
$ uv run basedpyright
```

Plugin scripts run under the user's `python3`, and macOS ships 3.9, so
they also check against 3.9:

```console
$ uv run basedpyright \
    --pythonversion 3.9 \
    plugins
```

### Test

Mid loop: unit tests and doctests, then plugin lint, manifest sync,
generated-file drift, and description-routing checks. Integration tests
exercise owned Git repositories and CLI subprocess workflows in the outer
loop.

```console
$ uv run pytest -q \
    -m 'not integration' \
    && uv run scripts/marketplace.py lint \
    && uv run scripts/marketplace.py sync --check \
    && uv run scripts/marketplace.py portable --check \
    && uv run scripts/skill_evals.py check
```

Outer loop and CI: run every test, including integration tests:

```console
$ uv run pytest -q
```

`marketplace.py lint` already runs `claude plugin validate --strict` over the
marketplace and each plugin when the CLI is on `PATH` (an error under `CI`).
Run it on the marketplace directly:

```console
$ claude plugin validate \
    --strict \
    .
```

Then on every plugin:

```console
$ for p in plugins/*/; do claude plugin validate --strict "$p" || exit 1; done
```

Plugin scripts and their tests use only the standard library, so the tests
also run on 3.9 with nothing installed but pytest:

```console
$ uv run \
    --no-project \
    --isolated \
    --python 3.9 \
    --with pytest \
    pytest -q plugins
```

### End-to-end install

Installs every plugin into both hosts under a throwaway `HOME`; needs
`claude` and `codex` on `PATH`. Outer loop only:

```console
$ uv run scripts/e2e.py \
    --source local \
    --host both
```

## Git Commit Standards

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
- **ai(rules[AGENTS])**: AI rule updates
- **ai(claude[rules])**: Claude Code rules (CLAUDE.md)

### Project Component Naming

This repo contains Claude Code and Codex plugins built from skills. Use the
`ai(claude[...])` component pattern:

- `ai(claude[plugin])` — plugin manifest, structure, or multi-component changes
- `ai(claude[plugins])` — changes spanning multiple plugins
- `ai(claude[skill])` — a single skill
- `ai(claude[skills])` — changes spanning multiple skills
- `ai(rules)` — AGENTS.md or other AI convention files

When a change targets a specific named component, include it:
- `ai(claude[skill{commit}])` — the `commit` skill specifically
- `ai(claude[plugin{weave}])` — the `weave` plugin specifically

Examples:
```
ai(claude[skill/commit]) Add heredoc formatting for multi-line messages

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

#### Release commits

Never create or push a tag on your own initiative — tags trigger the
CI publish workflow, so cutting one is the user's call. An explicit
instruction in the conversation is that call, including a `--tag` or
`--push-tag` flag; act on it without asking again.

Release commit subjects are plain and short: `Tag v<version>`. Put
the detailed why/what in the commit body. Don't use the
`Scope(type[detail]):` format for releases — don't bury the lede.

For multi-line commits, use heredoc to preserve formatting:
```bash
git commit -m "$(cat <<'EOF'
feat(Component[method]) add feature description

why: Explanation of the change.

what:
- First change
- Second change
EOF
)"
```

## Documentation Standards

### Code Blocks

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

## Comments earn their maintenance cost

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

## AI Slop Prevention

Treat AI slop as **review-hostile noise**, not as proof that text or
code is wrong. The goal is to maximize information density by removing
artifacts that make the repository harder to trust or navigate.

### The Anti-Slop Rubric

Before committing, audit all AI-assisted changes for these noise
patterns:

- **AI Signatures:** Remove "Generated by", footers, conversational
  filler ("Certainly!", "Here is..."), unexplained emojis (🤖, ✨), and
  AI-tool metadata.
- **Brittle References:** Avoid hard-coded line numbers, fragile
  file/test counts, dated "as of" claims, bare SHAs, and local
  absolute paths unless they are strict evidentiary artifacts (e.g.,
  benchmark logs).
- **Diff Narration:** Do not restate what moved, was renamed, or was
  removed in artifacts the downstream reader holds: code, docstrings,
  README, CHANGES, PR descriptions, or release notes. The diff and
  commit message already carry this history.
- **Branch-Internal Narrative:** Do not mention intermediate branch
  states, abandoned approaches, or "no longer" behavior unless users
  of a published release actually experienced the old state (**The
  Published-Release Test**).
- **Revision-History Leakage:** When asked to double-check, verify,
  or re-examine prior analysis, deliver the re-derived answer —
  standalone, rebuilt from source, in the original request's shape.
  Verdicts about your own prior claims (*overstated*, *still holds*)
  are diff narration against a baseline the reader never adopted; put
  confidence on the claim, not the revision. Exception: if the user
  acted on a prior claim (committed, filed, sent), state that
  correction explicitly, once.
- **Low-Value Scaffolding:** Remove ownerless TODOs (`TODO: revisit`),
  unused future-proofing, debug artifacts, and defensive wrappers that
  do not protect a currently reachable failure mode.
- **Prose Inflation:** Replace generic AI "tells" like *comprehensive,
  robust, seamless, production-ready, leverage, delve, tapestry,* and
  *best practices* with concrete descriptions of behavior,
  constraints, or trade-offs.
- **Coded Labels:** Write rules, options, and findings as plain
  imperatives. Don't tag them with codes like `[R1]`, `A1`, or
  `Option B` in artifacts a human reads — the reader shouldn't have to
  decode an index. Internal agent bookkeeping may use ids; shipped text
  may not.

### Durable Source Links

Link to a pinned revision, never to trunk. A pinned permalink is not a
brittle reference; an unlinked SHA dropped into prose is. `blob/main/…`
links rot silently — the file moves, lines shift, and the anchor lands
on unrelated code while still resolving.

- Prefer a release tag (`blob/v1.4.0/…`). Most durable, and it tells
  the reader which released version the claim held for.
- Otherwise use a 7-char commit ref (`blob/9a29b1a/…`) reachable from
  trunk. Use when there is no tag or the claim is about unreleased
  code. Never a PR-head SHA — it can be rebased or garbage-collected.
- Reserve `blob/main/…` for living documents meant to always show the
  latest state, such as a contributing guide.
- Line anchors (`#L120-L145`) are only safe on a pinned ref.

### Preservation & Context

Subjective cleanup must never remove load-bearing rationale. Adjudicate
comments with the comment policy above; borderline cases are deleted, not
kept.

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

### Cleanup in Hindsight

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

### Change Discipline

- Make the smallest coherent change that solves the verified problem;
  keep unrelated cleanup out of it.
- Reuse an existing file, component, helper, API, or test before adding
  a new one. Modify in place when the change fits the file's
  responsibility.
- Keep new APIs private until a caller outside the module needs them.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized high-touch module — not
  for a single-use helper or a one-line re-export.

### Keep Instructions Lean

Treat this file like code and prune it.

- Delete a line whose removal would not cause a mistake.
- Move multi-step procedures into skills, path-specific rules into
  nested AGENTS.md files, and hard limits into hooks or CI.
- Keep only non-obvious, broadly applicable defaults here. Anything a
  reader can infer from the code, a manifest, or a linter does not
  belong.

## Plugin Quality Standards

### Skill Files

- Every `SKILL.md` **must** have YAML frontmatter with at least `name` and `description`
- Skills **must not** hardcode language-specific tool commands (e.g., `uv run pytest`,
  `npm test`, `cargo test`). Instead, reference "the project's test suite / quality checks
  as defined in AGENTS.md/CLAUDE.md"
- Frontmatter `allowed-tools` should use bare tool names (e.g., `Bash`) rather than
  language-specific patterns (e.g., `Bash(uv run:*)`) so skills work across any project
- Never use `!` context expansion. Codex never expands it, and on Claude Code a
  command that fails or lacks a grant empties the whole skill without an error.
  Gather context in a numbered step instead.
- Never link outside the plugin; each plugin installs alone.
- Every step that writes human-facing prose links `../../references/prose-rules.md`.
- Put deterministic machinery (argument parsing, process control, git
  plumbing) in a tested script under the plugin's `scripts/`; keep judgment in
  prose. A skill that runs one says its `../../scripts/` path resolves from
  the skill's directory (a reference writes `../scripts/`, from its own
  directory) to an absolute path written literally in each command.
- Never `git push` unless the user passed `--push` or asked to push; otherwise
  finish local and print the push command. `--pr` means "open a pull request";
  a pull request to act on is a positional argument. A force-push is
  `--force-with-lease --force-if-includes`.

`scripts/marketplace.py lint` enforces the `!` and plugin-boundary rules, the plugin layout below, a
500-line ceiling on skill bodies, a contents list on any resource over 100
lines, and that every resource is named by some file in its plugin.

### Plugin Directory Structure

Every plugin directory under `plugins/` has this shape:

```
plugins/<name>/
├── .claude-plugin/
│   └── plugin.json      # name, description (required)
├── .codex-plugin/
│   └── plugin.json      # generated
├── README.md            # usage docs, prerequisites, component reference
├── skills/              # skills (skill-name/SKILL.md)
├── references/          # files skills read on demand
├── scripts/             # tested scripts skills run
├── templates/           # files a skill copies into a project (optional)
└── evals/               # eval cases for `claude plugin eval`
```

Hosts also accept `agents/`, `hooks/`, `.mcp.json`, and `.lsp.json`; no plugin
here ships them, and the plugin reference linked above holds their schemas.

`.codex-plugin/plugin.json` and every skill's `agents/openai.yaml` (Codex's
presentation and `allow_implicit_invocation` policy) are written by
`scripts/marketplace.py portable` and verified by `portable --check`. Never
hand-edit them; change `.claude-plugin/plugin.json` or the skill's `SKILL.md`
and regenerate.

### Shared Files

A file several plugins ship lives once in `shared/`, and `shared/vendor.yml`
lists the plugins that ship it. `portable` copies it into each plugin's
`references/` under a one-line banner, and `portable --check` fails when a copy
differs. Edit the file in `shared/`, never a copy.

### Skills Are the Only Workflow Component

Every workflow is a skill; no plugin ships `commands/`. Codex reads only
`skills/`, and a skill is invoked the same way from either host:
`/slop:deslop` in Claude Code, `slop:deslop` in Codex. A skill's directory
name and its frontmatter `name` match, or the two hosts invoke it by
different names.

A skill carrying a workflow that only makes sense when the user asks for it by
name sets `disable-model-invocation: true`; `portable` mirrors it into Codex's
`agents/openai.yaml`. That keeps it invocable by name only and never routed to
on the model's initiative, and keeps it out of a routing corpus where it would
crowd skills meant to be discovered.

Address bundled files by climbing out of the skill directory
(`../../references/x.md`), never through `${CLAUDE_PLUGIN_ROOT}`. Codex performs
no substitution on that variable.

### Skill Frontmatter

- `name` (required here) — skill display name; upstream it defaults to
  the directory name, but this repo's gates expect it written out
- `description` (required here) — when and how to invoke the skill
- `argument-hint` (required when the body consumes `$ARGUMENTS`) — placeholder
  Claude shows when the user invokes the skill
- `allowed-tools` (optional) — tools usable without a permission prompt;
  space- or comma-separated string, or a YAML list
- `disallowed-tools` (optional) — tools removed while the skill is active
- `context` (optional) — set to `fork` to run in a subagent
- `disable-model-invocation` (optional) — if true, runs without model invocation
- `user-invocable` — defaults to true; never write `user-invocable: true`
- Content can reference `$ARGUMENTS` to access arguments passed to the skill

`allowed-tools` grants pre-approval rather than sandboxing: every tool
stays callable either way, so listing tools only skips the permission
prompt for those. Only `disallowed-tools` removes a tool from the pool.

### Marketplace Manifest

Two manifests describe the same marketplace. `.claude-plugin/marketplace.json`
is hand-maintained and authoritative; `.agents/plugins/marketplace.json` is
generated from it. Codex prefers the generated one and accepts the Claude
manifest only as a legacy fallback, so both ship and neither host depends on
the other's spelling.

- Located at `.claude-plugin/marketplace.json`
- Must reference every plugin under `plugins/` with a valid `source` path
- Official spec requires only `name` and `source` per entry; this marketplace also
  requires `description`, `version`, `author`, and `category` for quality
- Valid categories: `development`, `productivity`, `testing`, `security`, `design`,
  `database`, `deployment`, `monitoring`, `learning`
- Source types for plugin entries:
  - Relative path: `"./plugins/my-plugin"` (for git-based marketplaces)
  - GitHub: `{ "source": "github", "repo": "owner/repo" }` (optional `ref`, `sha`)
  - Git URL: `{ "source": "url", "url": "https://.../.git" }` (optional `ref`, `sha`)
- Reserved marketplace names: `claude-code-marketplace`, `claude-code-plugins`,
  `claude-plugins-official`, `anthropic-marketplace`, `anthropic-plugins`,
  `agent-skills`, `life-sciences`. Names impersonating official Anthropic
  marketplaces are also blocked.

### Language-Agnostic Design

A plugin not named for a tool works with any language or framework. Its
skills discover project tooling by reading AGENTS.md / CLAUDE.md at run time
rather than assuming an ecosystem, and name tools only as examples. Plugins
named for a tool (pytest-optimizer, ruff, tailwind, terraform) target that
tool and still read the project's own gates.

### Portable Shell Examples

A shell command shipped in a skill or reference runs on whatever
machine the user has. Either use a spelling that works on both GNU
coreutils and BSD/Darwin, or show both forms and label them.

The differences that matter here:

- `sed -i` takes an optional suffix on GNU and a mandatory one on
  BSD/Darwin, and the two spellings are mutually exclusive. Ship
  `sed -i` for GNU and `sed -i ''` for BSD/Darwin.
- In `sed` basic regular expressions, `\+`, `\?`, and `\|` are GNU
  extensions. Write `-E` with a bare `+`, `?`, or `|` — that spelling
  is identical on both.
- `du --files0-from`, `find -printf`, `numfmt`, `tac`, `nproc`,
  `shuf`, `base64 -w`, `readlink -f`, `stat -c`, and `date -d` are
  GNU-only with no BSD/Darwin flag to swap in. Reach for a different
  construct, not a different flag.
- macOS ships bash 3.2, so `mapfile`, `readarray`, `declare -A`, and
  `${var,,}` are unavailable there regardless of which coreutils are
  installed.

Check before splitting a command in two. `xargs -r`, `xargs -0`,
`sort -V`, `du -sch`, `find -print0`, `head -c`, and POSIX `date`
format specifiers all work on BSD/Darwin, so a second variant for
those is noise. `xargs -a` and `xargs -d` are the GNU-only ones.

When a command is genuinely single-platform — WSL virtual disks,
`findmnt`, `systemctl` — say so in the surrounding prose instead of
inventing an equivalent.

### Orchestration Plan Convention

Skills with analysis-then-execute phases should include a portable
"Orchestration Plan" section before execution begins. This section:

1. Opens with this prelude, verbatim: "Enter plan mode before the first
   edit. In Claude Code call `EnterPlanMode`; in Cursor, Codex, or Gemini
   use `/plan` or `Shift+Tab`. Where plan mode is unavailable, present the
   plan as text."
2. Defines what the orchestration plan should contain (skill-specific checklist)
3. Requires presenting the plan and waiting for user approval
4. Instructs exiting plan mode before execution


### Output Contract Convention

Skills that produce structured output for users declare their sections in
a fixed order. When several skills in a plugin share the output pattern, the
template lives in one reference file.

1. A hero block is allowed at the top (1–4 lines, `⚠`/`✓` prefix or
   short summary; no prose paragraphs).
2. Body sections appear in a declared fixed order with verbatim level-2
   headings. No invented sections.
3. After the prescribed sections, end with an interactive next-step panel
   (via `AskUserQuestion`) where the user can act on the result without
   composing a follow-up command. Skip the panel only when the skill
   is already running inside plan mode. Where no question tool exists
   (Codex, headless runs), print the options as a plain list and stop.
4. A halted run prints one result sentence, then what the user must do.

### Accessible Formatting

- **Prefer prose and nested sections over tables** — reach for a table
  only when the data is genuinely matrix-shaped and stable. Repeated
  semantic headings (e.g., "Use when / Avoid when / Tradeoff") diff,
  wrap, and edit more cleanly than a table.
