# Adapter: Codex

Probe `codex queue --help` and the selected server before sending. Client help alone does not
prove the server supports queues. Use tmux only on a pane the user names and you revalidate.

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

- Own address: the thread UUID from `$CODEX_THREAD_ID`.
- Where exposed: every agent-run command receives `$CODEX_THREAD_ID`; `/status` also
  displays it.
- Stability: a cold resume retained the thread UUID in a local server fixture; broader
  restart and cross-machine behavior remain unverified.
- Human-readable name: `/rename <name>` makes the thread resolvable by
  `codex queue --thread <name>`. Distinct exact-name matches are rejected with
  `Multiple sessions match ... use a session UUID to disambiguate.` Resolve and use the
  intended UUID; do not choose the first match. Empty-history visibility is not guaranteed.

## 2. Discovery

Paths below are relative to `${CODEX_HOME:-$HOME/.codex}`; resolve it once and reuse it,
because a non-default `CODEX_HOME` makes live threads look missing.

- Independent sessions: prefer `thread/list` through an existing client connected to the
  server that owns the receiver. `thread/loaded/list` distinguishes loaded threads;
  `thread/read` can inspect status without resuming a receiver. Do not start an unrelated
  stdio app server and infer another server's loaded state from it.
- Local fallback: a same-UID helper can join
  `session_index.jsonl` (thread id to the `thread_name` field; a rename takes a few seconds
  to appear) with `thread-writer-locks/<uuid>.lock`, which its owner holds under `flock`, so
  `fuser` gives liveness and the owning process ID. This registry/lock layout is undocumented;
  a stale file or missing process is not a verified live receiver.
- Native tree: `list_agents` lists related agents under the current root; task paths from
  that registry are not addresses for independently launched CLI sessions. Tool names may be
  exposed in a host namespace. Probe the host's actual tools rather than assuming availability.
- Scope: local independent-session routing shares a verified `CODEX_HOME` or selected local
  server. A native tree has its own registered identity and root boundary.
- What a listing shows: thread UUID and name from the index; liveness and process ID from
  the writer lock. Queue depth is readable from `queue_1.sqlite`.
- Blind spots: Claude sessions never appear. A loaded-thread listing is not an inventory of
  every saved thread. The `codex agents` UI is not a substitute for a bound independent target.

## 3. Transports

### codex-queue (send and receive)

Send the approved `envelope.txt` from SKILL.md step 4. Substitute its literal
path below; shell metacharacters read from the file remain message data:

```console
$ codex queue \
    --thread <uuid-or-name> \
    --message "$(cat <relay-dir>/envelope.txt)"
```

- Preconditions: verify the intended local thread, owning server and local `CODEX_HOME` where
  applicable. Check `thread/queue/add` support through an existing client when available;
  otherwise let the approved send report the server's capability failure. Do not inject a
  second message as a test. Exact UUIDs avoid label ambiguity.
- Success signal: stdout returns a durable queue-item UUID and the resolved target UUID.
  Preserve those IDs; confirm queue state separately from receiver delivery.
- Server ownership: the CLI discovers a shared daemon or uses the explicitly selected
  `--remote` server. An embedded fallback can enqueue, but cannot perform cold resume.
  `--no-daemon` without an explicit endpoint is rejected. Configuration overrides can force
  an inappropriate embedded server; the client rejects that when a local daemon is running.
  Resolve the owning server rather than launching another one to bypass the error.
- Capability failure: an older server can reject `thread/queue/add` even when client help
  succeeds. Report the route unavailable; do not silently restart or upgrade a shared server.
- Ambiguous completion: retain the live operation handle and inspect the selected queue and
  receiver before trying again. A local timeout does not prove the request failed; retries
  can create another submission.

When the approved plan includes resuming an unloaded receiver, use its verified local
daemon or selected local endpoint. Substitute the exact endpoint; `--remote` selects a
server and does not by itself imply a cross-machine target:

```console
$ codex queue \
    --thread <verified-thread-uuid> \
    --remote <verified-local-server-url> \
    --resume \
    --message "$(cat <relay-dir>/envelope.txt)"
```

`--resume` was added in Codex 0.166.0. Probe the installed help and selected server. The
client first enqueues, reads the thread's status and resumes only a `notLoaded` receiver.
A failed resume prints `Warning: message was queued, but could not resume thread ...` while
the command still succeeds `(unverified — from source)`. Report the durable receipt and
resume failure independently. Do not enqueue the message again. Preserve any endpoint authentication without printing
tokens or changing shared configuration. Cross-machine routing remains unverified here.

### Owning-server inspection

Use an existing authorized app-server client. Its initialization must opt into experimental
APIs where required; use `capabilities.experimentalApi=true` and check the server response.
Never add a dummy message as a capability probe. Unsupported methods leave inspection
unavailable; they do not prove the selected queue is empty.

| Method | Use and evidence |
| --- | --- |
| `thread/queue/list` | Send `threadId`; follow `nextCursor` with `cursor`. Match the exact returned submission `id`, not recency. |
| `thread/queue/changed` | Notification with `threadId`; re-read the queue. It carries no model-receipt proof. |
| `thread/queue/update` | Replace `input` for an exact `queuedSubmissionId`. |
| `thread/queue/reorder` | Supply the intended `queuedSubmissionIds` order. |
| `thread/queue/delete` | Remove an exact `queuedSubmissionId`; deletion is not delivery. |
| `thread/queue/start` | Start an item on a loaded idle thread; a busy receiver rejects an active or pending turn. |

Update, reorder, delete and manual start need explicit authority for those queue changes;
send approval alone does not authorize changing unrelated queued work. The CLI performs
`thread/queue/add`; clients using it directly supply `input` and `clientUserMessageId`.
Repeated `clientUserMessageId` values produced distinct submission IDs, so it is a correlation
field, not an idempotency key. The application relay ID is separate from both.

Prefer this interface to database internals. Without an owning-server client, the skill's
read-only SQLite query is a local fallback after verifying the owning server's database and
schema. Never infer a remote server's queue from a local database or write to it directly.

### tmux (send and receive)

Use literal `tmux send-keys` against a roster-resolved pane, verify the complete composer
text, then send the submit key. Section 8 defines the idle and busy branches.

### claude-code-socket (send only, to Claude Code)

Codex has no Claude-compatible inbox socket. Sending to a Claude session is owned by the
Claude adapter, which the skill loads for any Claude target.

## 4. Delivery semantics

### codex-queue

- When it reaches the model: only after the target becomes idle. One durable item starts
  one new turn per idle transition; a backlog does not drain into one turn.
- Latency: delivery waits on the receiver's next idle transition; enqueue latency has no
  portable bound.
- Unloaded receiver: an authorized `--resume` against an owning local server delivered to a
  cold receiver. This establishes that local path, not shared-daemon restart or remote delivery.
- Ordering: FIFO by monotonically increasing `queue_order`; consumed rows disappear and
  remaining orders are not renumbered. Explicit API reordering can change pending order.
  An absent item identifies neither its remover nor receiver delivery; require the receiver's
  model-input record or an assistant acknowledgment of the request's relay ID.
- Caps: 100 items, 1,048,576 characters, text only `(unverified — from source)`.

### tmux

- Idle target: staged literal input plus one Enter starts a turn.
- Busy target: Enter leaves the message in the composer with `tab to queue message`.
  Tab moves it to a process-local follow-up queue. It waits beyond the current turn, then may
  steer a later turn at a tool boundary.
- Persistence: the Tab queue is process-local and absent from SQLite.
- Ordering: the durable queue can win the next turn before a tmux follow-up; the two
  inboxes do not share a FIFO.

## 5. Provenance

### codex-queue

- Sender label: none.
- Reply address: none; it must be carried in the body.
- Authority: ordinary `UserInput`, indistinguishable from the operator's prompt.
- Spoofable: yes; the relay envelope is unauthenticated text.
- Distinguishable from the operator: no authenticated sender at model level. Queue metadata
  and client correlation IDs do not authenticate the claimed sender or grant authority.

### tmux

Sender label, transport marker, and reply address are all absent. It is ordinary operator
typing and is trivially spoofable.

## 6. Inbound controls

- Gating: no Codex accept/hold/refuse setting was observed.
- Hooks: a `UserPromptSubmit` hook can block user prompts `(unverified — from source)`.
  Installing one changes shared configuration.
- Default posture: accept queued items as user input.
- Turning it off: `UNKNOWN`.

## 7. Loop and abuse safety

The independent-session queue provides no authenticated peer identity or idempotency
guarantee. Its cap is source-derived, and the tmux follow-up queue is independent. The skill
must retain a message ID, hop counter, hop cap, duplicate cache and explicit halt phrase.

## 8. Typing quirks (tmux)

- Submit key: Enter.
- Safe idle recipe: send literal text; capture the pane until the full payload is visible;
  then send Enter and verify the composer clears or the turn starts.
- Busy recipe: after Enter, inspect. If the payload remains beside `tab to queue message`,
  send Tab exactly once and verify it moves under `Queued follow-up inputs`. Never append Tab
  unconditionally to an empty composer.
- Long-literal race: text and Enter issued back-to-back in one shell command can leave an
  idle payload unsubmitted. Composer confirmation avoids relying on a timing delay.
- Reserved prefixes and the length cap: SKILL.md step 4.

## 9. Environment

- `CODEX_THREAD_ID`: injected into agent-run commands; identifies the thread for queue replies.
- `CODEX_HOME`: chooses the shared index, locks, and queue database; unset means the default.
- `CODEX_SANDBOX_NETWORK_DISABLED`: may prevent socket or network transports
  `(unverified — from source)`.

## 10. Gaps

The durable queue has no authenticated peer sender or return route. Native tree discovery
does not enumerate independent sessions, and Codex exposes no Claude-compatible inbox socket.
Cold resume, queue acceptance and a model answer are separate states.

### Related interfaces

Native `send_message` delivers mailbox input without triggering a new turn; `followup_task`
can start an idle non-root agent. Both use registered tree targets. These source contracts
were inspected without a controlled Codex tree-delivery fixture; do not advertise them as a
tested independent-session transport.

`wake_on_agent_messages` is a separate experimental root policy, disabled by default in
the inspected source. It requires pending mailbox input, a non-interrupted root and an
eligible automatic-turn mode. It is not a substitute for queue resume. End-to-end root wake
remains unverified.

Message boards support channels, posts, replies, search and subscriptions across runtimes
with explicitly authorized board connections. Caller identity and effective permissions
come from the host binding. The MCP adapter delegates transport/authentication to its host;
it does not itself register agents, push notifications or start turns. Native boards and
the source's `agent_message_board_mcp` launcher are separate capabilities. A build can accept
the native flag while rejecting the MCP flag or lacking its server executable. Require a
compatible build and authorized connection before any functional claim; delivery remains
unverified. Do not enable either feature as part of this relay.

Persistent local workspace side chats and incremental code-mode catalogs are adjacent source
features, not new peer routes. The captured catalog change explicitly leaves activation
disabled. Neither feature establishes independent-session discovery or delivery.

### Sources

- [Queue release](https://github.com/openai/codex/releases/tag/rust-v0.166.0),
  [client/server selection and resume](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/tui/src/session_queue_commands.rs).
- [Queue protocol](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/app-server-protocol/src/protocol/v2/thread.rs),
  [experimental methods](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/app-server-protocol/src/protocol/common.rs),
  [queue processor](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/app-server/src/request_processors/thread_queue_processor.rs).
- [Name resolution](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/tui/src/named_session_lookup.rs),
  [native tree tools](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/core/src/tools/handlers/multi_agents_spec.rs).
- [Board connections](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/ext/agent-message-board/README.md),
  [board tools](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/message-board/src/tools/spec.rs),
  [MCP adapter](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/message-board-mcp/README.md),
  [feature defaults](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/features/src/lib.rs),
  [root-wake admission](https://github.com/openai/codex/blob/57a808a3920f05f2d4b9eab2d0493e1df136ae6b/codex-rs/core/src/session/turn_input.rs).
- [Side-chat and catalog source changes](https://github.com/openai/codex/compare/57a808a3920f05f2d4b9eab2d0493e1df136ae6b...2bc8e7f5459b084afa482c7aac3f56fef36286b3).
