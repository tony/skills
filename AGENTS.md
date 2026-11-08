# AGENTS.md — skills

Project conventions and standards for AI-assisted development.

## Project Identity

This is a **public, third-party [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)**
providing language-agnostic AI / agentic workflow plugins for DX efficiency. Hosted
on GitHub ([tony/skills](https://github.com/tony/skills)), not affiliated with or
endorsed by Anthropic or OpenAI.

## Which Policy Applies

- Commit messages, pull request descriptions, Markdown, docstrings, and
  source comments: [.github/WRITING.md](.github/WRITING.md)
- Python in plugin scripts, `shared/`, and `scripts/`:
  [.github/PYTHON.md](.github/PYTHON.md)
- The gates, plugin layout, skills, and manifests: this file

Each is the single home for its subject. Where a rule seems to be stated
twice, the file listed above is the one that governs.

## Official Documentation References

These docs are the canonical references for the two plugin systems this
marketplace targets. Consult them when authoring or reviewing plugin
components.

Codex:

- [Package your plugin](https://developers.openai.com/plugins/build/plugins.md) — plugin packaging, marketplace format, local and repo marketplaces, bundled MCP servers and hooks
- [Build skills](https://developers.openai.com/plugins/build/skills) — SKILL.md authoring for Codex

Claude Code:

- [Plugins overview](https://code.claude.com/docs/en/plugins.md) — plugin lifecycle, installation, discovery
- [Plugin reference](https://code.claude.com/docs/en/plugins-reference.md) — component types, frontmatter schemas, directory structure
- [Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces.md) — creating and distributing a marketplace
- [Marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference.md) — marketplace.json schema, plugin sources, reserved names
- [Skills](https://code.claude.com/docs/en/skills.md) — skill authoring, SKILL.md format, `$ARGUMENTS`
- [Settings](https://code.claude.com/docs/en/settings.md) — plugin settings, permissions, scopes
- [Sub-agents](https://code.claude.com/docs/en/sub-agents.md) — agent frontmatter, delegation patterns, tool restrictions

## Quality gates

CI runs each check below on every pull request (`ruff format` as `--check`);
run them before committing.

### Format

CI fails on unformatted files. Drop `--check` to rewrite them:

```console
$ uv run ruff format --check
```

### Lint

```console
$ uv run ruff check
```

### Type check

```console
$ uv run ty check
```

Plugin scripts and `shared/` also check against their Python 3.14 floor
([PYTHON.md](.github/PYTHON.md#two-floors)):

```console
$ uv run ty check \
    --python-version 3.14 \
    plugins \
    shared
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
also run on 3.14 with nothing installed but pytest:

```console
$ uv run \
    --no-project \
    --isolated \
    --python 3.14 \
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

## Change Discipline

- Make the smallest coherent change that solves the verified problem;
  keep unrelated cleanup out of it.
- Reuse an existing file, component, helper, API, or test before adding
  a new one. Modify in place when the change fits the file's
  responsibility.
- Keep new APIs private until a caller outside the module needs them.
- Add a file only for a durable boundary — a distinct responsibility,
  independent reuse, or splitting an oversized high-touch module — not
  for a single-use helper or a one-line re-export.

## Keep Instructions Lean

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
  `--force-with-lease --force-if-includes`, or
  `--force-with-lease=<ref>:<sha>` alone when the expected tip is known:
  git-push documents `--force-if-includes` as a no-op beside an explicit
  `<expect>`.

`scripts/marketplace.py lint` enforces the `!` and plugin-boundary rules, the plugin layout below, a
500-line ceiling on skill bodies, a contents list on any resource over 100
lines, that every resource is named by some file in its plugin, and that a
Bash grader naming a bundled script also matches it called through a shell
variable (`python3 $G sub`).

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

The Codex page linked above documents a root `plugin.json` as the preferred
entry point. This repo keeps generating `.codex-plugin/plugin.json`, the
compatibility layout Codex still loads.

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
name, and that nobody chains into a prompt, a goal, or another skill's next
step, sets `disable-model-invocation: true`; `portable` mirrors it into Codex's
`agents/openai.yaml`. That keeps it invocable by name only and never routed to
on the model's initiative, and keeps it out of a routing corpus where it would
crowd skills meant to be discovered.

Claude Code reliably runs a flagged skill only from a slash command that opens
the prompt. It refuses one reached in a follow-up or `/goal` turn, named in
another command's arguments, or offered by another skill's next-step panel. A
skill users chain that way stays model-invocable, and its description makes an
explicit request the trigger: "Use when a user explicitly wants to …".

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
- `disable-model-invocation` (optional) — see Skills Are the Only Workflow
  Component
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

- Must reference every plugin under `plugins/` with a valid `source` path
- Beyond the [Marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference.md)
  (schema, plugin sources, reserved names; `claude plugin validate` enforces
  it), every entry needs `description`, `version`, `author`, and `category`
- Valid categories: `development`, `productivity`, `testing`, `security`, `design`,
  `database`, `deployment`, `monitoring`, `learning`

### Plugin Versions

A pull request that changes anything under `plugins/<name>/` changes that
plugin's `version` in `.claude-plugin/plugin.json`. `marketplace.py sync
--write` copies it into the marketplace entry, and `sync --check` fails when
they differ. CI runs `marketplace.py versions --base <ref>`, which names every
plugin whose files changed while its version did not. Generated files under
`.agents/` and `plugins/*/.codex-plugin/` do not count as a change.

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

Completed `goal-planner` handoffs may omit empty sections and end after the
artifact, compact status, and material gaps. They need no next-step panel;
ask only for a decision needed to finish the requested handoff.
