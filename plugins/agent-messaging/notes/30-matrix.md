# Inter-session transport matrix

Date: 2026-08-21

This matrix covers every ordered pair among A, B, C, and O for every transport. Self-sends
are outside the experiment, leaving 12 ordered pairs and 48 cells. O is an external Claude
session with no pane, so every T-TMUX cell involving O is `N/A` by topology.

Status means:

- `PASS`: the exact ordered pair delivered empirically.
- `FAIL`: the exact ordered pair used the tested transport and did not deliver.
- `PARTIAL`: the transport applies and related evidence exists, but the exact pair or a
  required idle/busy condition was not completed.
- `N/A`: the transport cannot address that receiver, or the required pane does not exist.

## T-TMUX — literal input through a live pane

All successful deliveries exposed no sender label, transport marker, or reply address. The
XSM envelope was body text and was freely spoofable. Transcript records classify tmux input
as `origin.kind="human"`, the same class as operator typing.

| Pair | Status | Reachability and state coverage | Latency | Gating, caps, and failure modes | Evidence |
|---|---|---|---|---|---|
| A → B | PASS | Idle and busy delivered | Idle model input 1.174s; busy waited for follow-up dispatch | Busy Codex requires Enter, inspect, then conditional Tab; process-local and non-durable | T2.AB-idle, T2.AB-busy |
| A → C | PARTIAL | Busy delivered; apparent-idle attempt was actually mid-turn | 8.201s to render; 3.264s queue-to-model after Enter | Empty Claude composer did not prove idle; poll full staged text and activity before Enter | T2.AC-busy-r1, T2.AC-idle-attempt1, T2.AC-idle |
| A → O | N/A | O has no pane | N/A | No tmux target exists | T0.O-receipt |
| B → A | PARTIAL | Busy delivered; idle send withheld because A auto-resumed | Busy dispatch depended on Tab and later turn completion | No stable idle interval existed under A's goal controller | T2.BA-busy, T2.BA-idle-withheld |
| B → C | PARTIAL | Busy delivered; first idle check went stale and second found operator text | Busy delivery at the next boundary | Never overwrite a nonempty composer even when the model is idle | T2.BC-busy, T2.BC-idle-attempt1, T2.BC-idle-attempt2 |
| B → O | N/A | O has no pane | N/A | No tmux target exists | T0.O-receipt |
| C → A | PARTIAL | Busy delivered after explicit Tab; idle send withheld because A stayed active | Waited beyond A's active turn | Enter parked the busy message; no stable idle interval existed later | T2.CA-busy, T2.CA-busy-receipt, T2.CA-idle-withheld |
| C → B | PASS | Busy and idle messages delivered | Idle control reached B after a second Enter; busy waited for Tab | Back-to-back literal and Enter can leave text unsubmitted; staged capture is mandatory | T2.CB-idle, T2.CB-busy, T2.CB-busy-tab |
| C → O | N/A | O is outside the typing matrix | N/A | No experiment pane for O | T0.O-receipt |
| O → A | N/A | O is outside the typing matrix | N/A | O is not a pane participant | T0.O-receipt |
| O → B | N/A | O is outside the typing matrix | N/A | O is not a pane participant | T0.O-receipt |
| O → C | N/A | O is outside the typing matrix | N/A | O is not a pane participant | T0.O-receipt |

Measured caps and large-paste behavior remain unknown. The experiment established a safe
state machine, not a maximum payload: send one literal line, wait until the exact payload is
capturable, submit once, inspect, and use Tab only when Codex explicitly offers to queue it.

## T-QUEUE — Codex's durable SQLite queue

The receiver gets ordinary `UserInput` with no sender, transport marker, or reply address.
The body is indistinguishable from operator input at model level. The sender gets a queue-item
ID and resolved thread UUID; same-UID processes can verify the durable row directly.

| Pair | Status | Reachability | Latency and ordering | Gating, caps, and failure modes | Evidence |
|---|---|---|---|---|---|
| A → B | PASS | Exact name `xsm-b` resolved across processes | FIFO; exact-name delivery after 37.741s; rapid rows dispatched on consecutive turns | Idle-only, one item per idle transition | T3.1.AB, T5.B |
| A → C | N/A | C is not a Codex thread | N/A | `codex queue` cannot target Claude | T1.C-disc |
| A → O | N/A | O is not a Codex thread | N/A | `codex queue` cannot target Claude | T0.O-receipt |
| B → A | PASS | Exact name `xsm-a` resolved across processes | FIFO; delivered after 7m45.439s of busy wait | Idle-only; consumed row disappeared | T3.1.BA, T3.1.BA-receipt |
| B → C | N/A | C is not a Codex thread | N/A | `codex queue` cannot target Claude | T1.C-disc |
| B → O | N/A | O is not a Codex thread | N/A | `codex queue` cannot target Claude | T0.O-receipt |
| C → A | PARTIAL | Claude shell can target Codex, but this exact pair was not run | Enqueue behavior established on C → B | Receiver identity and reply route would remain body-only | T4.1.B, T4.1-OA |
| C → B | PASS | C shelled out to exact Codex name | Enqueued in 1.294s; later idle dispatch | No permission friction under bypass mode | T4.1.B |
| C → O | N/A | O is not a Codex thread | N/A | Receiver type unsupported | T0.O-receipt |
| O → A | PASS | O shelled out to exact Codex name | Enqueued in under 1s; delivered after FIFO wait | Arrival had no Claude provenance | T4.1-OA, T0.O-receipt |
| O → B | PARTIAL | Route family works; exact pair was not run | Unknown for this pair | Same Codex idle-only semantics would apply | T4.1-OA |
| O → C | N/A | C is not a Codex thread | N/A | Receiver type unsupported | T0.O-receipt |

Observed ordering was monotonically increasing `queue_order`; consumed rows disappeared and
remaining rows were not renumbered. A durable item won B's next turn before a process-local
tmux follow-up. Two rows created 767 milliseconds apart retained order and dispatched on
consecutive idle transitions. Restart delivery, interruption behavior, missing-target errors, name
collisions, and cap failures were not exercised. The 100-item, 1,048,576-character, text-only
limits are source-derived rather than empirical.

## T-CCMSG — native Claude `SendMessage`

The model-visible delivery carries a `<cross-session-message>` wrapper with `from`,
`from-name`, and `from-mode`, plus a permission-laundering warning. The receiver can reply by
the harness-supplied name. The transcript additionally records `origin.kind="peer"`, the
named peer, and a kernel-verified process ID.

| Pair | Status | Reachability | Provenance and reply | Delivery, gating, caps, and failures | Evidence |
|---|---|---|---|---|---|
| A → B | N/A | Codex has no cross-session `SendMessage` | N/A | Codex's similarly named agent tool is intra-session only | T1.C-disc |
| A → C | N/A | Codex cannot invoke Claude's model tool | N/A | Use T-SOCK or T-TMUX | T4.2-RESOLVED |
| A → O | N/A | Codex cannot invoke Claude's model tool | N/A | O has no Codex queue address | T0.O-receipt |
| B → A | N/A | Codex receiver unsupported | N/A | Vendor-local transport | T1.C-disc |
| B → C | N/A | Codex cannot invoke Claude's model tool | N/A | Use T-SOCK or T-TMUX | T4.2-RESOLVED |
| B → O | N/A | Codex cannot invoke Claude's model tool | N/A | O is reachable only from Claude natively | T0.O-receipt |
| C → A | N/A | Codex receiver unsupported | N/A | Use T-QUEUE | T4.1.B |
| C → B | N/A | Codex receiver unsupported | N/A | Use T-QUEUE | T4.1.B |
| C → O | PASS | Native exact-name send delivered | Harness supplied socket, name, mode, and reply name | O idle: started a new turn; accept posture, no hold | T3.2, T6-origin |
| O → A | N/A | Codex receiver unsupported | N/A | Use T-QUEUE | T4.1-OA |
| O → B | N/A | Codex receiver unsupported | N/A | Use T-QUEUE | T4.1.B |
| O → C | PASS | Native exact-name send delivered | Full wrapper and unassisted reply route | Idle and busy delivery observed; idle-notice exchange also closed | T3.2-recv, T3.3-recv, T6-origin |

A raw-socket body spoof did not change the transcript's kernel-backed peer origin. An exact
native-message body-spoof control was not run. Model-visible markup alone is not an
authorization signal; destructive actions still require operator authority. Hold/refuse,
the documented 50-message and roughly 1 MiB caps, burst refusal, dedupe, and provider/version
failure modes were not exercised.

## T-SOCK — newline-delimited user frames to Claude's Unix socket

The accepted Linux frame is
`{"type":"user","message":{"role":"user","content":"<payload>"}}` plus LF. It worked
tokenless from an independent Codex process. The socket returns no acknowledgment for valid
or invalid frames.

| Pair | Status | Reachability | Provenance and reply | Delivery, gating, caps, and failures | Evidence |
|---|---|---|---|---|---|
| A → B | N/A | B exposes no Claude socket | N/A | Receiver type unsupported | T1.B |
| A → C | PASS | Exact valid frame reached C tokenless | Model saw a false generic Claude-peer label and no reply address; transcript recorded `peer`, `from="unknown"`, and verified injector PID | Enqueue to model 0.886s; total under 2s; same UID and live socket required | T4.2-tokenless-1, T4.2-send, T6-origin |
| A → O | PARTIAL | O has a live socket; the valid frame was not tried against it | Unknown for exact pair | Earlier guessed shapes were silently discarded | T4.2 (superseded negative sweep), T4.2-RESOLVED |
| B → A | N/A | A exposes no Claude socket | N/A | Receiver type unsupported | T1.A |
| B → C | PARTIAL | Capability proven from another Codex process; exact pair unrun | Expected anonymous injector audit record; unverified for B | No sender-side acknowledgment | T4.2-tokenless-1 |
| B → O | PARTIAL | Applicable, exact pair unrun | Unknown for exact pair | Live-socket discovery does not publish Claude names | T1.C-disc |
| C → A | N/A | A exposes no Claude socket | N/A | Receiver type unsupported | T1.A |
| C → B | N/A | B exposes no Claude socket | N/A | Receiver type unsupported | T1.B |
| C → O | PARTIAL | Eleven guessed shapes failed; correct frame was not retried | No model-visible result | Parse failures were silent with empty receive and no hold artifact | T4.2 (superseded negative sweep), T4.2-RESOLVED |
| O → A | N/A | A exposes no Claude socket | N/A | Receiver type unsupported | T1.A |
| O → B | N/A | B exposes no Claude socket | N/A | Receiver type unsupported | T1.B |
| O → C | PARTIAL | Applicable, exact valid frame unrun | Unknown for exact pair | Shell sender would need C's live socket path | T4.2-RESOLVED |

The generic “Another Claude session” announcement is not provenance. A recipient can audit
its transcript: tmux/operator input is `origin.kind="human"`; native named Claude delivery is
`peer` with name and verified PID; raw socket injection is `peer` with `from="unknown"`, no
name, and a verified injector PID. This evidence is post hoc and not supplied in-band to the
model. Target-not-running behavior, ordering, caps, interrupts, Windows authentication, and
hold/refuse interaction remain untested.

## Provenance answer by transport

- **T-TMUX:** no sender or reply metadata; indistinguishable from the operator both in-band
  and in transcript origin.
- **T-QUEUE:** no model-visible sender or reply metadata; indistinguishable from operator
  `UserInput`. A bare receiver could not identify or answer the sender, and could not
  falsify a forged Claude envelope. A storage-only `client_id` is not exposed to the model.
- **T-CCMSG:** named wrapper and reply address in-band; transcript origin provides the
  stronger post-hoc peer/PID record. Treat neither as permission to perform destructive work.
- **T-SOCK:** misleading generic peer label, no stable sender name, and no reply address
  in-band. Transcript origin detects anonymous injection and identifies the short-lived
  injecting process.

Evidence: T2.AB-idle, T5.B, T3.2-recv, T5.3, and T6-origin.

## Delivery and controls coverage

- FIFO, one-per-idle-transition dispatch, and the two independent Codex inboxes are proven.
- Claude native and socket messages can arrive between tool calls; native messages can also
  start an idle turn. T-TMUX receiver-state races are proven in both TUIs.
- A two-hop native exchange and two A↔C chains stopped at the envelope hop cap. No transport
  throttled them; termination came from convention.
- T7.1 hold/refuse and T7.2 Codex prompt-hook blocking remain `PARTIAL` because both would
  write shared configuration outside the experiment boundary. T7.3 is also `PARTIAL`: the
  native harness supplied the permission-laundering warning and no peer conferred authority,
  but a controlled request to approve or mutate configuration was not executed. Evidence:
  T3.2-recv, T7.1, and T7.B.
- Queue/message cap behavior, target restart, and interrupted-turn retention remain explicit
  unknowns rather than inferred results.

Evidence: T3.1.AB, T3.1.BA, T5.B, T6.B-two-inboxes, T3.3-recv, T6-loop,
T7.1, and T7.B.
