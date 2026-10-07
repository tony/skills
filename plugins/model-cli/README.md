# model-cli

Run a prompt through another vendor's AI CLI (Antigravity/agy for Gemini,
codex for GPT, Cursor's agent) with a fallback chain.

## Installation

In Claude Code, add the marketplace:

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
- `/model-cli:gemini` and `/model-cli:gpt`: user-invocable aliases for `agy`
  and `codex`, so the model does not route to two skills for one request.

Each skill follows `references/dispatch.md`, which owns triggers, failure
classes, and the report format.

## Risks

Your prompt, and any code in it, is sent to the vendor behind the CLI. A normal
run is write-enabled and has no sandbox (`codex --yolo`,
`agy --dangerously-skip-permissions`, `agent -f`): the delegated model can
edit any file you can, run any command, and use the network. That is the
design; use `mode:plan` for a review that must not change anything.
The prompt is also an argument of the CLI process, so other local users can
see it in `ps`.

`codex` also passes `--skip-git-repo-check`, which removes Codex's repo guard.
Commit or stash first; outside a git repository nothing the run changes can be
undone.

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

The default is 540 seconds, so one foreground Bash call (timeout plus 10
seconds) fits the 600-second tool cap. Override with `timeout:<seconds>` or
disable with `timeout:none`. `scripts/run_tier.py` enforces it, so no `timeout` or
`gtimeout` command is needed. A longer timeout runs in the background where
the host has background runs; otherwise it is clamped to 540 seconds.

## Prerequisites

Install at least one CLI:

- `agy`: [Antigravity CLI](https://antigravity.google/product/antigravity-cli)
- `codex`: [Codex CLI](https://github.com/openai/codex)
- `agent`: [Cursor CLI](https://cursor.com/cli)

`python3` (3.9 or newer) runs `scripts/run_tier.py`, which launches each tier.
