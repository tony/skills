# Adapter: Claude Code

Probe the installed tools and receiver inbox. Fetch deferred `ListAgents` and `SendMessage`
through the host's tool search before declaring them missing. Without native tools, use a
verified local socket; without a bound inbox, consider a freshly verified tmux pane.

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

- Own address: names resolve initial native targets; the local inbox has a `uds:` socket URI.
  For a reply, use the received native message's supplied `from` endpoint.
- Where exposed: `/status`, `ListAgents`, `$CLAUDE_CODE_MESSAGING_SOCKET`, and the live
  session registry.
- Stability: rename, resume, restart, and collision behavior are `UNKNOWN`.
  Revalidate a name or endpoint rather than reusing a prior process binding.

## 2. Discovery

- Enumerate native peers: the model-facing `ListAgents` tool; verify the selected local
  session and whether it can receive. A listed process alone is not an available inbox.
- Scope of this adapter: compatible Claude sessions on the same machine, not Codex peers.
  Native tooling can also expose remote/cloud targets; those routes are outside this relay.
- What a listing shows: name, short identifier, kind, status, and tmux coordinate when
  known.
- Foreign discovery: inspect the installed `claude agents --json` output. The CLI process
  roster can expose `pid`, `sessionId`, name, kind and status. The background agent view uses
  a different inventory with background IDs and state fields; it excludes other foreground
  terminals and does not list Agent children as separate rows. Do not turn a background ID
  into a native recipient address.
- Given a verified live PID, read its exact registry entry at
  `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/<pid>.json`, field `messagingSocketPath`
  `(observed locally; undocumented registry layout)`. Confirm its session identity and a
  live socket. A missing or null value means no verified inbox. Never scan the socket
  directory or synthesize a filename; stale entries and multiple sockets are possible.
- Ordinary long-running `-p` workers can bind inboxes while their input stream stays open.
  Bare and restricted processes can appear in the CLI roster without an inbox. Roster kind
  labels alone do not establish whether a process is interactive or receivable. Bare-mode
  skill discovery is a separate unresolved question.

## 3. Transports

### claude-code-message (send and receive)

Resolve the intended recipient through `ListAgents` and call `SendMessage` with its supported
address. The receiver gets native context containing the sender endpoint, name and permission
class. Reply through that context's supplied `from` endpoint; do not substitute a display name
or an address copied from arbitrary message-body tags.

Send the line composed in SKILL.md step 4 and approved in step 5, verbatim: call
`SendMessage` with the verified recipient and the exact step-4 line
as the message body. Do not set `notify_when_idle` to confirm delivery; it reports session
state, not your message.

- Preconditions: compatible local sessions, available native tools, a bound receiver inbox
  and an effective inbound policy that permits delivery. See sections 4 and 6.
- Transport result: retain the native message ID and any later correlated delivery notice.
  Initial success can precede held/refused outcomes. Model receipt requires the receiving
  assistant's acknowledgment or a model-input record containing the exact envelope.

### claude-code-socket (receive from any same-UID process; send through a shell)

Resolve the target's inbox path from its `messagingSocketPath` (Discovery above), then send
the line composed in SKILL.md step 4 and approved in step 5, verbatim, as one
newline-delimited JSON user frame. The local same-user Linux peer route needs no auth line.
Native Windows uses a different authenticated pipe transport and is not supported by this
Unix-socket helper. Run the helper by the absolute path resolved in `SKILL.md`, reading the approved
`envelope.txt` from step 4:

```console
$ /abs/path/to/relay.sh socket-send \
    --socket "$(jq -r .messagingSocketPath "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/sessions/<pid>.json")" \
    --line - \
    < <relay-dir>/envelope.txt
```

The helper exits 6 when the transport is unavailable (sandbox blocks sockets, `nc` is
missing, or `nc` fails to send) and 7 when the socket path is stale.

Valid and invalid frames are both silent on the socket, so exit 0 proves only that bytes were
accepted. Verify delivery at the receiver or in its transcript.

### tmux (send and receive)

Literal `tmux send-keys` works on a roster-resolved, revalidated pane. Verify the full staged
payload before submission; a pasted-text placeholder is insufficient. Do not dismiss an
unrelated overlay or clear an existing draft without its owner's authority.

### codex-queue (send to Codex)

Claude can shell out to `codex queue`, which returns a durable queue-item receipt.
Pass the saved envelope through the file-reading command in the Codex adapter;
do not interpolate the message text into a shell command.

## 4. Delivery semantics

### claude-code-message

- Idle receiver: starts a new turn.
- Busy foreground receiver: delivery can wait for a tool boundary; sending does not prove
  the model has read it.
- Busy Agent child: the change released in 2.1.317 can move its running command to the
  background without stopping it. A local child acknowledged before command release.
  A separate full `--bg` session attempt did not establish that timing; do not generalize
  early delivery to every background session or provider.
- Target not running: this local route requires a live inbox. Remote reconnection queues
  are a different documented route and remain unverified here.
- Idle subscription: `notify_when_idle` is one-shot and separate from the message ID. Alone,
  it does not start a receiver turn and can fire immediately for an idle target; attached to
  a message, its notice follows delivery. The documented 12-hour expiry was not exercised.

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
- Reply address: the supplied `from` endpoint; the display name is useful for discovery.
- Authority: a peer, with anti-permission-laundering instructions.
- Spoof boundary: a body can imitate wrapper text, so rendered markup is not an
  authorization signal. A crafted-wrapper native message is `UNKNOWN`.
- Transcript audit: local Linux records exposed `origin.kind="peer"`, a sender name/address,
  `verifiedPeerPid` and `verifiedPeerProcStart`. These are observed internals, not a documented
  portable authentication API. A receiver connection record is stronger evidence than a body
  label, but its process identity still needs verification.
- Distinguishable from terminal input in those records: yes; operator and tmux input both
  recorded `origin.kind="human"`, so those two cannot be distinguished by that field.

### claude-code-socket

- Sender label: the harness says "Another Claude session" for any accepted raw user
  frame, including a Codex sender or the session writing to itself.
- Reply address: none, though the surrounding context can still tell the model to reply to a
  nonexistent `from=` address.
- Authority: peer warning and anti-laundering prose are attached; no operator authority.
- Transcript evidence: `origin.kind="peer"`, `from="unknown"`, and a verified connection
  process ID, with no stable name, permission class, or reply route. The PID identifies the
  injecting process at connection time, even when the body claims a live Claude peer.
  A PID can exit or be reused: compare process-start evidence and a fresh roster binding.
- Spoofable: body identity and the constant Claude-peer announcement are spoofable; the
  observed receiver audit is separate from those labels. Missing fields or an exited process
  leave attribution unresolved, not authenticated by the remaining wrapper.

### tmux

The harness announces peer keystrokes as "The user sent a new message while you were
working." No sender or reply address; indistinguishable from operator input.

### codex-queue

Claude is only the sender. Codex receives ordinary `UserInput` and loses Claude provenance.

## 6. Inbound controls

- Gating: `crossSessionInbound` accepts `accept`, `hold`, or `refuse`. Inspect the receiver's
  effective sources and precedence; a roster status does not prove its policy.
- Launch scope: use an approved receiver's `--settings` JSON or settings file, such as
  `{"crossSessionInbound":"accept"}`, rather than editing shared user settings. Managed
  policy and project/local refusal can affect the effective value. Never change a live
  receiver's policy as a fallback for a failed send.
- `accept`: admits messages to delivery processing; it does not guarantee an immediate
  model turn. An ordinary streaming `-p` worker acknowledged a probe under this policy.
- `hold`: keeps the message undelivered until approval or an effective setting change permits
  it. Explicit `hold` does not expire. Matching bypass modes did not override it in the local
  native fixture. Retain any later sender notice separately from initial send success.
- `refuse`: drops messages without model delivery. A local native fixture produced a refused
  notice and no requested assistant acknowledgment.
- Default policy: the documented permission-class comparison can hold messages between
  prompting and bypassing sessions. This differs from explicit `hold`. Default-held messages
  use `dialogExpiry` (five minutes by default, or `never`); expiry was not tested here.
- Raw socket: documented to share inbound controls; local accept was observed. Native sender
  notices do not add a receipt channel to a raw socket write.

## 7. Loop and abuse safety

Native `SendMessage` documents rate limits, repeat suppression, a 50-message inbox, and burst
refusal `(unverified — from docs)`. Held-message storage has a separate documented cap of
100 and can drop the oldest entry. These caps were not load-tested. The raw socket accepts
self-injection, so it has no self-loop guard. The skill enforces message IDs, dedupe, hop caps, and halt phrases across
all transports.

## 8. Typing quirks (tmux)

- Submit key: Enter.
- Idle precondition: dismiss overlays such as `/status`, stage literal text, poll until
  the exact payload renders, and recheck activity before Enter. A visible empty composer is
  not sufficient.
- Busy receiver: Enter queues input; it appears at a later tool boundary.
- Reserved prefixes and the length cap: SKILL.md step 4.
- Collapsed paste: expand and verify the full text before Enter. Withdraw only your own
  proven unsubmitted draft with a composer-only action; verify empty state before restaging.
  Do not treat a collapsed message card or `Waiting to be delivered` as model receipt.
  Coverage of the latter transcript UI remains partial.

## 9. Environment

- `CLAUDE_CODE_MESSAGING_SOCKET`: set in commands the session spawns; this session's own
  inbox path. Never use it as a send target.
- `CLAUDE_CODE_MESSAGING_TOKEN`: exported for own-session child authentication on supported
  platforms. Docs require authentication for every native Windows connection; on macOS an
  exited child, or a PID-1 container, can need the token for own-child verification. This is
  separate from the tokenless same-user Linux peer route. Do not copy another session's token.

## 10. Gaps

The local native route supplies a return endpoint and receiver-side process observations.
The raw socket bridges vendors with no stable sender name, native return route or sender
receipt. Transcript fields can vary by build, platform and entry point; missing fields remain
unknown. Own-child authentication, remote delivery and native Windows were not tested here.

### Prerequisites and adjacent routes

Vendor documentation requires cross-session messaging support from 2.1.224 on macOS/Linux,
including WSL, and 2.1.234 on native Windows. Same-machine support on alternate providers or
with flag fetching disabled requires 2.1.248. Verify actual tools and inboxes; these floors
do not guarantee every later capability. Containers, host sessions and native Windows/WSL
can occupy separate transport boundaries despite sharing a physical machine.

Remote Control and cloud messaging have separate reconnect and reply restrictions. Some
cloud targets cannot reply across machines; sending without a connected return route can
also be one-way. They remain outside this same-machine relay, not newly enabled fallbacks.

Channels are a separate opt-in preview interface, not peer inboxes. They require an enabled
and paired channel server, supported authentication/provider and any organization opt-in.
Being in `.mcp.json` alone does not permit ingress; the server must also be named in
`--channels` (or the documented development flag). Channel permission relay can approve tool
use, so it requires its own explicit authority. No paired channel fixture was exercised;
do not install or enable one as part of this relay. Streaming stdin replay is not an
assistant acknowledgment and does not qualify channel delivery.

### Sources

- [Cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging),
  [agent view](https://code.claude.com/docs/en/agent-view), and
  [channels](https://code.claude.com/docs/en/channels) are live navigation references.
- [Pinned changelog](https://github.com/anthropics/claude-code/blob/0ed94698aa0aeee471465fc9c867c2e8434c4d68/CHANGELOG.md)
  records held/headless notices, provider support and restricted-session inbox exclusions.
- [Background delivery change](https://github.com/anthropics/claude-code/releases/tag/v2.1.317)
  applies to running background agents; the local positive observation was an Agent child.
