# model-cli

Run a prompt through another vendor's AI CLI (Antigravity/agy for Gemini,
codex for GPT, Cursor's agent) with a fallback chain.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install model-cli --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install model-cli@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add model-cli@skills
```

Claude Code uses a leading slash (`/model-cli:…`). Codex omits it (`model-cli:…`).

## Skills

- `/model-cli:agy` (`model-cli:agy` in Codex): Gemini through `agy`, falling
  back to `agent`.
- `/model-cli:codex` (`model-cli:codex`): GPT through `codex`, falling back to
  `agent`.
- `/model-cli:cursor` (`model-cli:cursor`): Cursor's `agent` only.

Each skill follows `references/dispatch.md`, which owns triggers, failure
classes, and the report format.

## Risks

Your prompt, and any code in it, is sent to the vendor behind the CLI. Normal
runs are write-enabled. Codex bypasses approvals and sandboxing with
`--dangerously-bypass-approvals-and-sandbox`; agy auto-approves tools with
`--dangerously-skip-permissions`. Cursor's `agent -f` allows commands while
preserving its configured sandbox. These runs can edit files, execute commands,
and use the network. Use `mode:plan` for a review that must not change anything.
The prompt is also an argument of the CLI process, so other local users can
see it in `ps`.

`codex` also passes `--skip-git-repo-check`, which removes Codex's repo guard.
Commit or stash first; outside a git repository nothing the run changes can be
undone. Before allowing a failed tier to fall back, the runner compares the
whole repository's tracked and non-ignored files, index, branch, and HEAD.
Changed state stops fallback; a failed write-enabled run also stops when the
state is unreadable. Ignored files and writes outside the repository are
outside that check.

## Plan mode

Add `mode:plan` (for example `/model-cli:codex review the auth flow mode:plan`)
to get a plan without edits. Each tier swaps its write-enabled flags for the
CLI's own read-only mode; the flags are in each skill's `SKILL.md`.

## Models and fallback

Each skill lists its tiers and default models. A model you name in the request
replaces the default for the tier it fits, and an unknown ID triggers a lookup
with `agy models` or `agent --list-models`. A tier that fails (for example,
not logged in) falls through to the next tier; which tier depends on the failure
class, listed in `references/dispatch.md`.

## Timeout

The default is 540 seconds. Override with `timeout:<seconds>` or disable
with `timeout:none`; `references/dispatch.md` holds the rules for longer
runs.

## Prerequisites

Install at least one CLI:

- `agy`: [Antigravity CLI](https://antigravity.google/product/antigravity-cli)
- `codex`: [Codex CLI](https://github.com/openai/codex)
- `agent`: [Cursor CLI](https://cursor.com/cli)

`python3` (3.9 or newer) on a POSIX host runs `scripts/run_tier.py`.
The runner uses process groups to stop delegated children; native Windows
execution is not supported.
