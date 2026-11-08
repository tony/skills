# agent-messaging

Message another running coding-agent session (Claude Code or Codex) on
this machine, and verify who actually sent an incoming message.

## Prerequisites

Both sessions run on the same machine under the same user; every route is
local, and the socket route trusts that boundary. Reaching a Claude session
needs the `claude` CLI on PATH, and reaching a Codex thread needs it to
share your `CODEX_HOME`; a thread under a different one is invisible, not
merely unreachable. The `codex-queue` route needs a Codex build that ships
`codex queue`; check with `codex queue --help`.

Tools: `jq` (envelope audit and socket frames), `python3` 3.14 or newer only to run the
tests, and per route: `nc` for the inbox socket, `tmux` for the typing fallback, and the
`sqlite3` CLI to read back a Codex queue item (optional; delivery is then reported
unconfirmed).

## Installation

From a shell, one command installs the plugin for Claude Code and
adds the marketplace first if it is missing:

```console
$ claude plugin install agent-messaging --marketplace tony/skills
```

Inside a Claude Code session, add the marketplace:

```text
/plugin marketplace add tony/skills
```

Install the plugin:

```text
/plugin install agent-messaging@skills
```

In Codex, add the marketplace:

```console
$ codex plugin marketplace add tony/skills
```

Install the plugin:

```console
$ codex plugin add agent-messaging@skills
```

Claude Code uses a leading slash (`/agent-messaging:…`). Codex omits it (`agent-messaging:…`).

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

- `SendMessage`: Claude Code to Claude Code. The only route that
  carries a sender name and a reply address in-band.
- `codex queue`: anything to Codex. Durable, so it survives a target
  that is not running, and externally auditable from its SQLite queue.
- Inbox socket: anything to Claude Code. One newline-delimited JSON
  frame, tokenless within the same operating-system user.
- `tmux send-keys`: universal fallback. Indistinguishable from the
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
`origin` records, and the session registry layout. A release of either CLI can change them, so the skill probes each route at run time
before choosing it:

- `codex queue --help` must exit 0 for the `codex-queue` route.
- `claude agents --json` must succeed for the inbox-socket route.
- `ListAgents` must exist as a tool for the native `SendMessage` route.

A failed probe drops that route and the skill falls back to the next one in its ranking,
ending at `tmux send-keys`. Delivery is then confirmed from receiver evidence, never from
the probe.

## Upstream

- Claude Code — [cross-session messaging][ccm]
- Codex — [repository][codex]

[ccm]: https://code.claude.com/docs/en/cross-session-messaging
[codex]: https://github.com/openai/codex
