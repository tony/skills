# The trial record

Four sessions — two Codex, two Claude Code — messaging each other on one machine
across every ordered pair and every transport. Read [`30-matrix.md`](30-matrix.md)
for the outcome per pair, [`40-skill-design.md`](40-skill-design.md) for the spec
the skill was written from, and the numbered findings files for the raw
experiments each claim cites.

## Transport names

These files use the labels the trial ran under. The skill and adapters use plain
names. Same transports, one to one:

| In these notes | In the skill | What it is |
|---|---|---|
| `T-QUEUE` | `codex-queue` | `codex queue --thread`, durable and readable from `queue_1.sqlite` |
| `T-CCMSG` | `claude-code-message` | the native `SendMessage` tool between Claude Code sessions |
| `T-SOCK` | `claude-code-socket` | a newline-delimited JSON frame written to a Claude Code inbox socket |
| `T-TMUX` | `tmux` | `tmux send-keys` into the receiver's pane |

The envelope `XSM/1` is `relay/1`, and its stop token `XSM-HALT` is `relay-halt`.
`XSMPROBE` and `XSMSOCK` are neither — they are marker strings carried inside
experiment payloads so a receiver's transcript could be grepped for them.

The notes keep the original labels because the experiment IDs beside them are
cited by name from the adapters and the skill. Renaming here would break those
citations without making any claim easier to check.
