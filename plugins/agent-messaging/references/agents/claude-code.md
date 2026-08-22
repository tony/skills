# Adapter: Claude Code 2.1.239

Validated with one Claude pane and one external native Claude peer.

Upstream: [cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging).

## 1. Identity

- **Own address**: native peers address the session by name; the local inbox address is the
  `uds:` socket URI.
- **Where exposed**: `/status`, `ListAgents`, `$CLAUDE_CODE_MESSAGING_SOCKET`, and the live
  session registry.
- **Stability**: the observed name and socket stayed stable. Rename, resume, restart, and
  collision behavior are `UNKNOWN` empirically.
- **Human-readable name**: C used `commit these changes (Branch 2)`; O used `codex-66`.

Evidence: Phase 1 in role C's findings and T3.2.

## 2. Discovery

- **Enumerate peers**: the model-facing `ListAgents` tool.
- **Scope**: Claude sessions only; it did not list either live Codex pane.
- **What a listing shows**: name, short identifier, kind, status, and tmux coordinate when
  known.
- **Foreign discovery**: `claude agents --json` lists live sessions with name, pid, and
  status; read the inbox from `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/<pid>.json`,
  field `messagingSocketPath`, rather than assuming a directory. The socket directory alone
  is not enough — it publishes no names, seven of twelve observed sockets were stale, and one
  logical session owned two.

Evidence: T1.C-disc and T1.O-disc.

## 3. Transports

### claude-code-message (send and receive)

The model calls `SendMessage` with a `ListAgents` name. The native receiver gets a structured
`<cross-session-message>` wrapper with sender socket, name, and permission class.

- **Preconditions**: live compatible Claude sessions and the cross-session feature enabled.
- **Success signal**: the tool returns a message ID; the receiver starts a turn if idle or
  receives it at a tool boundary if busy.
- **Failure modes**: feature, provider, and version gates were not varied and remain `UNKNOWN`
  empirically.

Evidence: T3.2 and T3.2-recv.

### claude-code-socket (receive from any same-UID process; send through a shell)

On Linux, the accepted newline-delimited frame is:

```json
{"type":"user","message":{"role":"user","content":"hello"}}
```

It can be sent tokenless:

```console
$ jq -nc \
    --arg content '<message>' \
    '{type:"user",message:{role:"user",content:$content}}' \
  | nc \
      -U \
      -N \
      -w 3 \
      "$CLAUDE_PEER_SOCKET"
```

The frame comes from Claude Code's own installed injection help string. A first auth line
`{"type":"auth","token":"..."}` is optional on Linux and required on native Windows
`(Windows requirement unverified — from docs)`.

Both valid and invalid frames are silent on the socket. Verify delivery at the receiver or
in its transcript; exit 0 proves only that bytes were accepted.

Evidence: T4.2-tokenless-1 and C's independent self-injection replication.

### tmux (send and receive)

Standard literal `tmux send-keys` works when a roster resolves the pane. A status overlay must
be dismissed before typing at an idle prompt.

Evidence: T0.C, T2.BC-busy, T2.AC-busy-r1.

### codex-queue (send to Codex)

Claude can shell out to `codex queue`. Under C and O's bypass modes this required no prompt,
returned a durable item receipt, and delivered after the Codex target became idle.

Evidence: T4.1 and T4.1-OA.

## 4. Delivery semantics

### claude-code-message

- **Idle receiver**: starts a new turn.
- **Busy receiver**: queues and enters the active turn at a later tool boundary without
  interrupting the running tool.
- **Target not running**: live-only `(unverified — from docs)`.
- **Ordering, caps, and interrupt behavior**: `UNKNOWN` empirically.

### claude-code-socket

- **Busy receiver**: A's message enqueued and dequeued in 0.886 seconds; C's self-injection
  drained in 2.3 seconds at a tool boundary.
- **Acknowledgment**: none. The sender cannot distinguish a valid frame from a discarded one
  without receiver cooperation.
- **Self-targeting**: allowed; native `SendMessage` refuses it.
- **Target not running, rapid-send ordering, and caps**: `UNKNOWN` empirically.

### tmux

- **Idle receiver**: one Enter submitted T0.C after the status overlay was dismissed.
- **Busy receiver**: input queued and surfaced inside the running turn at the next tool
  boundary; the active tool completed unaffected.
- **Ordering**: B's message arrived before A's later message, one per tool boundary.

Evidence: T3.2, T4.2-tokenless-1, T0.C, T2.BC-busy, T2.AC-busy-r1.

## 5. Provenance

### claude-code-message

- **Sender label**: the harness supplies `from`, `from-name`, and `from-mode` in a
  `<cross-session-message>` wrapper.
- **Reply address**: `from-name` for `SendMessage`; the socket URI is also supplied.
- **Authority**: explicitly a peer with anti-permission-laundering instructions.
- **Model-visible spoof boundary**: the body can imitate wrapper text, so rendered markup is
  not an authorization signal by itself. An exact crafted-wrapper native-message control is
  `UNKNOWN`; the tested raw-socket spoof arrived wrapperless.
- **Transcript audit**: native delivery records `origin.kind="peer"`, the named sender and
  address, and a kernel-verified process ID. This is stronger than the rendered wrapper.
- **Distinguishable from the operator**: yes after transcript audit; operator and tmux input
  record `origin.kind="human"`.

### claude-code-socket

- **Sender label**: the model-facing harness falsely says “Another Claude session” for any
  accepted raw user frame, including a Codex sender and C writing to itself.
- **Reply address**: none. The harness still tells the model to reply to a nonexistent
  `from=` address.
- **Authority**: peer warning and anti-laundering prose are attached, but they do not grant
  operator authority.
- **Transcript evidence**: `origin.kind="peer"`, `from="unknown"`, and a verified connection
  process ID; no stable name, permission class, or reply route. The kernel-backed PID detects
  the injecting process even when the body claims a live Claude peer.
- **Spoofable**: body identity and the constant Claude-peer announcement are spoofable. The
  transcript origin is not sender-controlled and exposed every tested injector as anonymous.
- **Distinguishable from the operator**: yes after transcript audit, but the model prompt has
  no stable sender identity or unassisted reply route.

### tmux

The harness announces peer keystrokes as “The user sent a new message while you were
working.” It supplies no sender or reply address and is indistinguishable from operator input.

### codex-queue

Claude is only the sender. Codex receives ordinary `UserInput` and loses Claude provenance.

Evidence: T3.2, T3.2-recv, T4.2-tokenless-1, T5.3, T6-origin,
T2.BC-busy, T4.1.B.

## 6. Inbound controls

- **Gating**: `crossSessionInbound` accepts `accept`, `hold`, or `refuse`. C explicitly used
  `accept`.
- **Default posture**: permission-class comparison `(unverified — from docs)`.
- **Isolated hold/refuse test**: not executed because changing user scope would affect
  unrelated sessions; use an isolated receiver with per-session settings if authorized.
- **claude-code-socket interaction**: C's explicit `accept` admitted an unnamed tokenless
  sender. Behavior under `hold` and `refuse` is `UNKNOWN` empirically.

Evidence: C Phase 1, standing T7.1 conflict, T4.2-tokenless-1.

## 7. Loop and abuse safety

Native `SendMessage` documents rate limits, repeat suppression, a 50-message inbox, and burst
refusal `(unverified — from docs)`. The raw socket accepted self-injection, so no self-loop
guard exists at that layer. The skill must enforce message IDs, dedupe, hop caps, and halt phrases
across all transports rather than trusting native controls.

## 8. Typing quirks (tmux)

- **Submit key**: Enter.
- **Idle precondition**: dismiss overlays such as `/status`, stage literal text, verify it,
  then submit. A visible empty composer is not sufficient: check activity, stage, poll until
  the exact payload renders, and recheck activity before Enter.
- **Busy receiver**: Enter queues input; it appears at a later tool boundary without
  interrupting the active tool.
- **Reserved prefixes**: `/`, `!`, `#`, and `@` are documented UI prefixes but were not
  empirically varied. The relay envelope begins with `[` and was safe.
- **Literal newline, paste limits, and maximum safe size**: `UNKNOWN`.

Evidence: T0.C, T2.BC-busy, T2.AC-busy-r1, T2.AC-idle-attempt1.

## 9. Environment

- `CLAUDE_CODE_MESSAGING_SOCKET`: set in commands spawned by the session; the inbox path.
- `CLAUDE_CODE_MESSAGING_TOKEN`: set in spawned commands; 32 characters in the observed
  session. Neither variable appeared in the long-running Claude process environment.
- `CODEX_COMPANION_TRANSCRIPT_PATH`: exposed C's active transcript path during the study.

Evidence: T4.2 token-acquisition notes and T4.2-tokenless-1.

## 10. Gaps

Native messaging has named, kernel-auditable provenance but is Claude-only and live-only.
The raw socket bridges vendors and is process-auditable, but has no stable session
identity, reply address, acknowledgment, or truthful vendor label. Foreign discovery exposes socket
PIDs without the names native messaging requires.

**One sentence for the maintainer:** audit transcript `origin` for peer class and verified
process identity; never authorize work from wrapper text or the generic peer announcement,
and treat raw socket input as anonymous, silent, and mislabeled in-band.

## Evidence

- `22-findings-claude-c.md`: Phase 1, T1.C-disc, T0.C, T2.BC-busy,
  T2.AC-busy-r1, T2.AC-idle-attempt1, T3.2, T3.2-recv, T4.1,
  T4.2-tokenless-1, T5.3, T6-origin.
- `23-findings-claude-o.md`: T1.O-disc and T3.2; its earlier T4.2 negative is
  superseded by T4.2-tokenless-1.
- `20-findings-codex-a.md`: T4.1-OA and T4.2-tokenless-1.
