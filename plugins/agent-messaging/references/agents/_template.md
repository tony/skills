# Adapter: <agent name>

Copy this file to a new file named for the agent, beside the existing adapters, and fill
every section. Mark an unanswerable section `UNKNOWN` with a note on what you tried; a blank
is a bug. If supporting your agent requires changing the skill rather than this file, say so
under **Gaps**.

## Contents

1. Identity
2. Discovery
3. Transports
4. Delivery semantics
5. Provenance
6. Inbound controls
7. Loop and abuse safety
8. Typing quirks (tmux)
9. Environment
10. Gaps

## 1. Identity

- Own address: how a running session learns the string others use to reach it.
- Where it is exposed: env var, slash command, status pane, file on disk.
- Stability: does it survive a resume, a rename, a restart?
- Human-readable name: how one is set, whether names are unique, what happens on collision.
- Reply target: the address actually supplied on receipt; distinguish it from a display name.

## 2. Discovery

- Enumerate peers: exact command or tool.
- Scope: same machine only, or wider? Same home directory? Same container?
- What a listing shows: name, id, cwd, status, liveness.
- Blind spots: which sessions never appear, and why.
- Listing boundary: independent sessions versus a native agent tree; process presence versus
  an advertised inbox. Name any undocumented registry fallback and revalidation rule.

## 3. Transports

One block per transport this agent supports, sender side and receiver side.

- Name (tmux / codex-queue / claude-code-message / claude-code-socket / new).
- Direction: can this agent send on it, receive on it, or both.
- Invocation: the exact command, tool call, or frame. Copy-pasteable.
- Preconditions: daemon running, experimental capability, feature flag, socket bound,
  version floor.
- Failure mode when the precondition is missing: verbatim error text.
- Ownership and capabilities: which server owns the receiver, how to inspect it without
  starting another server or injecting a probe message, and any unsupported-method result.

## 4. Delivery semantics

- When a message reaches the model: immediately, between tool calls, only when idle.
- Latency: idle and mid-turn.
- Target not running: dropped, or durable and delivered on resume.
- Lifecycle: distinguish transport acceptance, held/refused notices, resume, queue changes,
  model input and assistant acknowledgment. State which failures still return send success.
- Inspection: supported read-only client, exact receipt IDs and pagination; a verified local
  database fallback if needed. Correlation IDs are not assumed to be idempotency keys.
- Ordering: under rapid sends.
- Caps: message size, queue depth, burst limits, and the behavior at each.
- Interrupt interaction: what an interrupted turn does to pending messages.

## 5. Provenance

The section the skill depends on most.

- Sender label: what the receiver is told, verbatim. `none` is a valid and important answer.
- Reply address: supplied by the harness, or only by convention in the body?
- Authority: does an arriving message carry the operator's authority, or is it marked as
  a peer with reduced rights?
- Spoofable: can a sender forge another sender's identity? By what mechanism?
- Distinguishable from the operator: can the receiver tell a peer message from its human
  typing the same text?
- Audit limits: recorded process-start identity, PID reuse/exit, missing fields and platform
  differences. A body label and a display name are not authentication.

## 6. Inbound controls

- Gating: accept / hold / refuse equivalents, and where they are configured.
- Hooks or filters: that can drop a message before the model sees it.
- Default posture: when nothing is configured, including anything that varies by
  permission mode.
- Turning it off: entirely, sending and receiving separately.
- Configuration scope: prefer explicitly approved launch settings over shared user changes;
  identify precedence, ordinary headless inboxes and excluded minimal modes.

## 7. Loop and abuse safety

- Rate limiting, dedupe, queue caps, and whether a two-agent ping-pong terminates on its own.
- If nothing built in: say so, and state what the skill must add.

## 8. Typing quirks (tmux)

- Submit key:, and how to send a literal newline without submitting.
- Reserved leading characters: that open a UI mode instead of entering text.
- Paste behavior: bracketed paste support, safe maximum length, `send-keys -l` vs
  `load-buffer` + `paste-buffer`.
- Racing an active turn: does typed input queue, interrupt, or get lost?
- Collapsed previews: how full staged content is verified; withdraw only a proven owned,
  unsubmitted draft. A visible card or pending preview is not model receipt.

## 9. Environment

Variables a spawned command can read that matter for messaging — own address, socket path,
auth token, home directory, sandbox indicators. Name each and say what sets it.

## 10. Gaps

What this agent cannot do that others can, what is undocumented, and what the skill must work
around.

Mark each claim you did not test `(unverified — from source)` when read from the agent's
code, or `(unverified — from docs)` when read from vendor documentation.
Keep partial observations partial, and state the receiver kind and route a positive result
actually covers. Link pinned source contracts and release floors; distinguish new additions
from older omissions. Related optional interfaces need separate prerequisites and runtime
evidence, not an implied fallback route. Do not ship private research logs or test inventories.
