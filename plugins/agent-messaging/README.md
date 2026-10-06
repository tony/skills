# agent-messaging

Message another running coding-agent session — Claude Code or Codex — on
this machine, and verify who actually sent an incoming message.

## Requirements

Both sessions run on the same machine under the same user; every route is
local, and the socket route trusts that boundary. Reaching a Claude session
needs the `claude` CLI on PATH, and reaching a Codex thread needs it to
share your `CODEX_HOME` — a thread under a different one is invisible, not
merely unreachable. The `codex-queue` route needs a Codex build that ships
`codex queue`; check with `codex queue --help`.

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

`session-relay` finds reachable sessions, picks a transport, delivers through a safe state
machine, confirms arrival, and verifies sender identity. Invoke it as
`/agent-messaging:session-relay` in Claude Code or `agent-messaging:session-relay` in Codex.

## Helper script

`scripts/relay.sh` composes the one-line envelope (header encoding, unique id, hop cap, body
limit), sends a frame to a Claude inbox socket, and audits a transcript for the origin of a
relay id. It needs `jq` and runs on GNU and BSD/Darwin. Run `scripts/relay.sh selftest` to
check it.

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

## Support

The plugin relies on undocumented internals: the `queue_1.sqlite` schema, transcript
`origin` records, and the session registry layout. A release of either CLI can change them,
so the skill checks each route at run time (`codex queue --help`, `claude agents --json`)
instead of assuming a version.

## Upstream

- Claude Code — [cross-session messaging][ccm]
- Codex — [repository][codex]

[ccm]: https://code.claude.com/docs/en/cross-session-messaging
[codex]: https://github.com/openai/codex
