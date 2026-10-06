# Weave worker backends

Every weave ensemble resolves its worker backend before gathering project
context or starting an operational phase. The choice controls how every
participant, judge, refinement pass, and cascade escalation runs for the
session.

## Contents

- Caller contract
- Backend adapter
- Adversarial sub-agents
- Separate model CLIs
- Shared execution semantics

## Caller contract

The engine's `flags` command parses `--workers=subagents|model-clis` out of
`$ARGUMENTS` and reports it as `workers`; an invalid value is an error that
stops before execution. Set `worker_backend` from it.

When the flag is absent and an interactive choice tool is available, make this
the first question:

- **Question**: "How should weave run its adversarial workers?"
- **Header**: "Workers"
- **Adversarial sub-agents (Recommended)**: independent workers supplied by the
  current host. No separate AI command-line tools are launched.
- **Separate model CLIs**: the command's external-model lanes, with their
  detection, timeout, and retry behavior.

When interactive choice is unavailable or the session is headless, default to
`subagents`. The engine records `worker_backend` in session metadata and the
session-start event.

The selected backend is a session boundary. Retry and fallback may occur
within that backend, but never across it. Never switch from sub-agents to model
CLIs, or from model CLIs to sub-agents, without a new explicit user choice.

Result rendering takes `worker_backend` as `WORKER_BACKEND`, the successful
artifact IDs as `PARTICIPANTS`, the participant-to-executor mapping as
`EXECUTORS`, and resolved providers or models as `MODELS` (only for
`model-clis`). All four come from `session.json`.

## Backend adapter

The selected backend governs the whole session: setup, dispatch, retry,
artifact capture, judging, cascade, refinement, session metadata, result
rendering, and cleanup. `init` resolves an ordered participant roster once;
every later phase uses it.

Each roster entry has four independent values:

- `role_id`: `maintainer`, `skeptic`, or `builder`.
- `participant_id`: the stable artifact and attribution ID for this backend.
- `executor`: `host-native`, `host`, `agy`, `codex`, or the resolved fallback
  executable.
- `model`: optional provider/model information reported by the executor.

Never infer one value from another. In particular, the `gpt` participant ID is
not an executable; its normal model-CLI executor is `codex`.

Use `<participant>` as the placeholder in backend-independent paths and
events. A single output is
`$SESSION_DIR/pass-NNNN/outputs/<participant>.md`; a variant is
`$SESSION_DIR/outputs/<participant>-v<N>.md`. Blind-label maps point to
participant IDs.

The command supplies the task prompt, context packet, project-access mode,
pass and variant numbers, output schema, rubric, and convergence rules. The
adapter turns those values into one WorkItem per participant:

- role and participant identity
- task prompt and context packet
- `read-only` or `mutating` project access
- pass, optional variant, and optional judge kind
- output path and isolated worktree path

When `worker_backend == subagents`, dispatch WorkItems through the native
protocol below, then resume at the command's backend-independent verification,
rubric, synthesis, transition-gate, adoption, and presentation steps. Read
generic uses of "model" in those shared steps as "participant". Host judging
means the current orchestrator, never an assumed provider.

### Session contract

Every `session.json` and `session_start` event records `worker_backend`
and the ordered `participants`. `session.json` also records `executors` as an
object keyed by participant ID, and `models` only for `model-clis`. Pass and
completion events use participant IDs, including `participants_completed`,
`winner`, and `judged_by`. `update --drop` removes a worker that becomes
unavailable. Never write native role IDs to `models`.

## Adversarial sub-agents

Use three independent host-native sub-agents. Dispatch them in parallel when
the host has capacity; otherwise queue them without combining roles or sharing
intermediate answers. Each WorkItem launches a fresh sub-agent; the
orchestrator persists the returned response to its declared output path.

### Maintainer

Prioritize correctness, project conventions, and minimal scope. Challenge work
that is not necessary for the stated goal.

### Skeptic

Challenge assumptions, expose failure modes and unstated requirements, and
test whether the proposed direction is sound.

### Builder

Prioritize simple, practical, shippable work. Identify unnecessary abstraction
and favor the shortest design that satisfies the contract.

Give every role the same task, context packet, constraints, and repository
baseline. Each sub-agent starts from an independent context and must not read
another role's output before its own artifact is complete.

Use role identities for artifacts and attribution:

- `maintainer`
- `skeptic`
- `builder`

Write a single result as `<role>.md` and a variant as `<role>-v<N>.md`.
User-facing output names the role and identifies the worker backend as
`subagents`; it must not claim that the roles are different models. The
executor of every role is `host-native`; record a provider or model only when
the host reports one.

For project-read-only commands, give every role its own disposable isolated
worktree under the session directory, created from the pre-dispatch snapshot
(`worktrees create`), so the role sees the user's uncommitted work. Point the
worker at that worktree, never the user's working tree. Prompt hardening still
forbids project writes, so an accidental write is contained in a disposable tree.

For mutating commands, give every role its own isolated worktree on a
dedicated branch, including the Maintainer. A sub-agent may modify only its
assigned worktree. Keep the worktree across that role's refinement passes.
Compare and snapshot changes by participant ID, then adopt selected work only
through the command's synthesis flow.

After a read-only WorkItem returns, or after a mutating participant's diffs
and snapshots have been captured, remove only that participant's exact
session-scoped worktree. Native workers never run `checkout`, `clean`, or
`reset` against the user's checkout. The repo guard reports any change to the
checkout and never repairs it on its own (see the plugin's `docs/repo-guard-protocol.md`).

If the host cannot create native sub-agents, stop with a direct explanation.
In an interactive session, offer a new explicit choice to use separate model
CLIs. In a headless session, explain that the user can rerun with
`--workers=model-clis`; do not launch them automatically.

## Separate model CLIs

Run CLI detection only after the user explicitly selects `model-clis`; `init`
does it. The engine owns timeout handling, retry classification, lesser-model
fallback, and stderr capture.

Participant IDs stay fixed while roles and executors are recorded separately:

- `claude` carries the Maintainer role and runs through the host agent.
- `agy` carries the Skeptic role and normally runs through the `agy` CLI.
- `gpt` carries the Builder role and normally runs through the `codex` CLI.

Attribute each result with its role, lane artifact ID, and resolved executor.
Fallbacks stay within the lane's chain. If a lane exhausts that chain, mark
its lane artifact ID unavailable; do not replace it with a host-native sub-agent.

Every read-only CLI lane runs in a disposable worktree built from the
pre-dispatch snapshot; a mutating lane runs in its own branch worktree.

## Shared execution semantics

### Partial failure

Retry a failed worker only through mechanisms provided by the selected
backend. A sub-agent retry creates a fresh independent sub-agent with the same
role and input. A model-CLI retry is the engine's dispatch retry and fallback.

Continue with two successful roles and report the unavailable role. With one
successful role, produce a single-role result, omit consensus claims, and
state that adversarial comparison was unavailable. If every role fails, stop
and report each failure without synthesizing an answer.

### Judging

Host judging evaluates the successful participant artifacts regardless of
backend and records `judged_by = host`. Round-robin judging rotates across
successful participant IDs in roster order, not model names; `judge-plan` picks
the judge. A native round-robin judge is a fresh sub-agent assigned the selected
role; a model-CLI judge runs through `dispatch --judge`.

Panel judging dispatches one independent judge per successful role. Peer-only
scoring excludes the artifact-producing role's own judge. With too few judges
for peer scoring, use the command's degraded-panel or host fallback and name the
degradation. Judges receive immutable copies of the candidate artifacts and the
shared rubric, and never modify project files or candidates.

### Cascade

A cascade cheap pass uses the Maintainer role through the selected backend. If
the confidence gate escalates, launch the Skeptic and Builder through that same
backend and reuse the completed Maintainer artifact. An early exit is
attributed to the Maintainer role only. Escalation never changes
`worker_backend`, even when a role is unavailable.

### Refinement

Every refinement pass redispatches the successful participants through the
selected backend, preserving role and participant identities so attribution,
judge rotation, and failure reporting stay stable.
