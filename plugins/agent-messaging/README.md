# agent-messaging

Message a Claude Code session or Codex thread on this machine, verify delivery,
and inspect the recorded origin of an incoming message.

## Prerequisites

Both sessions run on the same machine under the same user; every route is
local, and the socket route trusts that boundary. Reaching a Claude session
needs the `claude` CLI on PATH and a verified receiver inbox. Bare/restricted
processes can appear in a roster without an inbox. Local Codex routing needs
the receiver's owning server and, where applicable, its `CODEX_HOME`; choosing
another home or server can make the intended thread invisible. Probe both
`codex queue --help` and the selected server's queue capabilities. Cold resume
also needs an owning daemon or selected local endpoint and explicit authority
to start the receiver.

Tools: `jq` (envelope audit and socket frames), `python3` 3.14 or newer only to run the
tests, and per route: `nc` for the inbox socket, `tmux` for the typing fallback, and the
`sqlite3` CLI as a fallback when an existing owning-server client cannot inspect the queue.
Neither a queue receipt nor queue disappearance proves model delivery.

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

`session-relay` finds reachable sessions, picks a transport, delivers through a state
machine, and distinguishes transport acceptance from receiver evidence. Invoke it as
`/agent-messaging:session-relay` in Claude Code or `agent-messaging:session-relay` in Codex.

## Helper script

`scripts/relay.sh` composes the one-line envelope (header encoding, unique id, hop cap, body
limit), sends a frame to a Claude inbox socket, and audits a transcript for the origin of a
relay id. It needs `jq` and runs on GNU and BSD/Darwin. Run `scripts/relay.sh selftest` to
check it.

## Transports

Ranked per sender and receiver, not hardcoded per vendor.

- `SendMessage`: Claude Code to Claude Code. Carries a sender name and return endpoint.
  Later policy notices and an idle notice are separate from an assistant acknowledgment.
- `codex queue`: anything to Codex. Returns a durable submission ID. Optional `--resume`
  can load an authorized receiver; a resume warning can accompany a successful enqueue.
  Prefer owning-server queue inspection, with a verified read-only SQLite fallback.
- Inbox socket: a same-user process to a compatible Claude Code session on macOS/Linux,
  including WSL. One newline-delimited JSON frame; native Windows pipes are a separate route.
- `tmux send-keys`: universal fallback. Indistinguishable from the
  operator typing.

Replies receive fresh envelope IDs and identify the request in their bodies. Native Claude
replies use the supplied return endpoint; a Codex queue or raw socket needs an explicit
return route. Message IDs, hop limits and halt behavior remain application controls across
all routes.

## Adapters

Per-agent behavior lives in `references/agents/<agent>.md`, covering
identity, discovery, delivery semantics, provenance, inbound controls, and
typing quirks. Adding an agent means writing one adapter, not editing the
skill's transport procedure. Native Codex tree tools do not enumerate independent CLI
sessions. Boards/MCP, automatic root wake and Claude channels need separate configured
fixtures; the adapters document their prerequisites without enabling them.

`references/agents/_template.md` is the contract. `UNKNOWN` is a valid
answer and is preferred over an inferred one.

## Support

The preferred Codex inspection interface is experimental. Its database fallback, Claude's
transcript `origin` records and the session registry layout are undocumented internals.
Probe the actual client, owning server and receiver before choosing a route:

- `codex queue --help` must expose the requested options, and the selected server must
  support `thread/queue/add`; cold resume has an additional owning-server requirement.
- `claude agents --json` must identify the intended live process, whose exact registry
  entry must advertise a live inbox for the socket route.
- Fetch deferred `ListAgents` and `SendMessage` tools before testing native availability;
  verify the recipient's effective inbound policy.

A failed probe rules out that route. A fallback still needs the approved plan's authority;
a required durable route is never silently replaced with typing. Confirm delivery from the
receiver, never from a probe, a visible message card, an idle notice or an absent queue item.
Transcript process fields can support local attribution but are not portable authentication
guarantees. The relay keeps bare-mode skill discovery, pending-message UI coverage and unrun
platform/optional routes explicit rather than inferring support.

## Upstream

- Claude Code — [cross-session messaging][ccm]
- Codex — [repository][codex]

[ccm]: https://code.claude.com/docs/en/cross-session-messaging
[codex]: https://github.com/openai/codex
