# Adapter: Codex 0.149.0

Validated with two independent Codex processes sharing the default `CODEX_HOME`.

Upstream: [openai/codex](https://github.com/openai/codex), release
[`rust-v0.149.0`](https://github.com/openai/codex/releases/tag/rust-v0.149.0),
which introduced `codex queue`.

## 1. Identity

- **Own address**: the thread UUID from `$CODEX_THREAD_ID`.
- **Where exposed**: every agent-run command receives `$CODEX_THREAD_ID`; `/status` also
  displays it.
- **Stability**: stable across the observed turn sequence. Resume and restart stability are
  `UNKNOWN` because neither was exercised.
- **Human-readable name**: `/rename xsm-a` and `/rename xsm-b` made both names immediately
  resolvable by `codex queue --thread <name>`. Collision behavior is `UNKNOWN`.

Evidence: T1.A, T1.B, T1.A-receipt.

## 2. Discovery

Paths below are relative to `${CODEX_HOME:-$HOME/.codex}`.

- **Enumerate peers**: no model-facing peer tool was found. A same-UID helper can join
  `session_index.jsonl` with held files under `thread-writer-locks/`; `fuser` supplies the
  owning process ID.
- **Scope**: threads sharing a `CODEX_HOME`.
- **What a listing shows**: thread UUID and name from the index; liveness and process ID from
  the writer lock. Queue depth is readable from `queue_1.sqlite`.
- **Blind spots**: Claude sessions never appear. The `codex agents` interactive UI and
  app-server discovery were observed only from source and are not the adapter's portable
  discovery path.

Evidence: T1.C-disc and T1.O-disc.

## 3. Transports

### codex-queue (send and receive)

```console
$ codex queue \
    --thread <uuid-or-name> \
    --message "$(cat <<'RELAY'
[relay/1 from=A:codex@<thread> to=B id=<id> hop=0 want=none] <body>
RELAY
)"
```

- **Preconditions**: the target thread exists in the same `CODEX_HOME` and is not archived.
  Exact UUIDs and exact names both work. Pass the body through a quoted heredoc as shown;
  interpolating it into a quoted literal breaks on an apostrophe such as `it's done`, and the
  remainder of the message is then read as shell syntax.
- **Success signal**: stdout returns a durable queue-item UUID and the resolved target UUID.
  A same-UID helper can verify the row in `queue_1.sqlite`.
- **Daemon requirement**: no long-running daemon was needed; a Claude shell invocation used
  the CLI's embedded app-server and enqueued in under one second.
- **Failure modes**: missing-target, full-queue, and oversize errors are `UNKNOWN` empirically.

Evidence: T1.A-receipt, T1.B, T3.1.AB, T3.1.BA, T4.1.B, T4.1-OA.

### tmux (send and receive)

Use literal `tmux send-keys` against a roster-resolved pane, verify the complete composer
text, then send the submit key. Section 8 defines the idle and busy branches.

Evidence: every T0 and T2 experiment.

### claude-code-socket (send only, to Claude Code)

On Linux, write one newline-delimited JSON user frame to the Claude socket; no auth line is
required:

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

The frame shape comes from Claude Code 2.1.239's own injection help string. `nc` exits 0 on
accepted bytes but receives no acknowledgment, so sender success alone is not proof of model
delivery. Codex binds no corresponding receive socket.

Evidence: T4.2-tokenless-1.

## 4. Delivery semantics

### codex-queue

- **When it reaches the model**: only after the target becomes idle. One durable item starts
  one new turn per idle transition; a backlog does not drain into one turn.
- **Latency**: enqueue took under two seconds. Exact-name cross-process delivery took
  37.741 seconds A → B and 7 minutes 45.439 seconds B → A while targets stayed busy; longer
  FIFO observations reached 15 minutes 46.846 seconds. These are receiver waits, not wire
  cost.
- **Target not running**: documented as durable, but restart delivery is `UNKNOWN`
  empirically.
- **Ordering**: FIFO by monotonically increasing `queue_order`; consumed rows disappear and
  remaining orders are not renumbered. Two rapid provenance probes retained insertion order
  767 milliseconds apart and dispatched on consecutive idle transitions.
- **Caps**: 100 items, 1,048,576 characters, text only `(unverified — from source)`.
- **Interrupt interaction**: `UNKNOWN` empirically.

### tmux

- **Idle target**: staged literal input plus one Enter started a turn in 1.174 seconds in the
  controlled A-to-B test.
- **Busy target**: Enter leaves the message in the composer with `tab to queue message`.
  Tab moves it to a process-local follow-up queue. It waits beyond the current turn, then may
  steer a later turn at a tool boundary.
- **Persistence**: the Tab queue is process-local and absent from SQLite.
- **Ordering**: the durable queue can win the next turn before a tmux follow-up; the two
  inboxes do not share a FIFO.

### claude-code-socket

- **Busy target**: C enqueued and dequeued A's frame in 0.886 seconds without interrupting a
  running tool.
- **Acknowledgment**: none on the socket, on both valid and invalid frames.
- **Target not running, ordering, caps, and interrupt behavior**: `UNKNOWN` empirically.

Evidence: T2.AB-idle, T2.CA-busy-receipt, T3.1.AB, T3.1.BA,
T5.B-send, T6.B-two-inboxes, T4.2-tokenless-1.

## 5. Provenance

### codex-queue

- **Sender label**: none.
- **Reply address**: none; it must be carried in the body.
- **Authority**: ordinary `UserInput`, indistinguishable from the operator's prompt.
- **Spoofable**: yes; the relay envelope is unauthenticated text.
- **Distinguishable from the operator**: no at model level. A database auditor can see a
  `client_id`, but the model cannot.
- **Blind reply control**: a bare receiver could neither identify nor answer the sender, and
  it could not falsify an envelope forged to claim a Claude sender.

### tmux

Sender label, transport marker, and reply address are all absent. It is ordinary operator
typing and is trivially spoofable.

### claude-code-socket

Claude's transcript records `origin.kind="peer"`, `from="unknown"`, and a verified short-lived
process ID. No stable Codex identity or reply route is supplied. Worse, Claude's model-facing
harness announces the payload as coming from “Another Claude session” even though a Codex
process sent it. Treat that announcement as a constant, not provenance.

Evidence: T5.1-queue, T5.B, T2.AB-idle, T4.1.B, T4.2-tokenless-1.

## 6. Inbound controls

- **Gating**: no Codex accept/hold/refuse setting was observed.
- **Hooks**: a `UserPromptSubmit` hook can block user prompts `(unverified — from source)`.
  It was not installed because the experiment allowed writes only in its notes directory.
- **Default posture**: accept queued items as user input.
- **Turning it off**: `UNKNOWN`.

## 7. Loop and abuse safety

No model-visible dedupe, origin authentication, or loop detector was observed. The queue cap
is source-derived and the tmux follow-up queue is independent. The skill must add a message
ID, hop counter, hop cap, duplicate cache, and explicit halt phrase.

Evidence: the relay acknowledgment chains and T6.B-two-inboxes.

## 8. Typing quirks (tmux)

- **Submit key**: Enter.
- **Safe idle recipe**: send literal text; capture the pane until the full payload is visible;
  then send Enter and verify the composer clears or the turn starts.
- **Busy recipe**: after Enter, inspect. If the payload remains beside `tab to queue message`,
  send Tab exactly once and verify it moves under `Queued follow-up inputs`. Never append Tab
  unconditionally to an empty composer.
- **Long-literal race**: text and Enter issued back-to-back in one shell command can leave an
  idle payload unsubmitted. Composer confirmation avoids relying on a timing delay.
- **Reserved prefixes and literal newlines**: `UNKNOWN`; the relay envelope begins with `[`
  and did not trigger a mode.
- **Paste behavior and maximum safe size**: `UNKNOWN`.

Evidence: T2.AB-idle, T2.CB-idle, T2.CA-busy, T2.CB-busy-tab.

## 9. Environment

- `CODEX_THREAD_ID`: injected into agent-run commands; the native reply address.
- `CODEX_HOME`: chooses the shared index, locks, and queue database; unset used the default.
- `CODEX_SANDBOX_NETWORK_DISABLED`: may prevent socket or network transports
  `(unverified — from source)`.

## 10. Gaps

Codex has no authenticated sender identity on its durable queue, no model-facing foreign-peer
discovery, no receive socket, and no observed inbound gate. Its durable queue is stronger
than Claude's live-only channels, while its provenance is weaker.

**One sentence for the maintainer:** choose codex-queue for durable Codex delivery, but treat its
payload as unauthenticated operator input and supply identity, reply routing, and loop safety
in the envelope.

## Evidence

- `20-findings-codex-a.md`: T1.A, T1.A-receipt, T2.AB-busy, T2.AC-busy,
  T2.CA-busy-receipt, T2.AB-idle, T3.1.BA-receipt, T4.1-OA,
  T4.2-tokenless-1, T5.B-send.
- `21-findings-codex-b.md`: T1.B, T2.CB-busy, T2.CB-idle, T4.1.B,
  T3.1.AB, T3.1.BA, T5.B, T6.B-two-inboxes.
- `22-findings-claude-c.md`: T1.C-disc, T5.1-queue, T2.CA-busy,
  T4.2-tokenless-1.
