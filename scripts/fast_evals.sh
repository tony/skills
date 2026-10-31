#!/usr/bin/env bash
# Routing tripwire: every should-not-fire case plus one trigger case per
# plugin, one run each. Usage: fast_evals.sh [--list]. Scaffolded cases are
# skipped. Needs a logged-in Claude Code. No -e: a failing case is judged by its verdict.
set -uo pipefail

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

# The helpers need Python 3.15, which their PEP 723 header asks uv for.
if ! command -v uv >/dev/null 2>&1; then
  echo "fast_evals.sh: uv is required to run the Python 3.15 helpers" >&2
  exit 2
fi
PY_RUN=(uv run --script)
cd "$SELF_DIR/.."

LIST_ONLY=0
[[ "${1:-}" == "--list" ]] && LIST_ONLY=1

OUT="${FAST_EVAL_OUT:-evals/results/fast}"
THRESHOLD="${FAST_EVAL_THRESHOLD:-0.5}"
MAX_COST="${FAST_EVAL_MAX_COST:-25}"
# A haiku judge misreads a reply that opens by naming what it could not verify.
JUDGE="${FAST_EVAL_JUDGE:-sonnet}"
# Parallel runs share one rate limit and one machine; raise with care.
JOBS="${FAST_EVAL_JOBS:-1}"

specs=()
for eval_dir in plugins/*/evals; do
  [[ -d "$eval_dir" ]] || continue
  plugin="$(basename "$(dirname "$eval_dir")")"
  trigger=""
  routing_trigger=""
  for case_dir in "$eval_dir"/*/; do
    [[ -d "$case_dir" ]] || continue
    name="$(basename "$case_dir")"
    # evals/results/ is not a case directory.
    [[ -f "$case_dir/case.yaml" || -f "$case_dir/prompt.md" ]] || continue
    # A scaffolded case needs tool grants the tripwire does not hand out.
    [[ -f "$case_dir/scaffold.sh" ]] && continue
    # Anchored: "03-negotiate-timeout" is not a should-not-fire case.
    if [[ "$name" == *-neg-* ]]; then
      specs+=("$plugin|$name")
      continue
    fi
    [[ -z "$trigger" ]] && trigger="$name"
    # Prefer a case asserting the skill fired; an artifact-graded case fails
    # for want of write tools and says nothing about routing.
    if [[ -z "$routing_trigger" ]] && grep -hEqs '^[[:space:]]*tool:[[:space:]]*["'"'"']?Skill["'"'"']?[[:space:]]*$' \
      "$case_dir/case.yaml" "$case_dir"/graders/*.md 2>/dev/null; then
      routing_trigger="$name"
    fi
  done
  [[ -n "$routing_trigger" ]] && trigger="$routing_trigger"
  [[ -n "$trigger" ]] && specs+=("$plugin|$trigger")
done

if (( LIST_ONLY )); then
  printf '%s\n' "${specs[@]}"
  echo "${#specs[@]} cases"
  exit 0
fi

# Passes only when complete, error-free, and every Skill-invocation grader
# passed; at a 0.5 threshold a passing answer grader would keep a broken route green.
verdict_for() {
  FAST_EVAL_THRESHOLD="$THRESHOLD" "${PY_RUN[@]}" "$SELF_DIR/fast_evals_verdict.py" "$1"
}

# Durations outlive their results, which are skipped or deleted, so ordering can use them.
TIMINGS="$OUT/.timings.json"

record_timing() {
  FAST_EVAL_TIMINGS="$TIMINGS" "${PY_RUN[@]}" "$SELF_DIR/fast_evals_order.py" \
    --record "$1|$2" "$OUT/$1--$2/aggregate-result.json" 2>/dev/null || true
}

# Without it every per-case log redirect fails.
mkdir -p "$OUT"

# Skip what a previous pass already settled.
pending=()
failed=()
accounted=0
for spec in "${specs[@]}"; do
  plugin="${spec%%|*}"
  case_name="${spec##*|}"
  result="$OUT/$plugin--$case_name/aggregate-result.json"
  if [[ -s "$result" ]]; then
    verdict="$(verdict_for "$result")"
    case "$verdict" in
      pass)
        echo "skip  $plugin/$case_name (scored previously)"
        accounted=$(( accounted + 1 ))
        continue ;;
      incomplete*)
        echo "redo  $plugin/$case_name (${verdict#incomplete: })"
        record_timing "$plugin" "$case_name"
        rm -rf "$OUT/$plugin--$case_name" ;;
      *)
        failed+=("$plugin/$case_name -- ${verdict#fail: }")
        echo "FAIL  $plugin/$case_name (${verdict#fail: })"
        accounted=$(( accounted + 1 ))
        continue ;;
    esac
  fi
  pending+=("$spec")
done

run_case() {
  local plugin="${1%%|*}" case_name="${1##*|}"
  env -u ANTHROPIC_API_KEY claude plugin eval "plugins/$plugin" \
      --case "$case_name" \
      --ablation none \
      --runs 1 \
      --judge-model "$JUDGE" \
      --threshold "$THRESHOLD" \
      --max-cost-usd "$MAX_COST" \
      --trust-plugin \
      --no-publish \
      --output-dir "$OUT/$plugin--$case_name" \
      >"$OUT/$plugin--$case_name.log" 2>&1
}

if (( ${#pending[@]} > 0 )); then
  echo "Running ${#pending[@]} case(s), $JOBS at a time."
  # Longest first, so the slow ensemble case does not straggle alone at the end.
  if (( JOBS > 1 )); then
    # Ordering never filters: take it only if the helper succeeded and returned
    # every case. Command substitution keeps the helper's exit status.
    if ordered_out="$(printf '%s\n' "${pending[@]}" \
        | FAST_EVAL_OUT="$OUT" "${PY_RUN[@]}" "$SELF_DIR/fast_evals_order.py")"; then
      ordered=()
      while IFS= read -r spec; do
        [[ -n "$spec" ]] && ordered+=("$spec")
      done <<<"$ordered_out"
      if (( ${#ordered[@]} == ${#pending[@]} )); then
        pending=("${ordered[@]}")
      else
        echo "warn: ordering returned ${#ordered[@]} of ${#pending[@]} cases; keeping discovery order"
      fi
    else
      echo "warn: ordering helper failed; keeping discovery order"
    fi
  fi
  # Batches, not a `wait -n` pool: macOS bash 3.2 has no `wait -n`.
  batch=()
  for spec in "${pending[@]}"; do
    run_case "$spec" &
    batch+=($!)
    if (( ${#batch[@]} >= JOBS )); then
      wait "${batch[@]}" 2>/dev/null || true
      batch=()
    fi
  done
  (( ${#batch[@]} > 0 )) && { wait "${batch[@]}" 2>/dev/null || true; }

  for spec in "${pending[@]}"; do
    plugin="${spec%%|*}"
    case_name="${spec##*|}"
    record_timing "$plugin" "$case_name"
    verdict="$(verdict_for "$OUT/$plugin--$case_name/aggregate-result.json")"
    accounted=$(( accounted + 1 ))
    if [[ "$verdict" == pass ]]; then
      echo "ok    $plugin/$case_name"
    else
      failed+=("$plugin/$case_name -- ${verdict#*: }")
      echo "FAIL  $plugin/$case_name ($verdict)"
    fi
  done
fi

# Refuse to report success for work that never ran.
if (( accounted != ${#specs[@]} )); then
  echo
  echo "internal error: accounted for $accounted of ${#specs[@]} cases; refusing to report a result"
  exit 1
fi

if (( ${#failed[@]} > 0 )); then
  echo
  echo "${#failed[@]} case(s) below threshold $THRESHOLD:"
  printf '  %s\n' "${failed[@]}"
  exit 1
fi
echo
echo "All ${#specs[@]} cases at or above threshold $THRESHOLD."
