# skills

A third-party marketplace of language-agnostic AI workflow plugins. Plugins
install into [Claude Code](https://code.claude.com/docs/en/plugin-marketplaces.md)
and [Codex](https://developers.openai.com/plugins/build/plugins), and are
readable by agents scanning `.agents/skills/`. The marketplace is not
affiliated with or endorsed by Anthropic or OpenAI.

> **Warning:** Review plugins before installing. Anthropic does not control plugin
> contents and cannot verify they work as intended.

**Repository:** [tony/skills](https://github.com/tony/skills)

Status: pre-1.0. Skills change without a compatibility promise; pin a commit
to hold one version.

## Plugins

Most work starts with `situate` to get oriented, `commit` and `pr` to land
changes, and `respond` to screen review feedback.

### Git and pull requests

| Plugin | Description |
|--------|-------------|
| [commit](plugins/commit/) | Create git commits following project conventions with format enforcement and safety checks. |
| [rebase](plugins/rebase/) | Rebase onto remote trunk with a file-overlap reading before the replay, conflict resolution, and quality gate verification. |
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
| [package-updater](plugins/package-updater/) | Update dependencies and toolchains across repositories. Checks the supply-chain cooldown first when one is configured, then commits toolchain, named bumps, and lockfile refreshes separately with release notes cited. |
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
| [goal-planner](plugins/goal-planner/) | Print, synthesize, and audit portable goals; keep approved planning profiles and numbered goal specifications without activating work. |
| [action](plugins/action/) | Convert tickets to branches in isolated worktrees. Uses team branch conventions, lands gated commits, and supports parallel tickets. |
| [ticket](plugins/ticket/) | Manage work across trackers (Linear, Jira, GitHub, etc.) respecting each platform's native object graph. Drafts durable tickets focused on invariants. |
| [spike](plugins/spike/) | Run no-commit spikes, strategy bakeoffs, or multi-round convergence in git worktrees. Tests ideas against quality gates and returns a commit-by-commit implementation plan. |

### Writing and verification

| Plugin | Description |
|--------|-------------|
| [lean](plugins/lean/) | Writing discipline and cleanup tools for tight, slop-free prose and code. |
| [voice](plugins/voice/) | Write or rephrase copy for the reader who will use it, from a brief of who they are, what they came to do, where it renders, when they arrive, and why it matters. |
| [double-check](plugins/double-check/) | Forces verification requests to return re-derived answers instead of diffs against prior turns. The align skill restates a chat's analysis standalone after a revision-log reply. |
| [gh](plugins/gh/) | File durable GitHub issues with reproductions, pinned links, and stripped PII. Enforces a markdown writing discipline reusable for any PR, comment, or ticket. |
| [skill-style](plugins/skill-style/) | Hold SKILL.md files to a deletion test: a line stays only when removing it would change what the agent does. Frontmatter, code blocks, and sections survive verbatim. |

### Research

| Plugin | Description |
|--------|-------------|
| [research](plugins/research/) | Research topics and assess decisions with pinned, captured sources in dated folders. Resume, re-verify, report. Clones dependencies at pinned versions. |
| [scholar](plugins/scholar/) | Distil a checkable ontology from a codebase, a repository set, or a written corpus. Types, controlled vocabulary, cited and measured evidence. |
| [business](plugins/business/) | Measure and report the business value of AI workflows from provenance-tagged data, in engineer-hours and cycle time, never currency. |

### Agents and models

Experimental: these drive other vendors' CLIs or read undocumented session
internals, either of which can change without notice.

| Plugin | Description |
|--------|-------------|
| [weave](plugins/weave/) | Run independent, adversarial AI participants via sub-agents or model CLIs to brainstorm, refine, plan, execute, architect, review, and synthesize. |
| [model-cli](plugins/model-cli/) | Run a prompt through one AI CLI at a time: agy (Gemini), codex (GPT), or cursor's agent, with fallback between tiers. |
| [agent-messaging](plugins/agent-messaging/) | Message another running Claude Code or Codex session, and verify who actually sent an incoming message. |
| [self-improvement](plugins/self-improvement/) | Mine local agent prompt history for how the skill catalog is really used, then land the changes that usage evidence supports. |
| [repo-skills](plugins/repo-skills/) | Derive a repository's own agent skills from its docs, git history, CI, shell history, and AI transcripts, test each with and without itself, and land them in two commits. |

### Machine upkeep

| Plugin | Description |
|--------|-------------|
| [disk](plugins/disk/) | Safely reclaim disk space. Classifies consumers as cache, redundant copy, or history, deleting only what is proven safe. |

## Installation

### Claude Code

From a shell, one command installs a plugin and adds the marketplace first
if it is missing:

```console
$ claude plugin install commit --marketplace tony/skills
```

Or add the marketplace from inside Claude Code:

```text
/plugin marketplace add tony/skills
```

Then install any plugin by the name in the table above:

```text
/plugin install commit@skills
```

`/plugin > Discover` browses the same list.

### Codex

Codex has no single-command form; add the marketplace once:

```console
$ codex plugin marketplace add tony/skills
```

Then install any plugin by the name in the table above:

```console
$ codex plugin add commit@skills
```

Each workflow is one skill, invoked as `/slop:deslop` under Claude Code and
`slop:deslop` under Codex. A skill that runs only when named sets
`disable-model-invocation` for Claude Code and `allow_implicit_invocation: false`
in its `agents/openai.yaml` for Codex.

### Other agents

`.agents/skills/` holds every skill flattened, with its references copied in,
for agents that read skills from that directory. The `skills` CLI installs
from it:

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
- An offline routing check scores every trigger prompt against every skill
  description and fails when two descriptions collide, so one skill does not
  steal another's prompts. [evals/README.md](evals/README.md) covers the
  model-backed suites and their credentials.
- CI installs every plugin into Claude Code and Codex under a throwaway
  `HOME` and checks each skill's frontmatter.

[AGENTS.md](AGENTS.md) lists the commands for each check.

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
