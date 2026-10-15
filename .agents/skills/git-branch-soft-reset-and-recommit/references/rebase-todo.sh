#!/bin/sh
# Drives git rebase -i with no editor and no TTY; every mode finishes or fails
# loudly. Exit: 0 success, 1 git failed (state may be left in progress), 2 refusal.

# RECUT_UPDATE_REFS=1 also moves local branches pointing into the range;
# RECUT_SIGN=1 re-signs rewritten commits, which a rebase strips.

set -eu

die() { printf '%s\n' "$*" >&2; exit 2; }
note() { printf '%s\n' "$*" >&2; }

git_dir_path() { git rev-parse --git-path "$1"; }

in_progress() {
    for f in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG sequencer; do
        if [ -e "$(git_dir_path "$f")" ]; then
            printf '%s\n' "$f"
            return 0
        fi
    done
    return 1
}

preflight() {
    git rev-parse --verify --quiet HEAD >/dev/null || die "refusing: no commits in this repository"
    if op=$(in_progress); then
        die "refusing: a git operation is already in progress ($op). Finish or abort it first."
    fi
    [ -z "$(git status --porcelain --untracked-files=no)" ] ||
        die "refusing: the working tree has uncommitted changes. Commit, stash, or discard them first."
}

# Pinned against user config that would otherwise change the todo format
# (rebaseMerges), hide dropped commits (missingCommitsCheck), or silently
# stash a dirty tree (autoStash).
rebase() {
    set -- -c rebase.rebaseMerges=false \
           -c rebase.missingCommitsCheck=error \
           -c rebase.autoStash=false "$@"
    [ "${RECUT_SIGN:-0}" = 1 ] && set -- -c commit.gpgSign=true "$@"
    GIT_EDITOR=false git "$@"
}

update_refs_flag() {
    [ "${RECUT_UPDATE_REFS:-0}" = 1 ] && printf '%s' --update-refs
}

report_state() {
    if op=$(in_progress); then
        note ""
        note "The rebase stopped and is still in progress ($op)."
        note "Inspect it, or discard the attempt with:  git rebase --abort"
    fi
}

case "${1:-}" in
status)
    if op=$(in_progress); then
        printf 'in progress: %s\n' "$op"
    else
        printf 'clean: no git operation in progress\n'
    fi
    ;;

show)
    # Generated directly rather than by driving a throwaway rebase: running
    # one to read its todo replays every commit and changes their SHAs.
    [ $# -eq 2 ] || die "usage: rebase-todo.sh show <base>"
    git rev-parse --verify --quiet "$2" >/dev/null || die "not a valid base: $2"
    git log --reverse --no-merges --format='pick %h %s' "$2"..HEAD
    ;;

apply)
    [ $# -eq 3 ] || die "usage: rebase-todo.sh apply <base> <plan-file>"
    [ -f "$3" ] || die "no such plan file: $3"
    preflight
    # Passed through the environment, not interpolated into the editor string:
    # git runs the sequence editor as `sh -c '<editor> "$@"' <editor> <todo>`,
    # so a path containing a quote would break the string it was spliced into.
    RECUT_PLAN=$(cd "$(dirname -- "$3")" && pwd)/$(basename -- "$3")
    export RECUT_PLAN
    GIT_SEQUENCE_EDITOR='cp -- "$RECUT_PLAN"' rebase rebase -i $(update_refs_flag) "$2" || {
        report_state; exit 1;
    }
    ;;

verify)
    [ $# -eq 3 ] || die "usage: rebase-todo.sh verify <base> <command>"
    preflight
    # --keep-base pins the base: without it this rebases onto <base> as a side
    # effect and silently drops commits that become empty.
    rebase rebase --keep-base --exec "$3" "$2" || { report_state; exit 1; }
    ;;

squash)
    [ $# -eq 2 ] || die "usage: rebase-todo.sh squash <base>"
    preflight
    GIT_SEQUENCE_EDITOR=true rebase rebase -i --autosquash $(update_refs_flag) "$2" || {
        report_state; exit 1;
    }
    ;;

*)
    die "usage: rebase-todo.sh {status|show <base>|apply <base> <plan>|verify <base> <cmd>|squash <base>}"
    ;;
esac
