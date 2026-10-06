# Weave engine reference

For authors of weave skills. `scripts/engine.py` runs the deterministic work of
a weave command; the skill body keeps the judgment. Bodies call the engine and
say what to do with its JSON. `scripts/test_engine.py` tests every command.

## Contents

- Running the engine
- Commands
- Session layout
- Lanes and dispatch
- Converting a skill

---

## Running the engine

A skill body defines `<engine>` as the path to `scripts/engine.py`, relative to
its own directory, and runs `python3 <engine> <command>`. It needs Python 3 and
`git` on a POSIX system. Each command prints one JSON object. Exit code 0 is success,
1 is a reported failure (`"ok": false` with `error` or a failure class), 2 is a
usage error. `engine.py --help` lists the commands and
`engine.py <command> --help` the arguments.

## Commands

Session
- `flags --command <name>`: reads the raw arguments on stdin; returns `prompt`,
  `passes`, `variants`, `timeout`, `mode`, `workers`, `judge`, `preamble`,
  `flags`, `timeout_menu`, `passes_recommended`, `notes`, `errors`. The
  per-command defaults live in `PROFILES`.
- `detect`: installed model CLIs, each lane's fallback chain, best search tools.
- `init --command <name> --backend <b>`: creates the session directory, the guard
  snapshot, and the roster. Adds `--mutating` (stash the user's changes first),
  `--variants N`, `--passes N`, `--timeout`, `--prompt-stdin`. `--bare` makes a
  workerless session with no snapshot. Returns `session_dir`, `toplevel`,
  `trunk`, `baseline_sha`, `participants`, `executors`, `artifacts`, `stash`.
- `context [--full-diff] [--diff-limit N]`: `trunk`, `branch`, `commits` on the
  branch, and the repo-state packet sections as `markdown`. Read-only; it needs no
  session.
- `update --session S`: `--status`, `--completed-passes`, `--event` with
  `--event-json`, `--drop <lane>`, `--set key=<json>`, `--link-latest`.
- `pass-dir --session S --pass N`: creates `pass-NNNN` for a later pass.

Prompts and lanes
- `prompt --lane <lane> --file F --out O`: writes the lane's prompt: role
  preamble, body, write ban. `--mutating` drops the ban. `--variant N --of M
  [--preamble-file P]` writes a variant prompt with no role and a built-in or
  custom preamble. `--judge` writes a judge prompt with no role.
- `dispatch --session S --lane agy|gpt --prompt-file F --timeout T`: runs one
  model CLI lane with retry and fallback. Adds `--pass N`, `--mutating`,
  `--variant N --of M`, `--judge`, `--preamble-file`, `--out`, `--stderr`.
  Returns `ok`, `output`, `stderr`, `executor`, `model`, `attempts`,
  `guard_violations`, or `failure_class`.
- `worktrees create|remove --session S --participants a,b [--base pre|head]`:
  per-participant worktrees recorded in `session.json`.
- `capture --session S --pass N --participant P [--tree PATH]`: a participant's
  binary patch, changed-file snapshots, and manifest; the index is not touched.
- `adopt --session S --pass N --pick path=P --delete path`: copies snapshots into
  the main checkout. `--all P` adopts everything `P` captured.
- `reset-main`, `stash-restore`: discard the main tree's changes only when the
  user's stash is recorded and present; pop the session's own stash entry.

Judging
- `labels --session S --pass N --participants a,b [--outputs-dir D]`: random blind
  labels, `label-map.json`, and identity-free copies under `blind/`.
- `judge-plan --session S --mode host|round-robin|panel --pass N`: who judges.
  Each judge's `how` is `host`, `native` (fresh sub-agent), or `external`
  (`dispatch --judge`). A panel reports `feasibility`: `full`, `degraded`, or
  `host-fallback`.
- `judge-parse --file F [--prior F2]`: parses a judge file's scores table;
  returns `columns`, `scores`, `totals`, `winner`, `winner_score`, `errors`.
  With `--prior`, `not_improved` is true when the winner's score did not rise.
- `panel-merge --judge name=path ...`: peer-only averaging over panel judge
  files; returns `merged`, `totals`, `winner` or `tied`, `peers`, and the
  judges whose files did not parse.

Guard
- `guard check --session S [--label L]`: compares the checkout with the
  pre-dispatch snapshot. Never changes it.
- `guard resolve --session S --choice keep|revert|quarantine`: applies the user's
  decision.
- `guard finish --session S`: logs `repo_guard_final`, drops pinned refs when clean.
- `guard prune [--repo R] [--days N]`: drops old pinned refs.

`docs/repo-guard-protocol.md` describes the guard.

## Session layout

`$SESSION_DIR` is `<root>/repos/<repo>/sessions/<command>/<session-id>`, outside
the repository.

- `session.json`, `events.jsonl`, `metadata.md`, `guard-events.jsonl`.
- `context-packet.md`, `original.md` (written by the skill).
- `pass-NNNN/outputs/<participant>.md`, `prompts/`, `stderr/`, `blind/`,
  `label-map.json`, `judges/<participant>.md`; mutating sessions add `diffs/`
  and `files/<participant>/`.
- Variants write `outputs/<participant>-v<N>.md` and `stderr/` at the session root.
- `worktrees/<name>`, `guard/<id>/`.

Participants are `maintainer`, `skeptic`, `builder` under `subagents` and
`claude`, `agy`, `gpt` under `model-clis`. `gpt` runs through `codex`, so never
treat the participant ID as an executable.

## Lanes and dispatch

Each external lane has a fallback chain. A step whose executable is missing is
skipped; the last step is the lesser model.

- `agy`: `agy` (Gemini 3.1 Pro), then `agent` (gemini-3.1-pro), then `agy`
  (Gemini 3.5 Flash).
- `gpt`: `codex`, then `agent` (gpt-5.4-high), then `agent` (gpt-5.4-mini).

Each attempt is classified: `ok`, `timeout`, `rate-limit`, `credit`, `crash`, or
`empty`. A timeout retries once at 1.5 times the limit, a rate limit retries after
10 seconds, an empty answer retries once, a credit or quota error skips the retry
and moves down the chain, and a crash ends the lane. `CREDIT_PATTERNS` in the
engine is the one list of credit-exhaustion strings.

Read-only attempts run in a disposable worktree built from the snapshot.
Mutating attempts run in the lane's registered worktree. A CLI runs with stdin
closed, a process group the timeout kills, and stderr appended to the lane's
stderr file.

## Converting a skill

1. Keep the frontmatter and the `Worker selection` section that cites
   `worker-backends.md`; keep the `ask-user-choice` marker.
2. Add the skill to `PROFILES` when it is new: default timeout, pass and variant
   presets, and boolean flags.
3. Start with `ensemble-core.md` (Start the session), passing the command name.
4. Write the prompt body and the context-packet emphasis; the engine adds roles
   and the write ban.
5. Dispatch with `ensemble-core.md` (Dispatch lanes). Variants add `--variant`;
   judges add `--judge` and use `judge-plan`; a refinement pass starts with
   `pass-dir`. Mutating skills add `--mutating`, `worktrees create`, `capture`,
   `adopt`, `reset-main`, and `stash-restore`.
6. Read-only skills close the guard (Close the repo guard) after the lanes.
7. Judge and synthesize with the shared sections, naming the convergence mode and
   rubric. Deslop and render with `deslop-pass.md` and `present-results.md`.
8. Finish with `ensemble-core.md` (Finish).

Keep the skill's own judgment prose; delete anything the engine or a reference
already says.
