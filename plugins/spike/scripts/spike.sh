#!/usr/bin/env bash
# Deterministic git plumbing for the spike skills: repository guard, stash
# sequences that report their own SHA, user-work save and restore, and the
# spike-only replay. Portable across GNU and BSD/Darwin; needs git.
set -euo pipefail

USER_MSG="user work before spike"

die() { printf 'spike.sh: %s\n' "$1" >&2; exit "${2:-1}"; }

usage() {
  cat <<'USAGE'
spike.sh guard
spike.sh ledger-dir
spike.sh stash MESSAGE
spike.sh save-user
spike.sh hold-user
spike.sh stash-on-top USER_SHA MESSAGE
spike.sh restore USER_SHA
spike.sh delta USER_SHA SPIKE_SHA
spike.sh replay-apply SPIKE_SHA [USER_SHA]
spike.sh drop SHA
spike.sh branch-start NAME
spike.sh branch-end ORIG NAME
USAGE
}

# Refuse a missing repository, an empty history, or a root that contains $HOME:
# a dotfile repository at home would sweep credentials into `git add -A`.
cmd_guard() {
  git rev-parse --verify HEAD >/dev/null 2>&1 || die "no repository or no commits"
  local top home
  top=$(git rev-parse --show-toplevel)
  home=$(cd "$HOME" && pwd -P)
  case "$home/" in
    "${top%/}"/*) die "repository root contains home: $top" ;;
  esac
  echo ok
}

cmd_ledger_dir() {
  local d
  d="$(git rev-parse --path-format=absolute --git-common-dir)/spike"
  mkdir -p "$d"
  echo "$d"
}

# Stash everything, untracked files included, and print the stash's own SHA
# (never stash@{0}, which is another entry when nothing changed).
cmd_stash() {
  [ $# -eq 1 ] || die "stash needs MESSAGE" 2
  cmd_guard >/dev/null
  git add -A
  local sha
  sha=$(git stash create "$1")
  if [ -z "$sha" ]; then
    echo "no changes"
  else
    git stash store -m "$1" "$sha"
    git reset -q --hard
    echo "$sha"
  fi
}

cmd_save_user() { cmd_stash "$USER_MSG"; }

# Save the user's work as a stash but leave the files in the tree.
cmd_hold_user() {
  cmd_guard >/dev/null
  git add -A
  local sha
  sha=$(git stash create "$USER_MSG")
  if [ -z "$sha" ]; then
    echo "no changes"
  else
    git stash store -m "$USER_MSG" "$sha"
    git reset -q
    echo "$sha"
  fi
}

# Stash a spike probed on top of the user's work and put that work back.
# Prints the spike stash SHA, or "no changes" when the spike added nothing.
cmd_stash_on_top() {
  [ $# -eq 2 ] || die "stash-on-top needs USER_SHA and MESSAGE" 2
  cmd_guard >/dev/null
  git add -A
  local spike
  spike=$(git stash create "$2")
  if [ -z "$spike" ] || git diff --quiet "$1" "$spike"; then
    git reset -q
    echo "no changes"
    return
  fi
  git stash store -m "$2" "$spike"
  git reset -q --hard
  cmd_restore "$1"
  echo "$spike"
}

# Reapply the user's stash and unstage it. A refused apply changes nothing and
# the stash stays: it is the only copy.
cmd_restore() {
  [ $# -eq 1 ] || die "restore needs USER_SHA" 2
  if ! git stash apply -q "$1"; then
    die "restore refused; your work is still in stash $1 and nothing was dropped"
  fi
  git reset -q
}

cmd_delta() {
  [ $# -eq 2 ] || die "delta needs USER_SHA and SPIKE_SHA" 2
  git diff "$1" "$2"
}

# Apply only the spike's own changes. With USER_SHA the spike stash also holds
# the user's edits, so replay the difference instead of the whole stash.
cmd_replay_apply() {
  [ $# -ge 1 ] && [ $# -le 2 ] || die "replay-apply needs SPIKE_SHA [USER_SHA]" 2
  if [ $# -eq 1 ]; then
    git stash apply -q "$1" || die "apply refused; stash $1 is untouched"
    git reset -q
    return
  fi
  local patch
  patch=$(mktemp "${TMPDIR:-/tmp}/spike-delta.XXXXXX")
  git diff --binary "$2" "$1" >"$patch"
  if git apply --check "$patch" 2>/dev/null; then
    git apply "$patch"
    rm -f "$patch"
  else
    rm -f "$patch"
    die "the delta does not apply to this tree; stash $1 is untouched"
  fi
}

# Drop a stash by SHA. Indexes shift as entries drop, so match the SHA, and
# never drop the saved user work.
cmd_drop() {
  [ $# -eq 1 ] || die "drop needs SHA" 2
  local line ref
  line=$(git stash list --format='%H %gd %gs' | awk -v sha="$1" '$1 == sha && !found {print; found = 1}')
  if [ -z "$line" ]; then
    echo "already gone"
    return
  fi
  case "$line" in
    *"$USER_MSG"*) die "refusing to drop the saved user work: $1" ;;
  esac
  ref=$(printf '%s' "$line" | awk '{print $2}')
  git stash drop -q "$ref"
  echo dropped
}

cmd_branch_start() {
  [ $# -eq 1 ] || die "branch-start needs NAME" 2
  local orig
  orig=$(git branch --show-current)
  [ -n "$orig" ] || orig=$(git rev-parse HEAD)
  git switch -q -c "$1" || die "cannot create branch $1; choose another name"
  echo "$orig"
}

cmd_branch_end() {
  [ $# -eq 2 ] || die "branch-end needs ORIG and NAME" 2
  if git show-ref --verify --quiet "refs/heads/$1"; then
    git switch -q "$1"
  else
    git switch -q --detach "$1"
  fi
  git branch -q -d "$2"
}

main() {
  [ $# -ge 1 ] || { usage >&2; exit 2; }
  local sub="$1"
  shift
  case "$sub" in
    guard) cmd_guard "$@" ;;
    ledger-dir) cmd_ledger_dir "$@" ;;
    stash) cmd_stash "$@" ;;
    save-user) cmd_save_user "$@" ;;
    hold-user) cmd_hold_user "$@" ;;
    stash-on-top) cmd_stash_on_top "$@" ;;
    restore) cmd_restore "$@" ;;
    delta) cmd_delta "$@" ;;
    replay-apply) cmd_replay_apply "$@" ;;
    drop) cmd_drop "$@" ;;
    branch-start) cmd_branch_start "$@" ;;
    branch-end) cmd_branch_end "$@" ;;
    -h | --help | help) usage ;;
    *) usage >&2; exit 2 ;;
  esac
}

main "$@"
