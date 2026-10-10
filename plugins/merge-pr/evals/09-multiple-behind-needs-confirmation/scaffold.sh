#!/usr/bin/env bash
# A stub gh for approved PRs #42 (feature/parser) and #43 (feature/lexer), both
# BEHIND: main has a commit the branches lack. pr checkout switches branch.
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
git checkout -q -b feature/lexer
echo lexer >lexer.txt
git add lexer.txt
git commit -q -m 'Add the lexer'
git push -q origin feature/lexer
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
    case "$3" in
      42) b=feature/parser; t="Add the parser" ;;
      *) b=feature/lexer; t="Add the lexer" ;;
    esac
    ms=CLEAN
    if ! $O merge-base --is-ancestor main "$b"; then ms=BEHIND; fi
    cat <<JSON
{"number":$3,"title":"$t","url":"https://example.invalid/pull/$3","state":"OPEN","mergedAt":null,"mergeCommit":null,"isDraft":false,"baseRefName":"main","headRefName":"$b","headRefOid":"$($O rev-parse "$b")","mergeable":"MERGEABLE","mergeStateStatus":"$ms","reviewDecision":"APPROVED","isCrossRepository":false,"maintainerCanModify":true,"commits":[{"messageHeadline":"$t"}]}
JSON
    ;;
  "pr list") echo '[{"number":42,"title":"Add the parser","headRefName":"feature/parser","baseRefName":"main","isDraft":false},{"number":43,"title":"Add the lexer","headRefName":"feature/lexer","baseRefName":"main","isDraft":false}]' ;;
  "pr checks") echo "build	pass	1m	https://example.invalid/run/1" ;;
  "pr checkout") if [ "$3" = 42 ]; then git checkout -q feature/parser; else git checkout -q feature/lexer; fi ;;
  "repo view") echo '{"mergeCommitAllowed":true,"squashMergeAllowed":true,"rebaseMergeAllowed":true}' ;;
  "pr merge") echo "$*" >>merge.log ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
