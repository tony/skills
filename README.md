# skills

A third-party marketplace of language-agnostic AI workflow plugins. Plugins
install into [Claude Code](https://code.claude.com/docs/en/plugin-marketplaces.md)
and [Codex](https://developers.openai.com/plugins/build/plugins), and are
readable by agents scanning `.agents/skills/`.

> **Warning:** Review plugins before installing. Anthropic does not control plugin
> contents and cannot verify they work as intended.

**Repository:** [tony/skills](https://github.com/tony/skills)

## Plugins

Most work starts with `situate` to get oriented, `commit` and `pr` to land
changes, and `respond` to screen review feedback.

### Git and pull requests

| Plugin | Description |
|--------|-------------|
| [commit](plugins/commit/) | Create git commits following project conventions with format enforcement and safety checks. |
| [rebase](plugins/rebase/) | Automated rebase onto trunk with conflict prediction, resolution, and quality gate verification. |
| [git-branch](plugins/git-branch/) | Rebuild branch history into atomic commits (byte-identical), or reimplement from scratch using existing tests as the spec. Includes an interactive-rebase toolkit. |
| [pr](plugins/pr/) | Draft, refresh, rewrite, and review PR descriptions, and draft merge commit messages, from the branch diff. |
| [merge-pr](plugins/merge-pr/) | Merge PRs matching repo history conventions. Includes readiness checks, CI watching, stack detection, and automated rebasing. |
| [respond](plugins/respond/) | Screen review feedback from humans or bots before changing code. Verifies claims against facts and project decisions. Valid findings become gated, atomic commits; invalid ones get evidence-backed replies. |
| [slop](plugins/slop/) | Audit a branch's commits or a repo's tracked files for AI slop and brittle references; fix through fixup or atomic commits. |
| [changelog](plugins/changelog/) | Generate and maintain categorized changelog entries from branch commits and PR context. |

### Releases and dependencies

| Plugin | Description |
|--------|-------------|
| [release](plugins/release/) | Cut and bump releases with safe defaults (no automatic push/tag). Rolls out releases to downstream consumers with CI verification. |
| [package-updater](plugins/package-updater/) | Update dependencies and toolchains across repositories. Checks the supply-chain cooldown first, then commits toolchain, named bumps, and lockfile refreshes separately with release notes cited. |
| [github-actions](plugins/github-actions/) | Update GitHub Actions pins fleet-wide. Verifies tags, researches release notes, commits each action separately, and supersedes Dependabot PRs. |
| [ruff](plugins/ruff/) | Upgrade Ruff across repositories. Works out which new rules can fire against each repo's select list and lands one reviewed commit per rule, citing the upstream rule doc. |
| [terraform](plugins/terraform/) | Upgrade Terraform and OpenTofu versions. Discovers every root module, moves provider constraints together because they combine across modules, and refreshes lock files. |

### Tests and code

| Plugin | Description |
|--------|-------------|
| [tdd](plugins/tdd/) | TDD bug-fix workflow: reproduce bugs as failing tests, determine root cause, fix, and verify. |
| [pytest-optimizer](plugins/pytest-optimizer/) | Profile and optimize pytest suites. Ranks and applies safe speedups as verified, independent commits. |
| [tailwind](plugins/tailwind/) | Detect and fix inconsistent spacing, margin/gap mixing, and padding asymmetry in Tailwind CSS layouts. |

### Planning and tickets

| Plugin | Description |
|--------|-------------|
| [situate](plugins/situate/) | Gain situational awareness before modifying code. Scans branches, PRs, tickets, and project conventions to orient the agent and verify the work required. |
| [action](plugins/action/) | Convert tickets to branches in isolated worktrees. Uses team branch conventions, lands gated commits, and supports parallel tickets. |
| [ticket](plugins/ticket/) | Manage work across trackers (Linear, Jira, GitHub, etc.) respecting each platform's native object graph. Drafts durable tickets focused on invariants. |
| [spike](plugins/spike/) | Run no-commit spikes, strategy bakeoffs, or multi-round convergence in git worktrees. Tests ideas against quality gates and returns a commit-by-commit implementation plan. |

### Writing and verification

| Plugin | Description |
|--------|-------------|
| [lean](plugins/lean/) | Writing discipline and cleanup tools for tight, slop-free prose and code. |
| [double-check](plugins/double-check/) | Forces verification requests to return re-derived answers instead of diffs against prior turns. Includes an alignment tool for repairing chats. |
| [gh](plugins/gh/) | File durable GitHub issues with reproductions, pinned links, and stripped PII. Enforces a markdown writing discipline reusable for any PR, comment, or ticket. |
| [skill-style](plugins/skill-style/) | Hold SKILL.md files to a deletion test — a line stays only when its removal would change what the agent does — while frontmatter, code blocks, and sections survive verbatim. |

### Research

| Plugin | Description |
|--------|-------------|
| [research](plugins/research/) | Research topics and assess decisions with pinned, captured sources in dated folders. Resume, re-verify, report. Clones dependencies at pinned versions. |
| [scholar](plugins/scholar/) | Distil a checkable ontology from a codebase, a repository set, or a written corpus. Types, controlled vocabulary, cited and measured evidence. |
| [business](plugins/business/) | Measure and report the business value of AI workflows with provenance-tagged data — metrics in engineer-hours and cycle time, never currency. |

### Agents and models

| Plugin | Description |
|--------|-------------|
| [weave](plugins/weave/) | Run independent, adversarial AI participants via sub-agents or model CLIs to brainstorm, refine, plan, execute, architect, review, and synthesize. |
| [model-cli](plugins/model-cli/) | Run prompts through individual AI CLIs — Antigravity/agy (Gemini), codex/GPT, and cursor/agent with fallback support. |
| [agent-messaging](plugins/agent-messaging/) | Message another running agent session — Claude Code or Codex — and verify who actually sent an incoming message. |
| [self-improvement](plugins/self-improvement/) | Mine local agent prompt history for how the skill catalog is really used, then land the changes that usage evidence supports. |

### Machine upkeep

| Plugin | Description |
|--------|-------------|
| [disk](plugins/disk/) | Safely reclaim disk space. Classifies consumers as cache, redundant copy, or history, deleting only what is proven safe. |

## Installation

### Claude Code

Add the marketplace from inside Claude Code:

```text
/plugin marketplace add tony/skills
```

Then install any plugin by the name in the table above:

```text
/plugin install commit@skills
```

`/plugin > Discover` browses the same list.

### Codex

Add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Then install any plugin by the name in the table above:

```console
$ codex plugin add commit@skills
```

Each workflow is one skill, invoked as `/slop:deslop` under Claude Code and
`slop:deslop` under Codex.

### Other agents

`.agents/skills/` holds every skill flattened, with its references copied in,
for agents that scan that directory (Cursor, pi, Antigravity, Grok). The
`skills` CLI installs from it:

```console
$ npx skills add tony/skills
```

## How plugins find project tooling

A skill that runs tests, lint, a formatter, a type checker, or a build reads
those commands from the project's `AGENTS.md` or `CLAUDE.md` at run time
instead of assuming `pytest` or `npm test`. Commit formats come from the same
files and from the repository's own history. Plugins named for a tool
(pytest-optimizer, ruff, tailwind, terraform) target that tool; the rest
assume no language.

## How quality is checked

- Every plugin ships eval cases in `plugins/<name>/evals/`: prompts with
  graders that assert what the skill did, including what it refused to do.
  Run a plugin's suite with `claude plugin eval plugins/<name>`.
- `scripts/skill_evals.py check` routes every trigger prompt in
  `evals/cases/` against every skill description and fails when two
  descriptions collide. It makes no model calls, so it runs on every pull
  request. [evals/README.md](evals/README.md) covers the model-backed suites.
- `scripts/marketplace.py lint` enforces the skill-authoring rules in
  [AGENTS.md](AGENTS.md).
- `scripts/e2e.py` takes every plugin through add, install, disable,
  enable, and uninstall in Claude Code and Codex under a throwaway `HOME`,
  and checks each skill's frontmatter.

## Development

Scripts run under [uv](https://docs.astral.sh/uv/getting-started/installation/).
[AGENTS.md](AGENTS.md) holds the authoring rules and the commands for every
check CI runs. `scripts/marketplace.py portable` writes the generated files
(`.agents/`, each plugin's `.codex-plugin/plugin.json`, and each plugin's copy
of a file in `shared/`); edit the sources and regenerate, never the outputs.

## Documentation

See the [official Claude Code plugin docs](https://code.claude.com/docs/en/plugins) for
authoring guides, component schemas, and marketplace publishing.

## License

MIT
