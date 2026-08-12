# skills

A third-party plugin marketplace providing language-agnostic AI / agentic
workflow plugins for DX efficiency. Every plugin installs into both
[Claude Code](https://code.claude.com/docs/en/plugin-marketplaces.md) and
[Codex](https://developers.openai.com/plugins/build/plugins), and the skills
are readable by any agent that scans `.agents/skills/`.

> **Warning:** Review plugins before installing. Anthropic does not control plugin
> contents and cannot verify they work as intended.

**Repository:** [tony/skills](https://github.com/tony/skills)

## Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| [commit](plugins/commit/) | Development | Create git commits following project conventions with format enforcement and safety checks. |
| [weave](plugins/weave/) | Development | Run independent, adversarial AI participants via sub-agents or model CLIs to brainstorm, refine, plan, execute, architect, review, and synthesize. |
| [rebase](plugins/rebase/) | Development | Automated rebase onto trunk with conflict prediction, resolution, and quality gate verification. |
| [changelog](plugins/changelog/) | Productivity | Generate and maintain categorized changelog entries from branch commits and PR context. |
| [tdd](plugins/tdd/) | Testing | TDD bug-fix workflow: reproduce bugs as failing tests, determine root cause, fix, and verify. |
| [model-cli](plugins/model-cli/) | Development | Run prompts through individual AI CLIs — Antigravity/agy (Gemini), codex/GPT, and cursor/agent with fallback support. |
| [pr](plugins/pr/) | Development | Manage gold-standard PR descriptions. Detects AI slop and verbose commits, resolving them via fixup commits and autosquash. |
| [research](plugins/research/) | Learning | Study dependencies locally. Clones upstream repos and creates version-pinned worktrees matching your project's exact versions. |
| [slop](plugins/slop/) | Development | Scan tracked files for AI slop and verbose noise, resolving each finding with atomic, verified commits. |
| [tailwind](plugins/tailwind/) | Design | Detect and fix inconsistent spacing, margin/gap mixing, and padding asymmetry in Tailwind CSS layouts. |
| [pytest-optimizer](plugins/pytest-optimizer/) | Testing | Profile and optimize pytest suites. Ranks and applies safe speedups as verified, independent commits. |
| [spike](plugins/spike/) | Development | Run no-commit spikes or strategy bakeoffs in git worktrees. Tests ideas against quality gates and returns a commit-by-commit implementation plan. |
| [respond](plugins/respond/) | Development | Screen review feedback from humans or bots before changing code. Verifies claims against facts and project decisions. Valid findings become gated, atomic commits; invalid ones get evidence-backed replies. |
| [action](plugins/action/) | Development | Convert tickets to branches in isolated worktrees. Uses team branch conventions, lands gated commits, and supports parallel tickets. |
| [lean](plugins/lean/) | Development | Writing discipline and cleanup tools for tight, slop-free prose and code. |
| [double-check](plugins/double-check/) | Productivity | Forces verification requests to return re-derived answers instead of diffs against prior turns. Includes an alignment tool for repairing chats. |
| [release](plugins/release/) | Development | Cut and bump releases with safe defaults (no automatic push/tag). Rolls out releases to downstream consumers with CI verification. |
| [merge-pr](plugins/merge-pr/) | Development | Merge PRs matching repo history conventions. Includes readiness checks, CI watching, stack detection, and automated rebasing. |
| [business](plugins/business/) | Productivity | Measure and report the business value of AI workflows with provenance-tagged data — metrics in engineer-hours and cycle time, never currency. |
| [disk](plugins/disk/) | Productivity | Safely reclaim disk space. Classifies consumers as cache, redundant copy, or history, deleting only what is proven safe. |
| [github-actions](plugins/github-actions/) | Development | Update GitHub Actions pins fleet-wide. Verifies tags, researches release notes, commits each action separately, and supersedes Dependabot PRs. |
| [situate](plugins/situate/) | Development | Gain situational awareness before modifying code. Scans branches, PRs, tickets, and project conventions to orient the agent and verify the work required. |
| [terraform](plugins/terraform/) | Development | Upgrade Terraform and OpenTofu versions. Discovers every root module, moves provider constraints together because they combine across modules, and refreshes lock files without narrowing platform coverage. |
| [ruff](plugins/ruff/) | Development | Upgrade Ruff across repositories. Works out which new rules can fire against each repo's select list and lands one reviewed commit per rule, citing the upstream rule doc. |
| [git-branch](plugins/git-branch/) | Development | Rebuild branch history into atomic commits (byte-identical), or reimplement from scratch using existing tests as the spec. Includes an interactive-rebase toolkit. |
| [package-updater](plugins/package-updater/) | Development | Update dependencies and toolchains across repositories. Checks the supply-chain cooldown first, then commits toolchain, named bumps, and lockfile refreshes separately with release notes cited. |
| [gh](plugins/gh/) | Development | File durable GitHub issues with reproductions, pinned links, and stripped PII. Enforces a markdown writing discipline reusable for any PR, comment, or ticket. |
| [ticket](plugins/ticket/) | Development | Manage work across trackers (Linear, Jira, GitHub, etc.) respecting each platform's native object graph. Drafts durable tickets focused on invariants. |

## Installation

### Claude Code

Add the marketplace:

```console
/plugin marketplace add tony/skills
```

You can also browse available plugins with `/plugin > Discover`.

Then install any plugin by the name in the table above:

```console
/plugin install commit@skills
```

### Codex

Add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Then install any plugin by the name in the table above:

```console
codex plugin add commit@skills
```

Each workflow is one skill, invoked as `pr:deslop` under Codex and
`/pr:deslop` under Claude Code.

## Design Philosophy

Every plugin in this repository is **language-agnostic**. Commands do not hardcode
language-specific tools like `pytest`, `jest`, `cargo test`, or `ruff`. Instead, they
reference the project's own conventions by reading `AGENTS.md` or `CLAUDE.md` at
runtime to discover:

- How to run the test suite
- How to run linters and formatters
- How to run type checkers
- What commit message format to use
- What test patterns to follow

This means the same plugin works whether your project uses Python, TypeScript, Rust, Go,
or any other language.

## Development

Scripts use [uv](https://docs.astral.sh/uv/) to manage Python dependencies.

Install uv:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

or:

```bash
wget -qO- https://astral.sh/uv/install.sh | sh
```

See [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for
other methods.

### Lint and validate

```bash
uv run ./scripts/marketplace.py lint
```

### Sync marketplace manifest with plugin directories

Dry-run:

```bash
uv run ./scripts/marketplace.py sync
```

Write changes to marketplace.json:

```bash
uv run ./scripts/marketplace.py sync --write
```

### Check for outdated entries

```bash
uv run ./scripts/marketplace.py check-outdated
```

### Regenerate the portable skill export

`.agents/skills/` is a generated, committed mirror of every plugin skill in a
flat form that agents outside Claude Code (Cursor, pi, Antigravity, Grok) can
read: spec-only frontmatter and no host-specific inline-bash expansion. A skill
reaches its plugin's shared files by climbing out of its own directory, and
flattening severs that climb, so every file it reaches is copied in and the
links rewritten. Each exported skill is therefore self-contained.

Codex needs none of this. It reads `skills/` in place, so it consumes the
plugins directly through `.codex-plugin/plugin.json`.

```bash
uv run ./scripts/marketplace.py portable
```

Verify the committed tree matches the plugins it was generated from:

```bash
uv run ./scripts/marketplace.py portable --check
```

Edit `plugins/*/skills/`. Never edit `.agents/skills/`, `.agents/plugins/`, or
`plugins/*/.codex-plugin/` — all three are generated.
`.agents/portable-manifest.json` records each exported skill's sources, its
bundled files, and how many times each source file is copied across the
export.

Hosts that scan `.agents/skills/` read the tree straight from a checkout, with
no install step. The `skills` CLI reads the same tree:

```bash
npx skills add tony/skills
```

That installs the export and nothing else. The CLI would otherwise also walk
each plugin's `skills/` directory and offer both renderings of the same skill —
the exported one and the Claude Code original, which has not been through the
transform. `metadata.pluginRoot` in the marketplace manifest is what keeps it to
the export alone; a manifest edit that drops it brings the duplicates back.

### Code quality for scripts

Lint:

```bash
uv run ruff check ./scripts/
```

Format check:

```bash
uv run ruff format --check ./scripts/
```

Type check:

```bash
uv run basedpyright ./scripts/
```

## Documentation

See the [official Claude Code plugin docs](https://code.claude.com/docs/en/plugins) for
authoring guides, component schemas, and marketplace publishing.

## License

MIT
