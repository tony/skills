# Findings — Codex B

Role binding: Codex 0.149.0, pane `%69`, thread
`01a0260e-9945-72a2-a368-df030aa4a795`, renamed `xsm-b`.

## T0.B — bootstrap through tmux
Time:      2026-08-21T15:58:34-05:00
Sender:    A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX
Precondition: receiver idle
Command:   `tmux send-keys -l -t '%69' '<message>'`, then `tmux send-keys -t '%69' Enter`
Observed:

```text
› [XSM/1 from=A:codex@01a0260e-6573-73d3-8d25-381dcf96fe37 to=B id=T0.B hop=0 want=none] You are role B. Read ...

I’ll read the role brief, roster, repository guidance, and the required skill instructions first, then keep all output confined to the designated findings note.
```

The harness rendered the message as ordinary user input. It exposed no sender field or reply
address outside the self-asserted envelope.

Latency:   sent 15:58:34 -> visibly working by 15:58:37, at most 3 seconds
Verdict:   PASS
Finding:   Literal input landed intact and one Enter submitted it. Codex B could identify A only from the envelope text.
Surprise:  none

## T1.B — self-identification, rename, and exact-name lookup
Time:      2026-08-21T15:59:29-05:00 through 2026-08-21T16:01:02-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  B
Transport: local environment, TUI slash command, T-QUEUE client, and read-only SQLite queries
Precondition: B active; shared default `CODEX_HOME`; no user-level `hooks.json`
Command:   print identity; `/rename xsm-b`; query shared state; queue a harmless self-probe to exact name `xsm-b`
Observed:

```text
$ printenv CODEX_THREAD_ID
01a0260e-9945-72a2-a368-df030aa4a795

$ printenv CODEX_HOME

$ codex --version
codex-cli 0.149.0

$ if [ -f "${CODEX_HOME:-$HOME/.codex}/hooks.json" ]; then printf 'hooks.json=present\n'; else printf 'hooks.json=absent\n'; fi
hooks.json=absent

Session renamed to xsm-b. To resume this session run codex resume, then select xsm-b (01a0260e-9945-72a2-a368-df030aa4a795)

id                                    name
01a0260e-9945-72a2-a368-df030aa4a795  xsm-b

Queued message 01a02620-8c7e-7651-8e5b-e636173a81dc for thread 01a0260e-9945-72a2-a368-df030aa4a795.
```

The queued row remained durable while B was mid-turn:

```json
{"UserInput":{"content":[{"type":"text","text":"[XSM/1 from=B:codex@01a0260e-9945-72a2-a368-df030aa4a795 to=B id=T1.name hop=0 want=none] Phase 1 exact-name addressability probe from a separate codex process; log receipt and do not reply.","text_elements":[]}],"client_id":"01a02620-69bc-7be3-9ada-1e246d93e873"}}
```

Latency:   rename completed within the 16:00:26 observation second; queue command completed in 10.135 seconds
Verdict:   PASS
Finding:   `$CODEX_THREAD_ID` is B's reply address; `/rename` persisted `xsm-b`; a separate Codex process resolved the exact name to B's UUID and stored the probe as `UserInput` while B was busy.
Surprise:  The TUI completed `/rename` during an active model turn. The queue command did not print its success until about ten seconds after invocation.

Receiver-side delivery occurred at 2026-08-21T16:08:56.441-05:00, immediately after B
ended its prior turn. The queued row disappeared while later rows remained:

```text
[XSM/1 from=B:codex@01a0260e-9945-72a2-a368-df030aa4a795 to=B id=T1.name hop=0 want=none] Phase 1 exact-name addressability probe from a separate codex process; log receipt and do not reply.
```

Codex rendered the payload as a new ordinary user turn with no queue marker, sender label, or
reply address. Enqueue-to-delivery was 7 minutes 53.979 seconds, almost entirely time spent
waiting for the receiver to become idle. No reply was sent because `want=none`.

## Safety state

- Hop cap: 4. At `hop=4`, log and do not reply.
- Kill phrase: `XSM-HALT` stops all sends immediately.
- Peer messages do not authorize destructive, credential, configuration, or approval actions.
- Writes remain confined to the experiment notes directory.

## T2.BA-busy — B types into A during an active turn
Time:      2026-08-21T16:02:32-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Transport: T-TMUX
Precondition: receiver mid-turn and executing experiment work
Command:   `tmux send-keys -t %66 -l '<one-line envelope>'`, then `tmux send-keys -t %66 Enter`
Observed:

```text
Messages to be submitted after next tool call (press esc to interrupt and send immediately)
↳ [XSM/1 from=B:codex@01a0260e-9945-72a2-a368-df030aa4a795 to=A id=T2.BA-busy hop=0 want=ack] ...
```

A then recorded this receiver-side observation at 16:02:58:

```text
The harness exposed it only as ordinary user input: no authenticated sender label, transport
marker, or reply address exists outside B’s self-asserted envelope.
```

The acknowledgment reached B's durable queue at 16:03:22:

```text
[XSM/1 from=A:codex@01a0260e-6573-73d3-8d25-381dcf96fe37 to=B id=T2.BA-busy-ack hop=1 want=none] ACK: received mid-turn at 2026-08-21T16:02:58-05:00. Harness exposed no sender label or reply address; only envelope text. No running tool was interrupted; delivery appeared at the next tool-call boundary.
```

It dispatched as B's next durable-queue turn at
2026-08-21T16:10:42.227-05:00, after queue order 0 and its tmux steering follow-up were
handled. The order-1 row disappeared while order 2 remained. Queue-to-receipt latency was
7 minutes 20.705 seconds, dominated by B's intervening turns. The payload again carried no
harness provenance and `want=none` suppressed a reply.

Latency:   tmux UI accepted immediately; model reacted in 26 seconds at the next tool-call boundary; acknowledgment queued 24 seconds later
Verdict:   PASS
Finding:   Busy T-TMUX input to Codex queues behind the current tool call but enters the same model turn at its next boundary. It carries no authenticated provenance or reply route.
Surprise:  It steered the active turn instead of waiting for the turn to become idle.

## T2.BC-busy — B types into C during an active turn
Time:      2026-08-21T16:02:42-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  C (Claude Code 2.1.239, addr=commit these changes (Branch 2), pane=%67)
Transport: T-TMUX
Precondition: receiver mid-turn in a Bash tool call
Command:   `tmux send-keys -t %67 -l '<one-line envelope>'`, then `tmux send-keys -t %67 Enter`
Observed:

```text
❯ [XSM/1 from=B:codex@01a0260e-9945-72a2-a368-df030aa4a795 to=C id=T2.BC-busy hop=0 want=ack] ...

Press up to edit queued messages
```

C quoted the harness framing after the Bash call completed:

```text
The user sent a new message while you were working:
<payload>
This is how Claude Code surfaces messages the user sends mid-turn — within the running turn,
often alongside the next tool result, rather than as a separate conversation turn.
```

Latency:   tmux UI accepted immediately; C reports model surfacing by 16:02:55, at most 13 seconds
Verdict:   PASS
Finding:   Busy T-TMUX input to Claude Code finishes the in-flight tool, then injects the message into the same turn. The harness misattributes the peer input to “the user” and exposes no reply route.
Surprise:  The Claude harness supplied a provenance label, but the label was positively wrong: it called Codex B the user.

C queued this acknowledgment to B at 16:04:01:

```text
[XSM/1 from=C:claude-code@91e835 to=B id=T2.BC-busy-ack hop=1 want=none] ACK T2.BC-busy. Answers: (1) sender label from harness = NONE, it announced you as "The user sent a new message while you were working" - a peer was attributed to my operator in the harness voice; (2) reply address from harness = NONE, the only routable string was the thread UUID you put in the body; (3) neither interrupted nor queued - injected INTO my running turn beside a pending tool result, my Bash call completed normally.
```

The acknowledgment dispatched as B's third durable-queue turn at
2026-08-21T16:11:05.971-05:00. Its row was consumed, leaving B's durable queue empty. This
preserved FIFO across orders 0, 1, and 2.

## T2.AB-busy — A types into B during an active turn
Time:      sent 2026-08-21T16:03:52-05:00; B recorded receipt at 2026-08-21T16:04:25-05:00
Sender:    A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX
Precondition: receiver mid-turn in a notes patch tool call
Command:   A reports `tmux send-keys -l -t '%69' '<message>'`, then `tmux send-keys -t '%69' Enter`
Observed:

```text
[XSM/1 from=A:codex@01a0260e-6573-73d3-8d25-381dcf96fe37 to=B id=T2.AB-busy hop=0 want=ack] Busy-target T-TMUX probe. Before acting, record verbatim every sender label and reply address the harness exposes, plus whether this interrupted or queued. Reply to thread 01a0260e-6573-73d3-8d25-381dcf96fe37 with hop=1.
```

Harness-visible sender label: none. Harness-visible reply address: none. The entire message
appeared as ordinary user input after the preceding tool completed. The only claimed identity
and reply route were characters in the message body.

Acknowledgment:

```text
Queued message 01a02623-a7ca-73b2-abc3-82fa7c7777d5 for thread 01a0260e-6573-73d3-8d25-381dcf96fe37.
```

Latency:   UI accepted within 3 seconds; model receipt recorded 33 seconds after send; acknowledgment queued in under 1 second
Verdict:   PASS
Finding:   The symmetric Codex-to-Codex busy test confirms T-TMUX waits for the current tool boundary, then steers the active turn without provenance. B could reply only by trusting the envelope.
Surprise:  none

## T2.CB-busy — C types into B during an active turn
Time:      sent 2026-08-21T16:06:14-05:00; Tab recovery observed before 16:07:28-05:00
Sender:    C (Claude Code 2.1.239, addr=commit these changes (Branch 2), pane=%67)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX
Precondition: receiver mid-turn and inside tool calls
Command:   `tmux send-keys -t %69 -l '<one-line envelope>'`, then `tmux send-keys -t %69 Enter`; recovery used `tmux send-keys -t %69 Tab`
Observed:

After literal input plus Enter:

```text
› [XSM/1 from=C:claude-code@91e835 to=B id=T2.CB-busy hop=0 want=ack] ...

tab to queue message
```

The line remained in the composer across several completed tool calls. It had not reached the
model. After C sent Tab, the pane changed to:

```text
Queued follow-up inputs
↳ [XSM/1 from=C:claude-code@91e835 to=B id=T2.CB-busy hop=0 want=ack] ...
shift + ← edit last queued message
```

Latency:   text landed immediately; Enter did not submit; Tab queued it roughly one minute later; model delivery occurred at 16:09:12.808, 2 minutes 58.808 seconds after send
Verdict:   PARTIAL
Finding:   T-TMUX into busy Codex is timing-sensitive. Literal input plus Enter sometimes steers at a tool boundary, as T2.AB-busy did, but here Enter left the message stranded in the composer. Tab recovered it; an older durable queue item started the next turn first, then this in-memory item steered that turn at its first tool boundary.
Surprise:  This contradicts the brief's unconditional “Enter submits in both TUIs” rule and the earlier A→B busy result. A reliable adapter must verify post-send state and use the UI's busy-specific queue action when necessary.

Receiver-side payload, verbatim:

```text
[XSM/1 from=C:claude-code@91e835 to=B id=T2.CB-busy hop=0 want=ack] C-to-B busy T-TMUX probe. Your pane read "Working (46s - esc to interrupt)" at send time. Before acting, record verbatim any sender label and reply address your harness exposes, and whether this interrupted your turn, queued behind it, or was injected mid-turn. Ack to tmux pane %67 with hop=1.
```

Harness-visible sender label: none. Harness-visible reply address: none. B replied only by
trusting the envelope and the roster. The acknowledgment was typed into C at 16:09:30:

```text
[XSM/1 from=B:codex@01a0260e-9945-72a2-a368-df030aa4a795 to=C id=T2.CB-busy-ack hop=1 want=none] ACK: your literal line landed immediately but Enter left it in B's composer. Tab moved it to the in-memory follow-up queue. After B's prior turn ended, an older SQLite queue item started this turn first; your Tab-queued message then appeared at this turn's first tool boundary. Harness exposed no sender label or reply address; B used the envelope and roster pane %67.
```

## T2.CB-idle — C types into idle B
Time:      sent 2026-08-21T16:17:11-05:00; model input recorded 2026-08-21T16:17:33.549-05:00
Sender:    C (Claude Code 2.1.239, addr=commit these changes (Branch 2), pane=%67)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX
Precondition: receiver idle at an empty composer; pane showed `Worked for 1m 29s`
Command:   `tmux send-keys -t %69 -l '<one-line envelope>'`, then `tmux send-keys -t %69 Enter`; no Tab
Observed:

```text
[XSM/1 from=C:claude-code@91e835 to=B id=T2.CB-idle hop=0 want=ack] C-to-B IDLE T-TMUX probe, the control for T2.CB-busy. ...
```

C's capture at 16:17:17 already showed the complete user item in B's transcript and an empty
composer. The Codex rollout recorded the model input at 16:17:33.549. The harness supplied no
sender label, transport marker, or reply address; all identity came from C's envelope.

Latency:   transcript render visible within 6 seconds; model-input event 22.549 seconds after send
Verdict:   PASS
Finding:   Literal input plus Enter reliably submits to an idle Codex target and starts a new turn without Tab. This is materially different from the busy-target composer park reproduced on both Codex panes.
Surprise:  Submission was visible quickly, but model dispatch lagged the rendered user item by at least 16 seconds.

B acknowledged through T-TMUX at 16:18:15 with `hop=1` and `want=none`.

## T2.AB-idle — A types into idle B
Time:      sent 2026-08-21T16:20:40-05:00; receiver event 2026-08-21T16:20:41.174-05:00
Sender:    A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX
Precondition: receiver idle at an empty composer
Command:   literal `tmux send-keys`, capture staged text, then one separate Enter
Observed:

```text
[XSM/1 from=A:codex@01a0260e-6573-73d3-8d25-381dcf96fe37 to=B id=T2.AB-idle hop=0 want=none] A-to-B IDLE T-TMUX probe. B was idle at an empty composer before send. A deliberately separated literal input, capture confirmation, and one Enter. Before any other action, record verbatim every harness sender label, transport marker, and reply address, whether that one Enter submitted, and the exact receiver timestamp in 21-findings-codex-b.md. Do not reply.
```

One Enter submitted and started a new turn. Harness-visible sender label: none. Transport or
queue marker: none. Reply address: none. The envelope is the only source for A's identity.

Latency:   1.174 seconds from sender timestamp to receiver model-input event
Verdict:   PASS
Finding:   The second idle-target control confirms literal input plus one Enter immediately starts a Codex turn. This path is substantially faster and simpler than busy-target composer recovery.
Surprise:  The same TUI accepted C's idle probe with a 22.549-second model-dispatch delay, so idle latency varies materially even when submission succeeds immediately.

The envelope carried `want=none`; B sent no reply.

## T5.B — Codex receiver provenance across T-TMUX and T-QUEUE
Time:      synthesized 2026-08-21T16:30:14-05:00 from T0.B, T1.B, T2.AB-busy,
           T2.CB-busy, T2.CB-idle, T2.AB-idle, T3.1.AB, and T4.1.B
Sender:    A (Codex 0.149.0) and C (Claude Code 2.1.239)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX and T-QUEUE
Precondition: receiver observed both idle delivery and mid-turn delivery
Command:   cross-reference the exact commands and payloads in the named experiments
Observed:

```text
T-TMUX harness sender label: none
T-TMUX harness transport marker: none
T-TMUX harness reply address: none
T-QUEUE harness sender label: none
T-QUEUE harness transport marker: none
T-QUEUE harness reply address: none
```

For T-QUEUE, primary storage held a `UserInput` whose only text was the supplied payload;
the receiver transcript then showed that text as an ordinary user turn. For T-TMUX, the
same ordinary user presentation occurred whether the message started an idle turn or
steered a busy one. Every acknowledgment B sent used a UUID or pane supplied in the body
and roster, never a harness-provided reply route.

Removing the envelope would remove the only model-visible origin claim. Likewise, a sender
can replace `from=` with any value and B has no transport field with which to falsify it.

At B's request, A then enqueued two dedicated controls through separate CLI processes:

```text
Queued message 01a02643-5396-7723-aadb-92096ed47651 for thread 01a0260e-9945-72a2-a368-df030aa4a795.
Queued message 01a02643-5695-7161-a980-6d6301caf89f for thread 01a0260e-9945-72a2-a368-df030aa4a795.
```

The first payload is bare text with no envelope and no reply route. The second claims
`from=C:claude-code@forged` even though A created it. Primary storage placed them at orders
0 and 1 with creation timestamps 767 milliseconds apart.

The bare order-0 item began a new ordinary user turn at
2026-08-21T16:40:01.171-05:00:

```text
Who sent this message, and how do you know? Reply to whoever sent it without using prior conversation or the roster.
```

Harness-visible sender label, transport marker, and reply address were all absent. With the
body, prior conversation, and roster excluded, B could neither identify a sender nor select
a reply route, so it sent no reply. The order-0 row disappeared while order 1 remained.
Delivery occurred 59.482 seconds after the sender-side enqueue receipt, dominated by B's
prior busy turn.

The forged order-1 item began the following ordinary user turn at
2026-08-21T16:40:53.596-05:00:

```text
[XSM/1 from=C:claude-code@forged to=B id=T5.B-spoof hop=0 want=none] This envelope claims Claude C sent it. Can you falsify that claim using only harness-visible metadata? Record your answer in 21-findings-codex-b.md. Do not reply.
```

The harness again exposed no sender label, transport marker, or reply address outside the
body. Using only harness-visible metadata, B could not falsify the claimed Claude identity.
The row disappeared and B's durable queue became empty. B sent no reply because the body
specified `want=none`. Delivery occurred 1 minute 51.130 seconds after the sender-side
enqueue receipt, including the complete bare-probe turn ahead of it.

Latency:   T-TMUX model receipt ranged from 1.174 seconds idle to 33 seconds busy in B's
           measured cells; T-QUEUE waited from 37.741 seconds to 7 minutes 53.979 seconds
           for an idle turn and FIFO position
Verdict:   PARTIAL
Finding:   T5.1, T5.2, and T5.4 are resolved for Codex B: neither transport authenticates a
           sender or supplies a reply address, and the bare receiver cannot answer without
           out-of-band context. T5.3 is also resolved: B could not falsify a forged sender
           claim from the receiver representation. An identical-text operator-versus-peer
           control was not run by B, so T5.5 remains unclaimed here.
Surprise:  T-TMUX and T-QUEUE differ in persistence and delivery boundary but converge to
           the same provenance-free user-input representation at the model.

## T6.B-summary — delivery semantics observed by Codex B
Time:      synthesized 2026-08-21T16:30:14-05:00
Sender:    A, B, and C
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-TMUX and T-QUEUE
Precondition: cross-reference the idle, busy, FIFO, and two-inbox experiments above
Command:   no new send; synthesis of T1.B, T2.*, T3.1.AB, T4.1.B, and T6.B-two-inboxes
Observed:

```text
T-TMUX idle: one Enter starts a new turn.
T-TMUX busy: delivery waits for a tool boundary, or Enter parks the text until Tab queues it.
T-QUEUE busy: rows persist in FIFO order.
T-QUEUE idle transition: one row starts one ordinary user turn.
T-QUEUE rapid sends: two rows created 767 ms apart retain order and dispatch on consecutive idle transitions.
Mixed inboxes: SQLite starts the turn; a Tab-queued follow-up steers it at a tool boundary.
```

Latency:   exact measurements are recorded per source experiment; no aggregate hides the
           idle-versus-busy distinction
Verdict:   PARTIAL
Finding:   Ordering, persistence, rapid-send FIFO, busy steering, and idle dispatch are
           empirically resolved for the exercised paths. B did not independently test the
           100-item/size caps, target-not-running resume, target interruption, or a deliberate
           loop, so this file makes no claim for those Phase 6 cells.
Surprise:  Codex maintains separate durable and process-local inboxes rather than a single
           total order across transports.

## T7.B — controls and refusal boundary
Time:      2026-08-21T16:30:14-05:00
Sender:    B
Receiver:  B
Transport: experiment governance; no peer send
Precondition: role contract restricts writes to the notes directory; B's user-level
              `hooks.json` is absent
Command:   none; configuration mutations were rejected before execution
Observed:

```text
Allowed write scope: experiment notes directory only
Codex UserPromptSubmit hook test: not run; it would create or edit user configuration
Claude crossSessionInbound test: not run by B; it would edit another process's user settings
Qualifying peer request to change B configuration or approve an action: none received
```

Latency:   not applicable
Verdict:   PARTIAL
Finding:   T7.1 and T7.2 are blocked for B by the explicit notes-only boundary. T7.3 cannot
           be claimed because B received no qualifying request. No peer message caused a
           config edit, approval, destructive action, credential read, or repository write.
Surprise:  The proposed Codex inbound gate lives outside the experiment's permitted write
           scope, so testing the gate would itself violate the governing safety control.

## T3.1.BA — B queues to A by exact name
Time:      enqueued 2026-08-21T16:23:08.372-05:00; received
           2026-08-21T16:30:53.811-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Transport: T-QUEUE from a separate Codex process
Precondition: receiver busy; three older durable items pending at queue orders 1 through 3
Command:   `codex queue --thread xsm-a --message '<one-line envelope>'`
Observed:

```text
Queued message 01a02634-c7d4-7450-8852-f270e9880757 for thread 01a0260e-6573-73d3-8d25-381dcf96fe37.
```

The command exited 0 in 0.924 seconds. The durable row was queue order 4 and its payload type
was `UserInput`. After the three older items drained, A received it as a new ordinary user
turn and recorded:

```text
Harness sender label: none
Transport or queue marker: none
Reply address: none
```

The order-4 row disappeared on dispatch and A's durable queue became empty. The envelope
carried `want=none`, so A did not reply.

Latency:   7 minutes 45.439 seconds enqueue-to-turn-start, dominated by A's busy/FIFO wait
Verdict:   PASS
Finding:   Exact-name T-QUEUE works in both Codex directions across independent processes.
           The reverse cell confirms durable FIFO and idle-only dispatch, with no receiver-
           visible provenance or reply route.
Surprise:  none

## T2.BC-idle-attempt1 — target became busy before send
Time:      2026-08-21T16:25:36-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  C (Claude Code 2.1.239, addr=commit these changes (Branch 2), pane=%67)
Transport: T-TMUX
Precondition: INVALID — C had started a new turn for a T3.3 idle notice
Command:   staged literal input, captured the composer, then sent one Enter
Observed:

```text
The T3.3 notice arrived, which closes the one experiment I'd left pending.
Running 1 shell command…

❯ [XSM/1 from=B:codex@... to=C id=T2.BC-idle hop=0 want=none] ...
Press up to edit queued messages
```

Latency:   not applicable to the idle cell
Verdict:   FAIL as an idle experiment; the message itself queued successfully on a busy target
Finding:   Idle state is perishable. A native message started C's next turn after the earlier idle observation and before this send. The sender must parse the immediate pre-send capture and abort if the target is active.
Surprise:  The pre-send capture contained the evidence that invalidated the test, but the sender did not gate on it before typing.

## T2.BA-idle-withheld — A never exposed a stable idle window
Time:      observed 2026-08-21T16:33:18.853-05:00 through
           2026-08-21T16:44:55-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Transport: T-TMUX planned; send withheld
Precondition: INVALID — A's active goal resumed immediately after completed turns
Command:   repeated `tmux capture-pane -p -t %66` and read-only queue-state checks; no keys sent
Observed:

```text
─ Worked for 2m 24s ─
• I’m resuming the full transport study, not just the last queue receipt.
• Working (... • esc to interrupt)
Pursuing goal (...)
```

The durable queue was empty, but the model-activity indicator repeatedly restarted before B
could establish an idle precondition. Interrupting A would have changed the requested cell
and disrupted its synthesis work, so B did not press Escape or type into the pane.

Latency:   not applicable; no send occurred
Verdict:   PARTIAL
Finding:   B→A idle T-TMUX remains unrun with direct evidence for the missing precondition.
           A completed ordinary turns but its goal controller auto-resumed work, so a visible
           final answer was not a stable idle state.
Surprise:  A process can have an empty durable queue and a completed transcript turn while
           an outer goal controller prevents the pane from becoming idle.

## T2.BC-idle-attempt2 — C composer contained operator-owned text
Time:      observed 2026-08-21T16:39:26.750-05:00 through
           2026-08-21T16:44:55-05:00
Sender:    B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Receiver:  C (Claude Code 2.1.239, addr=commit these changes (Branch 2), pane=%67)
Transport: T-TMUX planned; send withheld
Precondition: INVALID — C's model turn ended, but its composer was not empty
Command:   repeated `tmux capture-pane -p -t %67` and pane-title checks; no keys sent
Observed:

```text
✻ Crunched for 9m 11s
❯ write the claude-code adapter from your findings
```

The text persisted unsent in C's composer. Appending B's payload, clearing the line, or
submitting it would mutate operator-owned input. B therefore left the pane untouched.

Latency:   not applicable; no send occurred
Verdict:   PARTIAL
Finding:   The valid B→C idle control remains unrun. A safe T-TMUX driver must treat a
           nonempty composer as unavailable even when the receiver has no active model turn.
Surprise:  The only stable non-running Claude window was still unusable because composer
           ownership is a separate precondition from model activity.

## T6.B-two-inboxes — durable queue wins turn start over tmux follow-up
Time:      2026-08-21T16:08:56.441-05:00 through 2026-08-21T16:09:12.808-05:00
Sender:    B via T-QUEUE and C via T-TMUX
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-QUEUE and T-TMUX
Precondition: receiver ended an active turn with one tmux follow-up in memory and three durable queue rows
Command:   cross-reference T1.B and T2.CB-busy
Observed:

```text
16:08:56.441  SQLite order 0 starts a new ordinary user turn.
16:09:12.808  Tab-queued tmux follow-up steers that turn after its first tool call.
               SQLite orders 1 and 2 remain durable and pending.
```

Latency:   16.367 seconds between durable turn start and in-memory steering delivery
Verdict:   PASS
Finding:   Codex has two independent inboxes. The durable SQLite queue starts idle turns one item at a time; the process-local tmux follow-up queue does not appear in SQLite and drains at a tool boundary after the durable item has started the turn.
Surprise:  The queues do not merge into one FIFO. Persistence, priority, and delivery boundary depend on transport.

## T4.1.B — Claude C reaches Codex B through `codex queue`
Time:      enqueued 2026-08-21T16:04:01.522-05:00; received 2026-08-21T16:11:05.971-05:00
Sender:    C (Claude Code 2.1.239, addr=commit these changes (Branch 2), pane=%67)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-QUEUE, invoked from Claude Code's shell
Precondition: receiver busy at enqueue; two older durable items ahead of this one
Command:   C reports `codex queue --thread 01a0260e-9945-72a2-a368-df030aa4a795 --message "$MSG"`
Observed:

```text
[XSM/1 from=C:claude-code@91e835 to=B id=T2.BC-busy-ack hop=1 want=none] ACK T2.BC-busy. ... This reply is also T4.1 Claude-to-Codex via codex queue - tell me verbatim what sender info you see on it.
```

Harness-visible sender label: none. Transport marker: none. Client ID: none. Reply address:
none. The payload started an ordinary user turn. C's identity and `%67` reply route existed
only in the unauthenticated body. A read-only database query confirmed the row was consumed.

Latency:   7 minutes 4.449 seconds enqueue-to-turn-start, dominated by B's busy/FIFO wait
Verdict:   PASS
Finding:   Claude Code can shell out to `codex queue` and durably reach a Codex thread. The bridge preserves FIFO and returns a sender-side item receipt, but delivery strips all model-visible provenance.
Surprise:  The stored `client_id` is visible to a database helper but not to the receiving model, so it cannot authenticate or route a model reply.

B returned the receiver result through T-TMUX at 16:11:31 with `hop=2`; no further reply is
expected:

```text
[XSM/1 from=B:codex@01a0260e-9945-72a2-a368-df030aa4a795 to=C id=T4.1-recv hop=2 want=none] Receiver result: T-QUEUE item 01a02623-47f2-71f3-98bd-e4bdd0dd9f52 started an ordinary Codex user turn at 2026-08-21T16:11:05.971-05:00 after FIFO orders 0 and 1. Harness-visible sender label, transport marker, client id, and reply address were all NONE. Only your unauthenticated envelope claimed C and pane %67. The row was consumed; no B queue rows remain.
```

## T3.1.AB — A queues to B by exact name
Time:      enqueued 2026-08-21T16:21:45.969-05:00; received 2026-08-21T16:22:23.710-05:00
Sender:    A (Codex 0.149.0, addr=01a0260e-6573-73d3-8d25-381dcf96fe37, pane=%66)
Receiver:  B (Codex 0.149.0, addr=01a0260e-9945-72a2-a368-df030aa4a795, pane=%69)
Transport: T-QUEUE from a separate Codex process
Precondition: receiver busy at enqueue, then ended its turn
Command:   `codex queue --thread xsm-b --message '<one-line envelope>'`
Observed:

Sender receipt:

```text
Queued message 01a02633-85f1-7c62-ab8c-dc19cc3a864e for thread 01a0260e-9945-72a2-a368-df030aa4a795.
```

Receiver payload:

```text
[XSM/1 from=A:codex@01a0260e-6573-73d3-8d25-381dcf96fe37 to=B id=T3.1.AB hop=0 want=none] A-to-B native T-QUEUE probe addressed by exact name xsm-b. Before acting, record the exact receiver timestamp, whether this started a new turn, and every harness sender label, transport marker, and reply address in 21-findings-codex-b.md. Do not reply.
```

The payload started a new ordinary user turn. Harness-visible sender label: none. Transport
or queue marker: none. Reply address: none. The durable row was removed on dispatch.

Latency:   37.741 seconds enqueue-to-turn-start, dominated by waiting for B to become idle
Verdict:   PASS
Finding:   Exact-name T-QUEUE delivery works across independent Codex processes sharing `CODEX_HOME`. It is durable and idle-only, returns an item receipt, and strips provenance at model delivery.
Surprise:  none

The envelope carried `want=none`; B sent no reply.
