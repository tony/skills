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
spike.sh untracked [--leave PATHSPEC]...
spike.sh stash [--keep] [--leave PATHSPEC]... -F FILE|-
spike.sh save-user
spike.sh hold-user
spike.sh stash-on-top USER_SHA [--leave PATHSPEC]... -F FILE|-
spike.sh restore USER_SHA
spike.sh delta USER_SHA [SPIKE_SHA]
spike.sh replay-apply SPIKE_SHA [USER_SHA]
spike.sh drop SHA
spike.sh branch-start NAME
spike.sh branch-end ORIG NAME
spike.sh teardown WORKTREE STASH_SHA|none
USAGE
}

# Refuse a missing repository, an empty history, or a root that contains $HOME:
# a dotfile repository at home would sweep credentials into `git add -A`.
cmd_guard() {
  git rev-parse --verify HEAD >/dev/null 2>&1 || die "no repository or no commits"
  local top home
  top=$(git rev-parse --show-toplevel)
  [ -n "${HOME:-}" ] || die "HOME is not set; cannot tell whether the repository contains it"
  home=$(cd "$HOME" 2>/dev/null && pwd -P) || die "HOME is not a directory: $HOME"
  case "$home/" in
    "${top%/}"/*) die "repository root contains home: $top" ;;
  esac
  # save-user's add -A plus reset --hard would erase an operation's state.
  local op
  for op in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
    [ ! -e "$(git rev-parse --git-path "$op")" ] || die "$op present: finish or abort that operation first"
  done
  [ -z "$(git ls-files -u)" ] || die "unmerged paths: resolve them first"
  echo ok
}

# The git directory's spike/ folder; a private temp directory when the git
# directory refuses the write (sandboxed hosts).
cmd_ledger_dir() {
  local d
  d="$(git rev-parse --path-format=absolute --git-common-dir)/spike"
  if mkdir -p "$d" 2>/dev/null && [ -w "$d" ]; then
    echo "$d"
  else
    mktemp -d "${TMPDIR:-/tmp}/spike-ledger.XXXXXX"
  fi
}

# Bytecode is never source; a stash that swept it in would also carry it into
# a replay. Ignored files are already skipped by `git add -A`.
BYTECODE=(':(top,exclude,glob)**/__pycache__/**' ':(top,exclude,glob)**/*.pyc')
SPECS=()
KEEP=0
MSG=""
LOCK_FILE=""

# The message comes from a file (or stdin with "-"), never a shell argument:
# a goal mined from a trace may hold $(...) or backticks. Newlines collapse.
read_message() {
  local raw
  if [ "$1" = "-" ]; then
    raw=$(cat)
  else
    [ -f "$1" ] || die "message file not found: $1" 2
    raw=$(cat "$1")
  fi
  MSG=$(printf '%s' "$raw" | tr '\r\n' '  ')
  [ -n "${MSG// /}" ] || die "stash message is empty" 2
}

# Sets KEEP, SPECS (pathspecs for `git add`/`ls-files`) and, with -F, MSG.
parse_stash_args() {
  SPECS=(':/' "${BYTECODE[@]}")
  KEEP=0
  MSG=""
  local want_msg=$1
  shift
  while [ $# -gt 0 ]; do
    case "$1" in
      --keep) KEEP=1 ;;
      --leave)
        [ $# -ge 2 ] || die "--leave needs PATHSPEC" 2
        SPECS+=(":(top,exclude)$2")
        shift
        ;;
      -F)
        [ $# -ge 2 ] || die "-F needs FILE or -" 2
        read_message "$2"
        shift
        ;;
      *) die "unknown argument: $1" 2 ;;
    esac
    shift
  done
  if [ "$want_msg" = 1 ] && [ -z "$MSG" ]; then
    die "needs -F FILE (the message is never a shell argument)" 2
  fi
}

# Stashes share one stack, so two at once would interleave their SHAs.
acquire_lock() {
  [ -z "$LOCK_FILE" ] || return 0
  local dir f pid common
  common=$(git rev-parse --path-format=absolute --git-common-dir)
  dir="$common/spike"
  if ! { mkdir -p "$dir" 2>/dev/null && [ -w "$dir" ]; }; then
    dir="${TMPDIR:-/tmp}/spike-lock.$(printf '%s' "$common" | cksum | cut -d' ' -f1)"
    mkdir -p "$dir" || die "cannot create a lock directory"
  fi
  f="$dir/stash.lock"
  if ! (set -C; echo "$$" >"$f") 2>/dev/null; then
    pid=$(cat "$f" 2>/dev/null || true)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      die "another spike.sh is stashing (pid $pid); stash one at a time"
    fi
    rm -f "$f"
    (set -C; echo "$$" >"$f") 2>/dev/null || die "another spike.sh is stashing; stash one at a time"
  fi
  LOCK_FILE=$f
  trap 'rm -f "$LOCK_FILE"' EXIT
}

# Paths a stash would sweep in that no ignore rule covers: build output and
# logs show up here, before they travel with the spike.
cmd_untracked() {
  parse_stash_args 0 "$@"
  git ls-files --others --exclude-standard -- "${SPECS[@]}"
}

# Stash everything, untracked files included, and print the stash's own SHA
# (never stash@{0}, which is another entry when nothing changed). With --keep
# the files stay in the tree, unstaged, so a kept worktree still shows the work.
# Paths matched by --leave or the bytecode patterns stay in the tree.
cmd_stash() {
  parse_stash_args 1 "$@"
  cmd_guard >/dev/null
  acquire_lock
  git add -A -- "${SPECS[@]}"
  local sha
  sha=$(git stash create "$MSG")
  if [ -z "$sha" ]; then
    git reset -q
    echo "no changes"
  else
    git stash store -m "$MSG" "$sha"
    if [ "$KEEP" -eq 1 ]; then
      git reset -q
    else
      git reset -q --hard
    fi
    echo "$sha"
  fi
}

cmd_save_user() {
  cmd_guard >/dev/null
  acquire_lock
  git add -A
  local sha
  sha=$(git stash create "$USER_MSG")
  if [ -z "$sha" ]; then
    echo "no changes"
  else
    git stash store -m "$USER_MSG" "$sha"
    git reset -q --hard
    echo "$sha"
  fi
}

# Save the user's work as a stash but leave the files in the tree.
cmd_hold_user() {
  cmd_guard >/dev/null
  acquire_lock
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
# Prints the spike stash SHA first, so a refused restore still reports it, or "no changes" when the spike added nothing.
cmd_stash_on_top() {
  [ $# -ge 1 ] || die "stash-on-top needs USER_SHA and -F FILE" 2
  local user=$1
  shift
  parse_stash_args 1 "$@"
  cmd_guard >/dev/null
  acquire_lock
  git add -A -- "${SPECS[@]}"
  local spike
  spike=$(git stash create "$MSG")
  if [ -z "$spike" ] || git diff --quiet "$user" "$spike"; then
    git reset -q
    echo "no changes"
    return
  fi
  git stash store -m "$MSG" "$spike"
  echo "$spike"
  git reset -q --hard
  cmd_restore "$user"
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

# Without SPIKE_SHA, diff the current tree (untracked files included) against
# the user's stash: the spike's changes when it was never stashed.
cmd_delta() {
  [ $# -ge 1 ] && [ $# -le 2 ] || die "delta needs USER_SHA [SPIKE_SHA]" 2
  if [ $# -eq 2 ]; then
    git diff "$1" "$2"
    return
  fi
  git add -A
  git diff --cached "$1"
  git reset -q
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

# Drop a stash by SHA, full or abbreviated. Indexes shift as entries drop, so
# match the resolved SHA, and never drop the saved user work.
cmd_drop() {
  [ $# -eq 1 ] || die "drop needs SHA" 2
  local line ref full
  full=$(git rev-parse --verify --quiet "$1^{commit}" || true)
  if [ -z "$full" ]; then
    echo "already gone"
    return
  fi
  line=$(git stash list --format='%H %gd %gs' | awk -v sha="$full" '$1 == sha && !found {print; found = 1}')
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

# Remove a stashed worktree only when no source changes remain.
# Bytecode and ignored build output may require --force.
cmd_teardown() {
  [ $# -eq 2 ] || die "teardown needs WORKTREE and STASH_SHA (or none)" 2
  if [ "$2" != none ]; then
    local full
    full=$(git rev-parse --verify --quiet "$2^{commit}" || true)
    [ -n "$full" ] && git stash list --format='%H' | awk -v sha="$full" '$0 == sha {found = 1} END {exit !found}' ||
      die "no stash $2; stash the work before removing $1"
    git merge-base --is-ancestor "$(git -C "$1" rev-parse HEAD)" "$full" ||
      die "worktree has commits absent from stash $2: $1"
  else
    [ -n "$(git for-each-ref --count=1 --contains "$(git -C "$1" rev-parse HEAD)")" ] ||
      die "worktree has commits reachable from no ref: $1"
  fi
  git -C "$1" diff --cached --quiet || die "worktree holds unstashed staged changes: $1"
  [ -z "$(git -C "$1" ls-files --modified --others --exclude-standard -- ':/' "${BYTECODE[@]}")" ] ||
    die "worktree holds unstashed changes: $1"
  local left
  left=$(git -C "$1" ls-files --others --ignored --exclude-standard --directory -- ':/' "${BYTECODE[@]}")
  [ -z "$left" ] || printf '%s\n' "$left" | sed 's/^/spike.sh: removing ignored /' >&2
  git worktree remove "$1" 2>/dev/null || git worktree remove --force "$1" || true
  git worktree prune
  local abs
  abs=$(cd "$(dirname "$1")" 2>/dev/null && pwd -P)/$(basename "$1") || abs=$1
  if git worktree list --porcelain | awk -v target="$1" -v absolute="$abs" '
    /^worktree / {path = substr($0, 10); if (path == target || path == absolute) found = 1}
    END {exit !found}'; then
    die "worktree still listed: $1"
  fi
  echo removed
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
    untracked) cmd_untracked "$@" ;;
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
    teardown) cmd_teardown "$@" ;;
    -h | --help | help) usage ;;
    *) usage >&2; exit 2 ;;
  esac
}

main "$@"
