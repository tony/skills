# Adapter: <agent name> <version>

Copy this file to a new file named for the agent, beside the existing adapters, and fill
every section. Any section you
cannot answer stays in the file marked `UNKNOWN` with a note on what you tried — a blank is a
bug, `UNKNOWN` is data.

The skill reads adapters, never agent-specific code paths. If supporting your agent requires
changing the skill rather than this file, say so under **Gaps** — that is a finding about the
skill's design.

## 1. Identity

- **Own address**: how a running session learns the string others use to reach it.
- **Where it is exposed**: env var, slash command, status pane, file on disk.
- **Stability**: does it survive a resume, a rename, a restart?
- **Human-readable name**: how one is set, whether names are unique, what happens on collision.

## 2. Discovery

- **Enumerate peers**: exact command or tool.
- **Scope**: same machine only, or wider? Same home directory? Same container?
- **What a listing shows**: name, id, cwd, status, liveness.
- **Blind spots**: which sessions never appear, and why.

## 3. Transports

One block per transport this agent supports, sender side and receiver side.

- **Name** (tmux / codex-queue / claude-code-message / claude-code-socket / new).
- **Direction**: can this agent send on it, receive on it, or both.
- **Invocation**: the exact command, tool call, or frame. Copy-pasteable.
- **Preconditions**: daemon running, experimental capability, feature flag, socket bound,
  version floor.
- **Failure mode when the precondition is missing**: verbatim error text.

## 4. Delivery semantics

- **When a message reaches the model**: immediately, between tool calls, only when idle.
- **Latency**: measured, idle and mid-turn.
- **Target not running**: dropped, or durable and delivered on resume.
- **Ordering** under rapid sends.
- **Caps**: message size, queue depth, burst limits, and the behavior at each.
- **Interrupt interaction**: what an interrupted turn does to pending messages.

## 5. Provenance

The section the skill depends on most.

- **Sender label**: what the receiver is told, verbatim. `none` is a valid and important answer.
- **Reply address**: supplied by the harness, or only by convention in the body?
- **Authority**: does an arriving message carry the operator's authority, or is it marked as
  a peer with reduced rights?
- **Spoofable**: can a sender forge another sender's identity? By what mechanism?
- **Distinguishable from the operator**: can the receiver tell a peer message from its human
  typing the same text?

## 6. Inbound controls

- **Gating**: accept / hold / refuse equivalents, and where they are configured.
- **Hooks or filters** that can drop a message before the model sees it.
- **Default posture** when nothing is configured, including anything that varies by
  permission mode.
- **Turning it off** entirely, sending and receiving separately.

## 7. Loop and abuse safety

- Rate limiting, dedupe, queue caps, and whether a two-agent ping-pong terminates on its own.
- If nothing built in: say so, and state what the skill must add.

## 8. Typing quirks (tmux)

- **Submit key**, and how to send a literal newline without submitting.
- **Reserved leading characters** that open a UI mode instead of entering text.
- **Paste behavior**: bracketed paste support, safe maximum length, `send-keys -l` vs
  `load-buffer` + `paste-buffer`.
- **Racing an active turn**: does typed input queue, interrupt, or get lost?

## 9. Environment

Variables a spawned command can read that matter for messaging — own address, socket path,
auth token, home directory, sandbox indicators. Name each and say what sets it.

## 10. Gaps

What this agent cannot do that others can, what is undocumented, and what the skill must work
around. End with the single sentence a future maintainer most needs to know.

## Evidence

Link each non-obvious claim to the experiment ID in the findings files that established it.
Claims with no experiment ID are marked `(unverified — from source)` when the agent is open
source and the claim comes from reading its code, or `(unverified — from docs)` when it comes
from vendor documentation instead.
