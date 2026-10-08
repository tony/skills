#!/usr/bin/env bash
# A stub gh for one approved PR (#42, branch feature/parser) that is BEHIND:
# main has a commit the branch lacks. pr checkout switches to the branch.
# Any gh pr merge call is appended to merge.log.
set -euo pipefail

git init -q -b main
git config user.name demo
git config user.email demo@example.invalid
seq 1 20 >lines.txt
git add lines.txt
git commit -q -m 'Initial commit'
git init -q --bare origin.git
git remote add origin ./origin.git
git push -q origin main

git checkout -q -b feature/parser
echo parser >parser.txt
git add parser.txt
git commit -q -m 'Add the parser'
git push -q origin feature/parser
git checkout -q main
echo news >news.txt
git add news.txt
git commit -q -m 'Add news (#7)'
git push -q origin main

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
O="git --git-dir=origin.git"
case "$1 $2" in
  "pr view")
    ms=CLEAN
    if ! $O merge-base --is-ancestor main feature/parser; then ms=BEHIND; fi
    cat <<JSON
{"number":42,"title":"Add the parser","url":"https://example.invalid/pull/42","state":"OPEN","mergedAt":null,"mergeCommit":null,"isDraft":false,"baseRefName":"main","headRefName":"feature/parser","headRefOid":"$($O rev-parse feature/parser)","mergeable":"MERGEABLE","mergeStateStatus":"$ms","reviewDecision":"APPROVED","isCrossRepository":false,"maintainerCanModify":true,"commits":[{"messageHeadline":"Add the parser"}]}
JSON
    ;;
  "pr checks") echo "build	pass	1m	https://example.invalid/run/1" ;;
  "pr checkout") git checkout -q feature/parser ;;
  "repo view") echo '{"mergeCommitAllowed":true,"squashMergeAllowed":true,"rebaseMergeAllowed":true}' ;;
  "pr merge") echo "$*" >>merge.log ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
