# Adapter: Claude Code

Cross-session messaging, `ListAgents`, and the inbox socket need a build that ships them.
If `ListAgents` is not a tool in this session, use the socket or tmux route; if
`claude agents --json` fails, use tmux.

Upstream: [cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging).

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

- Own address: native peers address a session by name; the inbox address is the `uds:`
  socket URI.
- Where exposed: `/status`, `ListAgents`, `$CLAUDE_CODE_MESSAGING_SOCKET`, and the live
  session registry.
- Stability: rename, resume, restart, and collision behavior are `UNKNOWN`.

## 2. Discovery

- Enumerate peers: the model-facing `ListAgents` tool.
- Scope: Claude sessions only; Codex sessions never appear.
- What a listing shows: name, short identifier, kind, status, and tmux coordinate when
  known.
- Foreign discovery: `claude agents --json` lists live sessions with name, pid, and
  status; read the inbox from `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/<pid>.json`,
  field `messagingSocketPath`, rather than assuming a directory. The socket directory alone
  is not enough: it publishes no names, most entries are stale, and one logical session can
  own two.

## 3. Transports

### claude-code-message (send and receive)

The model calls `SendMessage` with a `ListAgents` name. The receiver gets a structured
`<cross-session-message>` wrapper with sender socket, name, and permission class.

- Preconditions: live compatible Claude sessions and the cross-session feature enabled.
- Success signal: the tool returns a message ID; the receiver starts a turn if idle or
  receives it at a tool boundary if busy.

### claude-code-socket (receive from any same-UID process; send through a shell)

Resolve the target's inbox path from its `messagingSocketPath` (Discovery above), then send
the line composed in SKILL.md step 4 and approved in step 5, verbatim, as one
newline-delimited JSON user frame. No auth line is needed on Linux; native Windows
requires `{"type":"auth","token":"..."}` first `(unverified — from docs)`. Run `relay.sh` by the absolute path resolved in `SKILL.md`:

```bash
/path/to/relay.sh socket-send \
    --socket "$(jq -r .messagingSocketPath "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/<pid>.json")" \
    --line - <<'RELAY'
<the exact line from step 4>
RELAY
```

The helper exits 6 when the transport is unavailable (sandbox blocks sockets, `nc` is
missing, or `nc` fails to send) and 7 when the socket path is stale.

Valid and invalid frames are both silent on the socket, so exit 0 proves only that bytes were
accepted. Verify delivery at the receiver or in its transcript.

### tmux (send and receive)

Literal `tmux send-keys` works when a roster resolves the pane. Dismiss a status overlay
before typing at an idle prompt.

### codex-queue (send to Codex)

Claude can shell out to `codex queue`, which returns a durable item receipt and delivers once
the target is idle. Pass the message through a quoted heredoc, never `--message '<text>'`,
which breaks on an apostrophe in the body. The Codex adapter owns the exact command.

## 4. Delivery semantics

### claude-code-message

- Idle receiver: starts a new turn.
- Busy receiver: queues, and enters the active turn at a later tool boundary without
  interrupting the running tool.
- Target not running: live-only `(unverified — from docs)`.

### claude-code-socket

- Busy receiver: the frame is dequeued at a tool boundary.
- Acknowledgment: none. The sender cannot tell a valid frame from a discarded one without
  receiver cooperation.
- Self-targeting: allowed; native `SendMessage` refuses it.

### tmux

- Idle receiver: one Enter submits once the status overlay is dismissed.
- Busy receiver: input queues and surfaces at the next tool boundary; the active tool
  completes unaffected.
- Ordering: one message per tool boundary, in arrival order.

## 5. Provenance

### claude-code-message

- Sender label: the harness supplies `from`, `from-name`, and `from-mode` in the wrapper.
- Reply address: `from-name` for `SendMessage`; the socket URI is also supplied.
- Authority: a peer, with anti-permission-laundering instructions.
- Spoof boundary: a body can imitate wrapper text, so rendered markup is not an
  authorization signal. A crafted-wrapper native message is `UNKNOWN`.
- Transcript audit: delivery records `origin.kind="peer"`, the named sender and address,
  and a kernel-verified process ID, which is stronger than the wrapper.
- Distinguishable from the operator: yes after transcript audit; operator and tmux input
  record `origin.kind="human"`.

### claude-code-socket

- Sender label: the harness says "Another Claude session" for any accepted raw user
  frame, including a Codex sender or the session writing to itself.
- Reply address: none, though the harness still tells the model to reply to a
  nonexistent `from=` address.
- Authority: peer warning and anti-laundering prose are attached; no operator authority.
- Transcript evidence: `origin.kind="peer"`, `from="unknown"`, and a verified connection
  process ID, with no stable name, permission class, or reply route. The PID identifies the
  injecting process even when the body claims a live Claude peer.
- Spoofable: body identity and the constant Claude-peer announcement are spoofable; the
  transcript origin is not sender-controlled.

### tmux

The harness announces peer keystrokes as "The user sent a new message while you were
working." No sender or reply address; indistinguishable from operator input.

### codex-queue

Claude is only the sender. Codex receives ordinary `UserInput` and loses Claude provenance.

## 6. Inbound controls

- Gating: `crossSessionInbound` accepts `accept`, `hold`, or `refuse`.
- Default posture: permission-class comparison `(unverified — from docs)`.
- Socket interaction: an explicit `accept` admits an unnamed tokenless sender; behavior
  under `hold` and `refuse` is `UNKNOWN`. Testing either changes user-scope settings, so use
  an isolated receiver.

## 7. Loop and abuse safety

Native `SendMessage` documents rate limits, repeat suppression, a 50-message inbox, and burst
refusal `(unverified — from docs)`. The raw socket accepts self-injection, so it has no
self-loop guard. The skill enforces message IDs, dedupe, hop caps, and halt phrases across
all transports.

## 8. Typing quirks (tmux)

- Submit key: Enter.
- Idle precondition: dismiss overlays such as `/status`, stage literal text, poll until
  the exact payload renders, and recheck activity before Enter. A visible empty composer is
  not sufficient.
- Busy receiver: Enter queues input; it appears at a later tool boundary.
- Reserved prefixes and the length cap: SKILL.md step 4.

## 9. Environment

- `CLAUDE_CODE_MESSAGING_SOCKET`: set in commands the session spawns; this session's own
  inbox path. Never use it as a send target.
- `CLAUDE_CODE_MESSAGING_TOKEN`: set in spawned commands; needed only for the Windows auth
  line.

## 10. Gaps

Native messaging has named, kernel-auditable provenance but is Claude-only and live-only.
The raw socket bridges vendors and is process-auditable, but has no stable session identity,
reply address, acknowledgment, or truthful vendor label. Foreign discovery exposes socket
PIDs without the names native messaging requires.
