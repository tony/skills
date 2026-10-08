#!/bin/sh
# apply-template.sh — POSIX shell template for the per-run apply.sh of
# /slop:deslop.
#
# `scripts/render_apply.py` renders this file to `<run-dir>/apply.sh`, where `<run-dir>`
# is `git rev-parse --path-format=absolute --git-path deslop/<ts>-<pid>` (so linked worktrees
# work), substituting these placeholders:
#   __REGISTRY_PATH__    — built-in or `--taxonomy=<path>` registry source
#   __REGISTRY_SHA256__  — SHA-256 of the registry at materialization
#   __BASELINE_SHA__     — trunk merge-base SHA at the start of the run
#   __TRUNK_REF__        — `origin/<trunk>`, for the autosquash hint
#
# Each step writes `.checkpoint/<NNNN>.done`; re-runs skip finished
# steps, and removing a marker re-runs that step. Numbered artifacts are
# processed in lexical order; each patch becomes one fixup commit, and
# autosquash folds fixups that share a target.
#
# Fixup and reword commits name their target by full SHA (`fixup! <sha>`,
# `amend! <sha>`), which autosquash resolves exactly; a subject match
# would pick the first of several commits sharing a subject.
#
# A reword step commits with `--allow-empty`: the commit carries only an
# `amend! <sha>` message, and autosquash uses the body verbatim. It
# is the one intentionally empty commit; `reword-map.tsv` records it for
# audit.
#
# A failed fixup commit reverses its patch when the index and worktree
# still match. Overlapping hook or user edits remain for inspection.
#
# The first run creates a backup branch at the starting tip and prints
# `Backup branch: <name>`; re-runs print the same name.
#
# Exit codes:
#   0  all steps complete
#   1  registry SHA-256 changed since materialization, or is unreadable
#   2  working tree is dirty
#   3  `git apply` failed, or the target SHA could not be read from a
#      patch name
#   4  the reword commit failed (for example, a hook rejected it)
#   5  a reword artifact could not be processed
#   6  the fixup commit failed (for example, a hook rejected it)
# Hooks are never bypassed; repair the cause and re-run.

set -eu

run_dir=$(cd "$(dirname -- "$0")" && pwd)
cd "$(git rev-parse --show-toplevel)"
checkpoint_dir="$run_dir/.checkpoint"
mkdir -p "$checkpoint_dir"

# ── registry SHA-256 lock ─────────────────────────────────────────

current_sha256=$(sha256sum -- "__REGISTRY_PATH__" 2>/dev/null | awk '{print $1}')
if [ -z "$current_sha256" ]; then
    current_sha256=$(shasum -a 256 -- "__REGISTRY_PATH__" 2>/dev/null | awk '{print $1}')
fi

if [ -z "$current_sha256" ]; then
    echo "apply.sh: cannot compute SHA-256 of registry __REGISTRY_PATH__" >&2
    exit 1
fi

if [ "$current_sha256" != "__REGISTRY_SHA256__" ]; then
    echo "apply.sh: registry SHA-256 changed since materialization" >&2
    echo "  expected: __REGISTRY_SHA256__" >&2
    echo "  current:  $current_sha256" >&2
    echo "  re-run /slop:deslop to materialize a fresh patch series" >&2
    exit 1
fi

# ── clean-tree precondition ───────────────────────────────────────

if [ -n "$(git status --porcelain)" ]; then
    echo "apply.sh: working tree is dirty; commit or stash first" >&2
    git status --short >&2
    exit 2
fi

# ── backup branch ─────────────────────────────────────────────────
#
# Created once, before the first history change; a re-run reuses it.
# It retains the starting commits, not later uncommitted work.

backup_file="$checkpoint_dir/backup"
if [ -f "$backup_file" ]; then
    backup=$(cat "$backup_file")
else
    current=$(git branch --show-current)
    stem="${current:-detached}-pre-deslop-$(date -u +%Y%m%d-%H%M%S)"
    backup=$stem
    n=1
    while git show-ref --verify --quiet "refs/heads/$backup"; do
        n=$((n + 1))
        backup="$stem-$n"
    done
    git branch "$backup"
    printf '%s\n' "$backup" > "$backup_file"
fi
echo "Backup branch: $backup"

# ── per-step helper ───────────────────────────────────────────────

checkpoint_path() {
    printf '%s/%04d.done' "$checkpoint_dir" "$1"
}

is_done() {
    [ -f "$(checkpoint_path "$1")" ]
}

mark_done() {
    : > "$(checkpoint_path "$1")"
}

# ── patch application loop ────────────────────────────────────────
#
# The target SHA is embedded in each filename
# (`NNNN-fixup-<sha>-<finding-id>.patch`, `NNNN-reword-<sha>.txt`).
# Each patch applies to the tree left by the lower-numbered ones, so
# patches that touch one file must be generated in numeric order.

step_num=0

for entry in "$run_dir"/[0-9]*; do
    [ -e "$entry" ] || continue

    base=$(basename -- "$entry")

    case "$base" in
        0000-*)
            continue
            ;;
    esac

    step_num=$(( step_num + 1 ))

    if is_done "$step_num"; then
        continue
    fi

    case "$base" in
        *-fixup-*.patch)
            target_sha=$(echo "$base" | sed -nE 's/^[0-9]+-fixup-([0-9a-f]+)(-.*)?\.patch$/\1/p')
            if [ -z "$target_sha" ]; then
                echo "apply.sh: cannot extract target SHA from $base" >&2
                exit 3
            fi

            full_sha=$(git rev-parse --verify --quiet "${target_sha}^{commit}") || full_sha=
            if [ -z "$full_sha" ]; then
                echo "apply.sh: target $target_sha is not a commit" >&2
                exit 3
            fi

            if ! git apply --index -- "$entry"; then
                echo "apply.sh: git apply failed on $base" >&2
                echo "  fix the patch (or remove it) and re-run" >&2
                exit 3
            fi

            if git diff --cached --quiet; then
                mark_done "$step_num"
                continue
            fi

            if ! git commit -m "fixup! $full_sha"; then
                echo "apply.sh: fixup commit for $full_sha failed" >&2
                if git apply -R --index -- "$entry"; then
                    echo "  patch rolled back; repair the cause and re-run" >&2
                else
                    echo "  rollback refused overlapping edits; inspect the index and worktree" >&2
                    echo "  patch and backup branch remain available" >&2
                fi
                exit 6
            fi

            mark_done "$step_num"
            ;;

        *-reword-*.txt)
            target_sha=$(echo "$base" | sed -E 's/^[0-9]+-reword-([0-9a-f]+)\.txt$/\1/')
            if [ -z "$target_sha" ]; then
                echo "apply.sh: cannot extract target SHA from $base" >&2
                exit 5
            fi

            mkdir -p "$run_dir/reword"
            cp -- "$entry" "$run_dir/reword/${target_sha}.txt"

            full_sha=$(git rev-parse --verify --quiet "${target_sha}^{commit}") || full_sha=
            if [ -z "$full_sha" ]; then
                echo "apply.sh: cannot resolve $target_sha to a commit" >&2
                exit 5
            fi

            # Autosquash strips the `amend! <sha>` line and uses the
            # rest of the body as the message; no editor runs.
            msg_tmp=$(mktemp "$run_dir/.amend-msg.XXXXXX")
            printf 'amend! %s\n\n' "$full_sha" > "$msg_tmp"
            cat -- "$entry" >> "$msg_tmp"

            map_row=$(printf 'amend! %s\t%s\treword/%s.txt' \
                "$full_sha" "$target_sha" "$target_sha")
            echo "$map_row" >> "$run_dir/reword-map.tsv"

            if ! git commit --allow-empty -F "$msg_tmp"; then
                rm -f -- "$msg_tmp"
                echo "apply.sh: git commit reword for $target_sha failed" >&2
                echo "  if a hook rejected the commit, repair and re-run" >&2
                exit 4
            fi

            rm -f -- "$msg_tmp"
            mark_done "$step_num"
            ;;

        *)
            echo "apply.sh: unrecognized artifact $base — skipping" >&2
            mark_done "$step_num"
            ;;
    esac
done

echo "apply.sh: $step_num steps complete"
echo "apply.sh: fixup commits visible via: git log --oneline '__BASELINE_SHA__..HEAD'"
echo "apply.sh: to autosquash, run /slop:deslop --apply-rebase or:"
echo "          GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash __TRUNK_REF__"
