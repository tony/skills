# Phase 0 roster

Captured: 2026-08-21T15:57:30-05:00

The experiment window is tmux session `34`, window `1` (`@50`). Role O is the external
Claude Code session that authored `00-GOAL.md`; it is not one of the three experiment panes.

## Role A — Codex

- **Pane**: `%66` (index 0, top)
- **Agent**: Codex 0.149.0, `gpt-5.6-sol`, reasoning `max`
- **cwd**: `~/work/ai/skills`
- **Permission mode**: Full Access / YOLO
- **CODEX_HOME**: unset in the launch environment; default `~/.codex`
- **Own address**: `01a0260e-6573-73d3-8d25-381dcf96fe37`
- **Address source**: `$CODEX_THREAD_ID` in an agent-run command and the shared state DB
- **Status at capture**: active

## Role B — Codex

- **Pane**: `%69` (index 1, bottom left)
- **Agent**: Codex 0.149.0, `gpt-5.6-sol`, reasoning `max`
- **cwd**: `~/work/ai/skills`
- **Permission mode**: Full Access / YOLO
- **CODEX_HOME**: unset in the launch environment; default `~/.codex`
- **Own address**: `01a0260e-9945-72a2-a368-df030aa4a795`
- **Address source**: `/status`
- **Status at capture**: idle; no model turn yet, and no row in the shared state DB yet

## Role C — Claude Code

- **Pane**: `%67` (index 2, bottom right)
- **Agent**: Claude Code 2.1.239, Opus 5, effort `xhigh`
- **cwd**: `~/work/ai/skills`
- **Settings scope**: user settings
- **Permission mode**: bypass permissions
- **Inbound posture**: `crossSessionInbound: accept`
- **Session ID**: `25340a0c-e401-43cb-8224-0df7eca2240f`
- **Session name**: `commit these changes (Branch 2)`
- **Own peer address**: `uds:/run/user/1000/cc-socks/2385068.sock`
- **Address source**: `/status` and the live Claude session registry
- **Status at capture**: idle

## Role O — Claude Code orchestrator

- **Pane**: none; external interactive session on the same machine
- **Agent**: Claude Code 2.1.239, Opus 5
- **cwd**: `~/study/ai-agents/codex`
- **Settings scope**: user settings
- **Permission mode**: bypass permissions
- **Session ID**: `7a80ce4a-ca43-47db-b325-706d2d5cd9c5`
- **Session name / SendMessage address**: `codex-66`
- **Own peer address**: `uds:/run/user/1000/cc-socks/1989951.sock`
- **Address source**: live Claude session registry; authorship from the session transcript
- **Status at capture**: idle

## Raw topology capture

Command:

```console
$ tmux list-panes \
    -t '34:1' \
    -F '#{pane_index}\t#{pane_id}\t#{pane_active}\t#{pane_current_command}\t#{pane_current_path}\t#{pane_pid}\t#{pane_title}'
```

Observed:

```text
0  %66  0  node    ~/work/ai/skills  2281682  skills
1  %69  0  node    ~/work/ai/skills  2306336  skills
2  %67  1  claude  ~/work/ai/skills  2292197  commit these changes (Branch 2)
```

## T0.A — bootstrap Codex A

Time:      before 2026-08-21T15:57:30-05:00
Sender:    operator
Receiver:  A (Codex 0.149.0, pane=%66)
Transport: direct operator prompt, not T-TMUX
Precondition: receiver idle
Command:   unavailable; supplied through the Codex client
Observed:  A read the attached brief and inspected the window without another prompt.
Latency:   not measured
Verdict:   PARTIAL
Finding:   Bootstrap succeeded, but it does not validate tmux delivery to A.
Surprise:  The pasted brief predated the on-disk T0 bootstrap amendment.

## T0.B — bootstrap Codex B

Time:      2026-08-21T15:58:34-05:00
Sender:    A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX
Precondition: receiver idle
Command:   `tmux send-keys -l -t '%69' '<message>'`, then `tmux send-keys -t '%69' Enter`
Observed:  `I’ll read the role brief, roster, repository guidance, and the required skill instructions first, then keep all output confined to the designated findings note.`
Latency:   sent 15:58:34 -> visibly working by 15:58:37, at most 3 seconds
Verdict:   PASS
Finding:   The single-line text landed intact, one Enter submitted it, and B began reading the brief without another prompt.
Surprise:  none

## T0.C — bootstrap Claude C

Time:      2026-08-21T15:59:15-05:00
Sender:    A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Receiver:  C (Claude Code 2.1.239, addr=uds:/run/user/1000/cc-socks/2385068.sock, pane=%67)
Transport: T-TMUX
Precondition: receiver idle after `Escape` dismissed `/status`
Command:   `tmux send-keys -l -t '%67' '<message>'`, then `tmux send-keys -t '%67' Enter`
Observed:  `Reading roster file` followed by a shell read of `10-roster.md`.
Latency:   sent 15:59:15 -> visibly working by 15:59:18, at most 3 seconds
Verdict:   PASS
Finding:   The single-line text landed intact, one Enter submitted it, and C began reading the brief without another prompt.
Surprise:  The status overlay had to be dismissed before literal input could reach the prompt.

## Phase 0 caveats

- A's T0 path still needs an independent T-TMUX control before later T-TMUX results can be
  generalized to Codex A.
- B exposes a session UUID in `/status`, but durable state and queue addressability remain
  Phase 1 experiments.
- O's registration is live and authoritative, but O must still record its own `/status` and
  `/list-agents` output in `23-findings-claude-o.md`.
