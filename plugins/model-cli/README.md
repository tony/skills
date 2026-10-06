# model-cli

Run prompts through individual AI CLIs — Antigravity/agy (Gemini),
codex/GPT, and cursor/agent with fallback support.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install model-cli@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add model-cli@skills
```

## Skills

| Skill | Claude Code | Codex | Description |
|---|---|---|---|
| Antigravity CLI | `/model-cli:agy` | `model-cli:agy` | Run a prompt through the Antigravity (`agy`) CLI for Gemini, fall back to gemini then agent |
| Codex CLI | `/model-cli:codex` | `model-cli:codex` | Run a prompt through the Codex CLI (OpenAI GPT), fall back to agent |
| GPT CLI | `/model-cli:gpt` | `model-cli:gpt` | Alias for codex — same backend, same fallback |
| Gemini CLI | `/model-cli:gemini` | `model-cli:gemini` | Alias for agy — Antigravity supersedes the gemini CLI; same backend chain |
| Cursor Agent CLI | `/model-cli:cursor` | `model-cli:cursor` | Run a prompt through Cursor's agent CLI directly |

The agy, codex, and cursor skills trigger automatically during delegation.
The gpt and gemini aliases are user-invocable only to avoid duplicate
auto-triggering.

## How It Works

Each skill follows a 6-step workflow:

1. **Capture:** Extracts prompt and timeout triggers (`timeout:<seconds>` or
   `timeout:none`) from `$ARGUMENTS`.
2. **Detect CLI:** Checks for the native binary or falls back to `agent`.
3. **Detect Timeout:** Validates `timeout` or `gtimeout` availability.
4. **Execute:** Runs CLI with timeout limits via temporary prompt files.
5. **Handle Failure:** Classifies failures (timeout, rate-limit, crash, empty
   output) and retries transients.
6. **Clean Up:** Presents the result, backend source, and removes temporary
   files.

### Fallback Resolution

| Skill | Primary CLI | Fallback chain | Agent model |
|-------|------------|----------------|-------------|
| `agy` / `gemini` | `agy --model "Gemini 3.1 Pro (High)" --dangerously-skip-permissions -p` | `gemini -m gemini-3-pro-preview` → `agent --model gemini-3.1-pro` | `gemini-3.1-pro` |
| `codex` / `gpt` | `codex` | `agent --model gpt-5.4-high` | `gpt-5.4-high` |
| `cursor` | `agent` | none | — |

### Timeout

Defaults to 600 seconds. Override with `timeout:<seconds>` or disable with
`timeout:none`.

## Prerequisites

Install at least one external CLI:

| CLI | Model | Install |
|-----|-------|---------|
| `agy` | Gemini (via Antigravity) | [Antigravity CLI](https://antigravity.google/product/antigravity-cli) |
| `codex` | GPT | [Codex CLI](https://github.com/openai/codex) |
| `gemini` | Gemini (fallback) | [Gemini CLI](https://github.com/google-gemini/gemini-cli) |
| `agent` | Cursor (fallback) | [Agent CLI](https://cursor.com/cli) |

Install the Antigravity CLI:

```console
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

### macOS timeout support

On macOS, install GNU coreutils to enable `gtimeout`:

```console
brew install coreutils
```

If neither `timeout` nor `gtimeout` is found, commands run without time limits.

## Plan-Only Mode

Add `mode:plan` to any invocation (e.g., `/model-cli:codex analyze mode:plan`)
for a detailed implementation plan without making changes. This triggers a
preamble instructing the model to analyze and describe rather than execute.

## Comparison with weave

| Feature | weave | model-cli |
|---------|------|-----------|
| Parallel execution | All models at once | Single model |
| Synthesis | Best-of-all merge | Direct output |
| Multi-pass refinement | Supported | Not applicable |
| Worktree isolation | For write commands | Not needed |

## Shell Resilience

- **Portable detection:** Uses `command -v` instead of `which`.
- **Injection prevention:** Writes prompts to temporary files
  (`/tmp/mc-prompt-XXXXXX.txt`).
- **Diagnostics:** Captures stderr to separate files
  (`/tmp/mc-stderr-<model>.txt`).
- **Retry protocol:** Classifies failures (timeout, rate-limit, crash, empty
  output) and retries transient errors once.
