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
run is write-enabled in the live working tree (`codex --yolo`,
`agy --dangerously-skip-permissions`, `agent -f`), so the delegated model can
edit files and run commands there. That is the design; commit or stash first
if the tree matters.

## Plan mode

Add `mode:plan` (for example `/model-cli:codex review the auth flow mode:plan`)
to get a plan without edits. Plan mode swaps each tier's flags for the CLI's
own read-only mode:

- `codex exec --sandbox read-only` for Codex.
- `agent --mode plan` for Cursor's agent.
- `agy --mode plan` for Antigravity, without the permission-skipping flag, so
  headless runs auto-deny any edit or command.

## Models and fallback

The model IDs in the skills are defaults. A model you name in the request
replaces the default for the tier it fits, and an unknown ID triggers a lookup
with `agy models` or `agent --list-models`.

- `agy` and `gemini`: `agy` with Gemini 3.1 Pro, then `agent` with
  `gemini-3.1-pro`, then `agy` with Gemini 3.8 Flash.
- `codex` and `gpt`: `codex`, then `agent` with `gpt-5.4-high`, then `agent`
  with `gpt-5.4-mini-medium`.
- `cursor`: `agent`, no fallback.

A tier that crashes (for example, not logged in) falls through to the next
tier that uses a different binary.

## Timeout

The default is 600 seconds. Override with `timeout:<seconds>` or disable with
`timeout:none`. On macOS, install GNU coreutils for `gtimeout`:

```console
brew install coreutils
```

Without `timeout` or `gtimeout`, runs have no time limit.

## Prerequisites

Install at least one CLI:

- `agy`: [Antigravity CLI](https://antigravity.google/product/antigravity-cli)
- `codex`: [Codex CLI](https://github.com/openai/codex)
- `agent`: [Cursor CLI](https://cursor.com/cli)
