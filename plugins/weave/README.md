# weave

Run independent, adversarial AI participants via sub-agents or model CLIs to
brainstorm, refine, plan, execute, architect, review, and synthesize.

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install weave --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install weave@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add weave@skills
```

Claude Code uses a leading slash (`/weave:…`). Codex omits it (`weave:…`).

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/weave:ask` | `weave:ask` | Ask adversarial participants a question, synthesize the best answer |
| `/weave:plan` | `weave:plan` | Get independent implementation plans, synthesize the best plan |
| `/weave:prompt` | `weave:prompt` | Run a prompt in isolated worktrees, pick the best implementation |
| `/weave:execute` | `weave:execute` | Run a task in isolated worktrees, synthesize the best parts of each |
| `/weave:architecture` | `weave:architecture` | Generate project scaffolding, conventions, skills, and architectural docs, then synthesize the best architecture |
| `/weave:review` | `weave:review` | Run independent code reviews, produce a consensus-weighted report |
| `/weave:fix-review` | `weave:fix-review` | Fix review findings as atomic commits with test coverage |
| `/weave:brainstorm` | `weave:brainstorm` | Generate independent original ideas from each participant, with optional multiple variants |
| `/weave:refine` | `weave:refine` | Iteratively improve an artifact through adversarial critique and weaving |
| `/weave:brainstorm-and-refine` | `weave:brainstorm-and-refine` | Full pipeline: brainstorm originals, then iteratively judge, weave, and refine |
| `/weave:serene-bliss` | `weave:serene-bliss` | Three-lens DX brainstorm-and-refine (Bliss, Serenity, Sublimity) with panel judging |

## How It Works

Every ensemble command runs the same sequence:

1. **Choose workers**: `--workers=subagents|model-clis` (sub-agents recommended).
2. **Configure**: parse flags, then ask for what is still unset.
3. **Run in parallel**: dispatch the Maintainer, Skeptic, and Builder lanes.
4. **Synthesize**: verify claims, score blind, combine the best elements.
5. **Refine**: for more than one pass, re-attack what is unresolved.

Multi-pass differs by command:

- **Residual re-attack** (ask, review): a pass N of 2 or more receives only the unresolved items from the prior pass.
- **Targeted conflict resolution** (plan, prompt, execute, architecture): a later pass addresses only unresolved conflicts, critic findings, and low scores.
- **Expansive weaving** (brainstorm-and-refine, refine): each pass is a full judge, weave, and distribute cycle.
- **Remediation** (fix-review): applies review findings as atomic commits; multi-pass does not apply.

Finding commits run hooks in an isolated worktree and publish only the
approved file bytes. Hook edits or concurrent index/HEAD changes stop the
commit and retain recovery artifacts. Unrelated staging and working files
stay untouched; edits arriving after capture remain unstaged. Hooks remain
trusted project programs, not a security sandbox.

Worker backends are strictly isolated: retry and fallback stay inside the chosen backend.

### When not to use

Skip weave for a task one agent answers in a single pass: a typo, a rename, a question whose answer is in one file. Independent workers, judging, and refinement add cost. Use them when comparing alternatives and checking disagreements is worth that cost.

### Command categories

Commands that need commits (`execute`, `prompt`, `architecture`, `review`, `fix-review`) refuse in one sentence without a git repository that has at least one commit. `ask` and `plan` degrade with a stated "no repository" note. `brainstorm`, `brainstorm-and-refine`, `refine`, and `serene-bliss` run anywhere: with no usable repository the repo guard is off and workers start in an empty scratch directory. A checkout rooted at `/`, at your home directory, or at a directory containing your home directory counts as no repository, and a command that snapshots, stashes, or adds worktrees refuses it.

- **Read-only** (`ask`, `plan`, `brainstorm`, `refine`, `brainstorm-and-refine`, `serene-bliss`, `review`): gather perspectives and synthesize. Workers and executable verification use scratch worktrees; the final guard must attest checkout state before the result is presented.
- **Write**: `prompt`, `execute`, and `architecture` give every participant its own worktree, including the host `claude` lane under `--workers=model-clis`. The engine stashes your uncommitted work first and restores it after the apply decision. `prompt` picks one winner, `execute` selects the best parts, and `architecture` selects conventions, skills, and scaffolding per file. Only approved snapshots reach your checkout. `fix-review` edits the checkout and commits findings one by one.

### Shared protocols

- **Context packet**: conventions, repo state, and key snippets go verbatim into every prompt, so all lanes work from the same information.
- **Role differentiation**: each lane gets a distinct lens (Maintainer, Skeptic, Builder) to reduce shared blind spots.
- **Blind judging**: outputs get random labels during scoring to prevent identity bias.
- **Structured synthesis**: verify claims, score against a rubric, adjudicate conflicts, converge, then a critic pass, all backed by codebase evidence.
- **Consensus signal**: findings carry per-lane agreement tags (unanimous, majority, split, single); split items keep both positions (ask, review).
- **Judge, weave, distribute**: pick the best, take strengths from runners-up, redistribute (refine, brainstorm-and-refine).

## Engine

`scripts/engine.py` runs the deterministic work: flag parsing, session setup, model-CLI dispatch with retry and fallback, worktrees, diff capture, judging helpers, and the repo guard. It needs `python3` (3.9 or newer) and `git` on a POSIX system. `scripts/test_engine.py` tests it against real git repositories and stub CLIs. `python3 scripts/engine.py --help` lists every command.

Shared judgment prose lives in `references/ensemble-core.md` (context packet, dispatch, blind judging, synthesis, consensus), `references/ensemble-techniques.md` (cascade and residual re-attack), `references/present-results.md` (shared rendering rules, plus one file per result kind in `references/results/`), and `references/deslop-pass.md`. `references/worker-backends.md` defines the two backends.

## Repo Guard

`init` records tracked and non-ignored untracked content, staging, and HEAD.
It pins the content snapshot under `refs/weave-guard/<session>/`. Read-only
lanes use snapshot worktrees; mutating lanes use their own branches.
Native prompts specify an absolute root for every file and shell call. These
are cooperative instructions, not a filesystem sandbox: a worker can escape
through an absolute path or an incorrectly rooted tool call.

The guard compares content, staging, and HEAD after dispatch and before
presentation. Drift retains recovery snapshots without rewriting the checkout.
A mutating violation stops before adoption or cleanup, preserving leaked
work and the original user stash for inspection. Read-only runs can offer keep,
revert, or quarantine; headless runs keep the drift and cannot claim unchanged.

## Flags

| Flag | Values | Default | Example |
|------|--------|---------|---------|
| `--workers=...` | `subagents` or `model-clis` | `subagents` | `/weave:ask --workers=model-clis question` |
| `--passes=N` | 1-5 | per command | `/weave:plan --passes=2 add auth` |
| `--timeout=N\|none` | seconds or `none` | per command (`model-clis` only) | `/weave:ask --timeout=300 question` |
| `--mode=fast\|balanced\|deep` | preset | `balanced` | `/weave:execute --mode=deep task` |
| `--cascade` | flag (ask, review) | off | `/weave:ask --cascade question` |
| `--variants=N` | 1-3 | 1 | `/weave:brainstorm --variants=2 idea` |
| `--judge=host\|round-robin` | who judges each refinement pass | `host` | `/weave:refine --judge=round-robin draft` |
| `--preamble=...` | text | built-in | `/weave:brainstorm --preamble='focus on perf' idea` |
| `--no-deslop`, `--quiet-deslop`, `--verbose-deslop` | flags | off | `/weave:ask --quiet-deslop question` |

Flags are read only from the start of the arguments; the first word that is not a flag, or a bare `--`, begins the prompt, so flag-like words inside your text stay untouched. The engine's `PROFILES` table holds each command's defaults. `ask`, `plan`, `prompt`, `execute`, `architecture`, and `review` presets are `fast` (1 pass, 0.5x timeout), `balanced` (1 pass, 1x), and `deep` (2 passes, 1.5x). `brainstorm` presets set variants (`deep` is 2). `refine` presets are 1, 2, and 3 passes. `brainstorm-and-refine` and `serene-bliss` presets set passes the same way, and `brainstorm-and-refine` also sets variants.

Default timeouts: ask, brainstorm, refine, brainstorm-and-refine, serene-bliss 450s; plan and prompt 600s; review 900s; execute and architecture 1200s.

When a flag is set the matching question is skipped. Otherwise the command asks through `AskUserQuestion`: workers, pass count, and (for `model-clis`) timeout. Headless mode defaults to `subagents`. If the host cannot create native sub-agents, weave stops and explains how to rerun with `--workers=model-clis`; it never launches separate CLIs implicitly.

### Judge modes

`--judge=host` has the host agent judge every pass. `--judge=round-robin` rotates judging across successful participants: native mode launches a fresh role-matched sub-agent, model-CLI mode runs the lane's CLI. The host always weaves and judges that pass itself when a judge response cannot be parsed. `serene-bliss` fixes the judge to a panel with peer-only averaging.

## Plan Mode

`review`, `fix-review`, `execute`, `prompt`, and `architecture` enter plan mode to produce an orchestration plan, present it for approval, then exit plan mode before executing. `plan` enters plan mode first and stays there: the host's plan file is the deliverable, and host sub-agents handle the non-readonly work.

| Tool | Enter plan mode | Exit plan mode |
|------|----------------|----------------|
| Claude Code | `EnterPlanMode` tool | `ExitPlanMode` tool |
| Cursor | `/plan` or `Shift+Tab` | Exit per tool method |
| Codex | `/plan` | Exit per tool method |
| Gemini | `/plan` or `Shift+Tab` | Exit per tool method |

Without plan mode the commands still run; the phase structure guides the analysis before execution.

## Output

Commands render through `references/present-results.md` and their kind's file in `references/results/`: a hero block, prescribed sections in a fixed order, an Attribution footer, and a next-step panel that can hand the result off into plan mode.

## Workers

The default backend launches three independent host-native sub-agents (Maintainer, Skeptic, Builder) with the same task and context packet. They never see one another's answers before finishing their own. Artifacts use the IDs `maintainer`, `skeptic`, and `builder`; this mode does not claim different models.

The opt-in `model-clis` backend keeps the host, Antigravity, and GPT lanes, with artifact IDs `claude`, `agy`, and `gpt`. The GPT lane normally runs through `codex`. The engine owns each lane's fallback chain: `agy` falls back to `agent` with a Gemini model, then to a lesser Gemini model; `codex` falls back to `agent` with a GPT model, then to a lesser one.

## Cascade Mode

`--cascade` (ask, review) runs the Maintainer lane first, self-verifies it against the codebase, and launches the Skeptic and Builder only when a confidence trigger fires or the user escalates. The worker backend never changes on escalation.

## Deslop Pass

The prose-producing commands (`ask`, `refine`, `brainstorm-and-refine`, `serene-bliss`, `plan`, `review`) run a deslop pass on the final synthesis before it reaches the terminal. It detects slop signatures (flagship phrases, restated subjects, fragile counts and line numbers, AI footers) against the Tier A/B/C taxonomy that `/slop:deslop` and `/slop:scan` use, calibrated against the last 50 trunk commit messages. The pass reads its registry from `references/signatures.yml` in this plugin; without it, the pass emits a one-line skip and the synthesis is presented unchanged.

`brainstorm` is never desloped, because independent diversity is its product. `execute`, `prompt`, `architecture`, and `fix-review` produce code and rely on the project's quality gates.

The original synthesis stays next to the desloped one as `<artifact>.pre-deslop.md`:

```console
$ diff \
    "<session_dir>/pass-0001/synthesis.pre-deslop.md" \
    "<session_dir>/pass-0001/synthesis.md"
```

`<session_dir>/deslop-report.md` records the registry hash, applied, declined, and advisory findings, and the word delta. A 30% word-delta hard abort restores the original. A single edit that would remove 15% or more becomes advisory, and its held trim goes to `<artifact>-deslop-held.md`.

## Session Artifacts

Commands persist outputs, prompts, and synthesis results under a storage root, for inspection and for reference across passes.

The storage root is the first of `$AI_AIP_ROOT`, `$XDG_STATE_HOME/ai-aip`, `~/Library/Application Support/ai-aip` (macOS), and `$HOME/.local/state/ai-aip`.

A repo is `<slug>--<hash>`: the slugified directory name and 12 hex characters of a SHA-256 of the origin URL plus slug (the absolute path when there is no remote). A session ID is `<YYYYMMDD-HHMMSSZ>-<PID>-<4 hex chars>`.

```
$AI_AIP_ROOT/repos/<slug>--<hash>/
├── repo.json
└── sessions/<command>/
    ├── latest -> <SESSION_ID>
    └── <SESSION_ID>/
        ├── session.json
        ├── events.jsonl
        ├── metadata.md
        ├── context-packet.md
        ├── guard-events.jsonl
        ├── guard/<id>/          # only when the checkout changed
        ├── outputs/             # variants: <participant>-v<N>.md
        └── pass-0001/
            ├── prompt.md
            ├── prompts/
            ├── outputs/<participant>.md
            ├── stderr/
            ├── blind/
            ├── label-map.json
            ├── judges/
            ├── synthesis.md
            ├── diffs/           # write commands: <participant>.patch and .json
            └── files/           # write commands: changed-file snapshots per participant
```

With the default backend the participants are `maintainer`, `skeptic`, and `builder`; with `model-clis` they are `claude`, `agy`, and `gpt`. Only files that differ from `HEAD` are snapshotted into `files/<participant>/`; deleted files appear in the manifest only, so a later pass can cross-reference files without depending on worktree persistence. Pass directories use zero-padded numbering and mode 700, and stay after the session.

`session.json` records `session_id`, `command`, `status` (`in_progress` or `completed`), `toplevel`, `branch`, `ref`, `mutating`, `worker_backend`, `participants`, `executors` (participant ID to executor), `models` and `chains` (only for `model-clis`), `completed_passes`, `prompt_summary` (first 120 characters), `guard` (the snapshot; absent with `unguarded: true` in no-repo mode), and timestamps. `stash` records the user's stashed changes for a write command. `events.jsonl` holds one JSON object per line: `session_start`, `pass_complete`, `repo_guard_final`, and `session_complete`. The engine updates both atomically.

To list sessions, scan the `session.json` files under `sessions/<command>/`; `latest` points at the most recently completed session.

## Prerequisites

The default backend needs a host that can launch sub-agents. No separate provider CLI or account is required.

For `--workers=model-clis`, install one or more of these CLIs:

| CLI | Model | Install |
|-----|-------|---------|
| `agy` | Gemini (via Antigravity) | [Antigravity CLI](https://antigravity.google/product/antigravity-cli) |
| `codex` | GPT | [Codex CLI](https://github.com/openai/codex) |
| `agent` | Any (fallback) | [Agent CLI](https://cursor.com/cli) |

If no CLI resolves for a lane, weave reports the lane unavailable. It does not fall back to host sub-agents.

`init` picks each lane step's model once per session from that CLI's own listing (`agy models`, `agent --list-models`) with `scripts/closest_model.py`, taking the newest version of the step's tier. A step whose listing fails, times out, or has no match keeps its pinned model from `LANES` in `scripts/engine.py`, so the lane keeps its vendor; `codex` runs its own default model. `session.json` records the chain under `chains`, each step with its source (`live`, `pinned`, or `default`), and dispatch reuses it.

The engine enforces timeouts itself, so no `timeout` or `gtimeout` binary is needed. It closes each CLI's stdin, appends stderr to a per-lane file, and kills the CLI's whole process group on timeout.

To confirm which model the Antigravity lane runs, pass the `agy` model that a session recorded under `models` in its `session.json`:

```console
$ agy \
    --model "<recorded model>" \
    -p "Report your exact model ID and reasoning level." </dev/null
```

## Language-Agnostic Design

Commands read AGENTS.md / CLAUDE.md at runtime for quality gates, test commands, and conventions. Nothing is hardcoded for a language or framework.
