# Goal planner evals

Run six real Claude cases, then check their retained artifacts. A native score
alone does not establish exact printed/saved equality or complete specifications.
All inputs are synthetic. Scaffolds create only owned fixture files; cases have
no network, publication, personal-history, or implementation task.

The cases cover:

- `01-claude-stdout`: a tighter whole-payload limit, Unicode, and no writes.
- `02-save-spec`: default Claude headroom, exact printing, and a complete paired specification.
- `03-synthesize-revisions`: cross-date numbering, unchanged reuse, excluded work, and source injection.
- `04-audit-gates`: missing evidence, known failures, invented guarantees, and excluded acceptance gates.
- `05-profile-consent`: explicit selections, unapproved history candidates, and separate machine bindings.
- `06-codex-long`: uncapped full-text Codex output without files or an unnecessary companion.

Run from this `evals/` directory with the CLI's configured credentials and
keep reports local.
The tool grants permit only each case's declared tools. `--scaffold` runs the
authored fixture scripts; `--trust-plugin` records that the operator reviewed
the plugin and suite. Each case defaults to one run; this command also fixes
one arm and one concurrent agent. The semantic judge uses Sonnet.

```console
$ claude plugin eval .. \
    --ablation none \
    --runs 1 \
    --concurrency 1 \
    --judge-model sonnet \
    --scaffold \
    --allow-tools Bash Write Edit \
    --trust-plugin \
    --keep-temp \
    --no-publish \
    --output-dir results/run
```

The installed CLI supports native regex, file, tool, and LLM graders, but no
custom executable grader. Run [check_results.py](check_results.py) afterward.
It reads the actual final message and retained working directory from each
trace, verifies the saved bytes and companion hash, checks all original
requirements, and rejects changed inputs, unauthorized writes, extra revisions,
or unapproved profile values. It also requires every native grader to pass.
When the CLI seals retained files, the checker temporarily enables read access
to that run's sealed directory and restores its permissions afterward. It reads
artifact data only and never executes files or loads configuration from the fixture.

```console
$ python3 check_results.py \
    results/run/aggregate-result.json
```

For a pilot, add `--case 01-claude-stdout` to both commands and select a new
output directory. Keep unsuccessful reports; do not overwrite them with reruns.
An unexpected judge disagreement requires inspecting the printed evidence and
grader protocol, not deleting the criterion or lowering the pass threshold.

[fixtures.py](fixtures.py) supplies the immutable synthetic source contracts.
[test_goal_eval_checks.py](test_goal_eval_checks.py) checks meaningful negative
controls without model calls: Unicode overflow, newline mismatches, stale
digests, missing requirements despite a valid digest, relative locators,
unnecessary revisions, changed predecessors, executed history instructions,
stdout-only writes, and unapproved preferences. The eval package entry point
is [__init__.py](__init__.py).

```console
$ python3 -m unittest discover \
    -s . \
    -p test_goal_eval_checks.py
```

Leading slash invocations expand the skill before the agent runs, so they may
produce no `Skill` tool event. These cases grade the required helper call or
audit digest and the resulting behavior, rather than asserting that event.
One model run per case provides a reproducible smoke check, not a reliability
estimate; use repeated runs and a with/without comparison for that question.
