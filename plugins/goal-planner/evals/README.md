# Goal planner evals

Run six real Claude cases, then check their retained artifacts. Native graders
judge meaning and tool behavior; [check_results.py](check_results.py) checks exact
counts, printed/saved bytes, full source content, companion hashes, revisions,
and consent. Inputs from [fixtures.py](fixtures.py) are synthetic and local.

- `01-claude-stdout`: a tighter limit, Unicode counts, and no writes.
- `02-save-spec`: Claude headroom and a complete paired specification.
- `03-synthesize-revisions`: cross-date numbering and reuse, current exclusions,
  preserved failures, and inert generated history.
- `04-audit-gates`: missing evidence, known failures, and false blockers.
- `05-profile-consent`: explicit selections and separate machine bindings.
- `06-codex-long`: the complete uncapped source without files or a companion.

From this directory, run one arm and one concurrent agent, keeping reports local.
`--scaffold` runs the authored fixture scripts; `--trust-plugin` confirms that
those scripts and the plugin were reviewed. Tool grants respect each case's
restrictions. The semantic judge uses Sonnet.

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

The CLI has no custom executable grader, so run the artifact postcheck separately:

```console
$ python3 check_results.py \
    results/run/aggregate-result.json
```

The checker requires complete native grades and a successful final result. It
reads retained artifacts without executing them. For owned sealed directories,
it temporarily enables read access and restores the original permissions.
Saved workflows may use scratch files; stdout and profile cases reject extra
writes. The requested count sentence belongs to these fixtures, not the product's
output contract. Reuse is checked against linked tool results and judged against
the actual trace, without requiring a helper filename or shell spelling.

Add `--case 01-claude-stdout` to both commands for a pilot. Always choose a new
output directory and retain unsuccessful reports. Historical Claude 2.1.310 runs
of cases 03 and 05 encountered native write `Errno 30`; those receipts remain
UNVERIFIED for their artifact obligations. A failed native write does not justify
bypassing its execution sandbox or claiming success.

[test_goal_eval_checks.py](test_goal_eval_checks.py) supplies offline corruption
controls for counts, missing/truncated output, stale hashes, incomplete companions,
fake reuse, changed inputs, unauthorized writes, consent, and false completion.
The package entry point is [__init__.py](__init__.py).

```console
$ python3 -m unittest discover \
    -s . \
    -p test_goal_eval_checks.py
```

A single model run is a smoke check. Reliability claims need repeated runs and a
with/without comparison; a judge disagreement needs evidence review.
