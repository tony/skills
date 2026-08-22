# agent-messaging

Message another running coding-agent session — Claude Code or Codex — on
this machine, and verify who actually sent an incoming message.

## Requirements

Both sessions run on the same machine under the same user; every route is
local, and the socket route trusts that boundary. The `codex-queue` route
needs Codex 0.149 or newer, the release that added `codex queue`; the
trial ran on 0.149.0.

## Installation

In Claude Code, add the marketplace:

```console
/plugin marketplace add tony/skills
```

Install the plugin:

```console
/plugin install agent-messaging@skills
```

In Codex, add the marketplace:

```console
codex plugin marketplace add tony/skills
```

Install the plugin:

```console
codex plugin add agent-messaging@skills
```

## Skills

| Claude Code | Codex | Description |
|---|---|---|
| `/agent-messaging:session-relay` | `agent-messaging:session-relay` | Find reachable sessions, pick a transport, deliver through a safe state machine, confirm arrival, and verify sender identity. |

## Transports

Ranked per sender and receiver, not hardcoded per vendor.

- **`SendMessage`** — Claude Code to Claude Code. The only route that
  carries a sender name and a reply address in-band.
- **`codex queue`** — anything to Codex. Durable, so it survives a target
  that is not running, and externally auditable from its SQLite queue.
- **Inbox socket** — anything to Claude Code. One newline-delimited JSON
  frame, tokenless within the same operating-system user.
- **`tmux send-keys`** — universal fallback. Indistinguishable from the
  operator typing.

## Adapters

Per-agent behavior lives in `references/agents/<agent>.md`, covering
identity, discovery, delivery semantics, provenance, inbound controls, and
typing quirks. Adding an agent means writing one adapter, not editing the
skill — if the skill needs changing, the adapter boundary is wrong.

`references/agents/_template.md` is the contract. `UNKNOWN` is a valid
answer and is preferred over an inferred one.

## Evidence

Four sessions — two Codex, two Claude Code — messaging each other across
four transports on one machine. Every claim in the skill traces to a
numbered experiment in [`notes/`](notes/): the transport matrix in
[`30-matrix.md`](notes/30-matrix.md), the full design spec in
[`40-skill-design.md`](notes/40-skill-design.md), and each session's
raw findings alongside them.

These are a record, not instructions. They sit outside `references/` so
the skill never loads them and no export check ever rewrites them.

Three results worth knowing before using any of it:

- Provenance comes from the transcript `origin` record, never from the
  rendered wrapper or the "Another Claude session sent a message"
  announcement, which fires even for a Codex process.
  `origin.verifiedPeerPid` is kernel-supplied; the wrapper is not.
- `tmux send-keys` into a busy Codex pane parks the payload unsubmitted.
  `send-keys` exits 0 and the text is visible, so exit status is not
  delivery.
- Measured latency ran from 0.886s over the socket to 7m45s for a queued
  message behind a busy receiver — bounded by the receiver's idle
  transition, not by the transport.

Untested areas are listed rather than inferred: cap failures, restart
behavior, inbound `hold`/`refuse`, and name-collision stability.

## Upstream

- Claude Code — [cross-session messaging][ccm]
- Codex — [repository][codex], [`rust-v0.149.0`][codex-149], the release
  that introduced `codex queue`

[ccm]: https://code.claude.com/docs/en/cross-session-messaging
[codex]: https://github.com/openai/codex
[codex-149]: https://github.com/openai/codex/releases/tag/rust-v0.149.0
