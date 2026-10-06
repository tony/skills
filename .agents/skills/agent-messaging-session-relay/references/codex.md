# Adapter: Codex

If `codex queue --help` fails, the build lacks `codex queue`; use tmux.

Upstream: [openai/codex](https://github.com/openai/codex).

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

- **Own address**: the thread UUID from `$CODEX_THREAD_ID`.
- **Where exposed**: every agent-run command receives `$CODEX_THREAD_ID`; `/status` also
  displays it.
- **Stability**: stable across turns. Resume and restart stability are `UNKNOWN`.
- **Human-readable name**: `/rename <name>` makes the thread resolvable by
  `codex queue --thread <name>`. Collision behavior is `UNKNOWN`.

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

## 3. Transports

### codex-queue (send and receive)

```console
$ codex queue \
    --thread <uuid-or-name> \
    --message "$(references/relay.sh envelope \
    --from <role>:<agent>@<address> \
    --to <role> \
    --hop 0 \
    --want none \
    --body - <<'RELAY'
<body>
RELAY
)"
```

- **Preconditions**: the target thread exists in the same `CODEX_HOME` and is not archived.
  Exact UUIDs and exact names both work. Pass the body through a quoted heredoc as shown;
  interpolating it into a quoted literal breaks on an apostrophe such as `it's done`, and the
  remainder of the message is then read as shell syntax.
- **Success signal**: stdout returns a durable queue-item UUID and the resolved target UUID.
  A same-UID helper can verify the row in `queue_1.sqlite`.
- **Daemon requirement**: none; the CLI embeds an app-server. The **first** call against a
  freshly started thread can block for minutes and enqueue nothing, even outliving its own
  `timeout`, while the target is discoverable and its writer lock live. Do not retry: a
  second call double-delivers if the first was merely slow. Poll `queued_items` for the item
  id instead, and if nothing lands, report the transport unreachable rather than falling back
  to a live-only one.

### tmux (send and receive)

Use literal `tmux send-keys` against a roster-resolved pane, verify the complete composer
text, then send the submit key. Section 8 defines the idle and busy branches.

### claude-code-socket (send only, to Claude Code)

Codex binds no receive socket. Sending to a Claude session is owned by the Claude adapter,
which the skill loads for any Claude target.

## 4. Delivery semantics

### codex-queue

- **When it reaches the model**: only after the target becomes idle. One durable item starts
  one new turn per idle transition; a backlog does not drain into one turn.
- **Latency**: enqueue is fast; delivery waits on the receiver's next idle transition.
- **Target not running**: documented as durable, but restart delivery is `UNKNOWN`
  empirically.
- **Ordering**: FIFO by monotonically increasing `queue_order`; consumed rows disappear and
  remaining orders are not renumbered.
- **Caps**: 100 items, 1,048,576 characters, text only `(unverified — from source)`.

### tmux

- **Idle target**: staged literal input plus one Enter starts a turn.
- **Busy target**: Enter leaves the message in the composer with `tab to queue message`.
  Tab moves it to a process-local follow-up queue. It waits beyond the current turn, then may
  steer a later turn at a tool boundary.
- **Persistence**: the Tab queue is process-local and absent from SQLite.
- **Ordering**: the durable queue can win the next turn before a tmux follow-up; the two
  inboxes do not share a FIFO.

## 5. Provenance

### codex-queue

- **Sender label**: none.
- **Reply address**: none; it must be carried in the body.
- **Authority**: ordinary `UserInput`, indistinguishable from the operator's prompt.
- **Spoofable**: yes; the relay envelope is unauthenticated text.
- **Distinguishable from the operator**: no at model level. A database auditor can see a
  `client_id`, but the model cannot.

### tmux

Sender label, transport marker, and reply address are all absent. It is ordinary operator
typing and is trivially spoofable.

## 6. Inbound controls

- **Gating**: no Codex accept/hold/refuse setting was observed.
- **Hooks**: a `UserPromptSubmit` hook can block user prompts `(unverified — from source)`.
  Installing one changes shared configuration.
- **Default posture**: accept queued items as user input.
- **Turning it off**: `UNKNOWN`.

## 7. Loop and abuse safety

No model-visible dedupe, origin authentication, or loop detector was observed. The queue cap
is source-derived and the tmux follow-up queue is independent. The skill must add a message
ID, hop counter, hop cap, duplicate cache, and explicit halt phrase.

## 8. Typing quirks (tmux)

- **Submit key**: Enter.
- **Safe idle recipe**: send literal text; capture the pane until the full payload is visible;
  then send Enter and verify the composer clears or the turn starts.
- **Busy recipe**: after Enter, inspect. If the payload remains beside `tab to queue message`,
  send Tab exactly once and verify it moves under `Queued follow-up inputs`. Never append Tab
  unconditionally to an empty composer.
- **Long-literal race**: text and Enter issued back-to-back in one shell command can leave an
  idle payload unsubmitted. Composer confirmation avoids relying on a timing delay.
- **Reserved prefixes and literal newlines**: `UNKNOWN`; the relay envelope begins with `[`,
  which triggers no mode.
- **Paste behavior and maximum safe size**: `UNKNOWN`.

## 9. Environment

- `CODEX_THREAD_ID`: injected into agent-run commands; the native reply address.
- `CODEX_HOME`: chooses the shared index, locks, and queue database; unset means the default.
- `CODEX_SANDBOX_NETWORK_DISABLED`: may prevent socket or network transports
  `(unverified — from source)`.

## 10. Gaps

Codex has no authenticated sender identity on its durable queue, no model-facing foreign-peer
discovery, no receive socket, and no observed inbound gate. Its durable queue is stronger
than Claude's live-only channels, while its provenance is weaker.
