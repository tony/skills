#!/usr/bin/env bash
# A two-PR stack (#31 on main, #32 on #31's branch) with a stub gh. Each
# gh pr merge call is appended to merge.log and squash-merges the PR's
# branch into origin main; pr view reports state from merge.log and the
# remote. gh pr edit is appended to edit.log and retargets #32 to main.
set -euo pipefail

export GIT_AUTHOR_NAME=demo GIT_AUTHOR_EMAIL=demo@example.invalid
export GIT_COMMITTER_NAME=demo GIT_COMMITTER_EMAIL=demo@example.invalid
git init -q -b main
git config user.name demo
git config user.email demo@example.invalid
seq 1 20 >lines.txt
git add lines.txt
git commit -q -m 'Initial commit'
git init -q --bare origin.git
git remote add origin ./origin.git
git push -q origin main

git checkout -q -b stack-1
echo one >one.txt
git add one.txt
git commit -q -m 'Add one'
git checkout -q -b stack-2
echo two >two.txt
git add two.txt
git commit -q -m 'Add two'
git push -q origin stack-1 stack-2
git checkout -q main

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
export GIT_AUTHOR_NAME=demo GIT_AUTHOR_EMAIL=demo@example.invalid
export GIT_COMMITTER_NAME=demo GIT_COMMITTER_EMAIL=demo@example.invalid
O="git --git-dir=origin.git"
head_of() { [ "$1" = 31 ] && echo stack-1 || echo stack-2; }
merged() { [ -f merge.log ] && grep -q "pr merge #\?$1 " merge.log; }
case "$1 $2" in
  "pr list")
    echo '[{"number":31,"title":"Add one","headRefName":"stack-1","baseRefName":"main","isDraft":false},{"number":32,"title":"Add two","headRefName":"stack-2","baseRefName":"stack-1","isDraft":false}]'
    ;;
  "pr view")
    n=${3#\#}
    br=$(head_of "$n")
    base=main
    if [ "$n" = 32 ] && ! { [ -f edit.log ] && grep -q . edit.log; }; then base=stack-1; fi
    state=OPEN merged='"mergedAt":null,"mergeCommit":null'
    if merged "$n"; then
      state=MERGED
      merged='"mergedAt":"2026-01-01T00:00:00Z","mergeCommit":{"oid":"'$($O rev-parse main)'"}'
    fi
    ms=CLEAN
    if [ "$n" = 32 ] && ! $O merge-base --is-ancestor main stack-2; then ms=BEHIND; fi
    cat <<JSON
{"number":$n,"title":"PR $n","url":"https://example.invalid/pull/$n","state":"$state",$merged,"isDraft":false,"baseRefName":"$base","headRefName":"$br","headRefOid":"$($O rev-parse "$br")","mergeable":"MERGEABLE","mergeStateStatus":"$ms","reviewDecision":"APPROVED","isCrossRepository":false,"maintainerCanModify":true,"commits":[{"messageHeadline":"PR $n"}]}
JSON
    ;;
  "pr checks") echo "build	pass	1m	https://example.invalid/run/1" ;;
  "pr edit") echo "$*" >>edit.log ;;
  "pr checkout") git checkout -q "$(head_of "${3#\#}")" ;;
  "repo view") echo '{"mergeCommitAllowed":true,"squashMergeAllowed":true,"rebaseMergeAllowed":true}' ;;
  "pr merge")
    echo "$*" >>merge.log
    n=${3#\#}
    br=$(head_of "$n")
    c=$($O commit-tree "$($O rev-parse "$br^{tree}")" -p main -m "Squash PR $n (#$n)")
    $O update-ref refs/heads/main "$c"
    ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
