# Goal planner evals

Run the six workflow cases and a denied-save control, then check their retained artifacts. Native graders
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
- `07-denied-save`: blocked allocation prints the complete unsaved goal and
  specification, preserves the blocker, and performs no fallback writes.

From this directory, run one arm and one concurrent agent, keeping reports local.
`--scaffold` runs the authored fixture scripts; `--trust-plugin` confirms that
those scripts and the plugin were reviewed. Tool grants respect each case's
restrictions. The semantic judge uses Opus.

Inspect `claude plugin eval --help` first. Use an absolute, new output directory
outside the repository. On Linux, select a short owned temporary root outside
common temporary directories if the runner's write-deny policy covers its own
fixture. Keep sandbox enforcement unchanged. A long root can exceed Unix socket
pathname limits.

Create a short owned root for this run:

```console
$ eval_tmp_root=$(mktemp -d "$HOME/.goal-eval.XXXXXX")
```

```console
$ TMPDIR="$eval_tmp_root" claude plugin eval .. \
    --ablation none \
    --runs 1 \
    --concurrency 1 \
    --judge-model opus \
    --scaffold \
    --allow-tools Bash Write Edit \
    --trust-plugin \
    --keep-temp \
    --no-publish \
    --output-dir <absolute-report-directory>
```

The CLI has no custom executable grader, so run the artifact postcheck separately:

```console
$ python3 check_results.py \
    <absolute-report-directory>/aggregate-result.json
```

The checker requires complete native grades and a successful final result. It
reads retained artifacts without executing them. For owned sealed directories,
it temporarily enables read access and restores the original permissions.
Saved workflows may use scratch files within their fixture; stdout and profile
cases reject extra writes. The count sentence follows the product's output
contract. Only the direct-call evidence convention is specific to these fixtures.

For save cases, retain `draft.json`; synthesis also retains `next-day.json`,
identical except for its requested date. Call the public helper directly in
separate Bash calls and leave JSON results unmodified on stdout. The checker
links those actual commands to results, verifies both actual requested dates
from public result fields as well as the retained requests, then
checks printed/saved identity and the complete artifact inventory. Option order
and Python executable spelling can vary. Shell wrappers or redirected summaries
leave this controlled probe unverified; they are not product failures. Echoed
JSON, an unlinked result, or a missing second render cannot establish reuse.

Native semantic judges read complete final replies or saved specifications.
Their separate handoff-only trace check sees only the runner's first/last events;
review the complete retained trace for forbidden execution. The postcheck uses
that complete trace for publication evidence, avoiding native trace sampling.

Add `--case 01-claude-stdout` to both commands for a pilot. Always choose a new
output directory and retain unsuccessful reports. A failed native write does not
justify bypassing its execution sandbox or claiming success. The denied-save
control places an immutable regular file at `Documents/.goal-reservations`, so
normal public allocation fails after constructing the payload. The model must
then print the complete goal and authored specification without more tool calls.

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
