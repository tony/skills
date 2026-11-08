#!/usr/bin/env bash
# A stub gh for one ready PR in a repo whose history is squash-merged with
# (#N) subjects. Every gh pr merge call is appended to merge.log; after one
# is logged, pr view reports the PR as MERGED.
set -euo pipefail

git init -b main >/dev/null
git config user.name demo
git config user.email demo@example.invalid
echo "# demo" >README.md
git add README.md
git commit -q -m 'Initial commit'
for n in 1 2 3; do
  echo "$n" >"f$n.txt"
  git add "f$n.txt"
  git commit -q -m "parser(feat[lexer]) Add stage $n (#$n)"
done
git init -q --bare origin.git
git remote add origin ./origin.git
git push -q origin main

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "pr view")
    if [ -f merge.log ]; then
      state=MERGED
      merged='"mergedAt":"2026-01-01T00:00:00Z","mergeCommit":{"oid":"abcdef0123456789abcdef0123456789abcdef01"}'
    else
      state=OPEN
      merged='"mergedAt":null,"mergeCommit":null'
    fi
    cat <<JSON
{"number":42,"title":"Add the parser","url":"https://example.invalid/pull/42","state":"$state",$merged,"isDraft":false,"baseRefName":"main","headRefName":"feature/parser","headRefOid":"0123456789abcdef0123456789abcdef01234567","mergeable":"MERGEABLE","mergeStateStatus":"CLEAN","reviewDecision":"APPROVED","isCrossRepository":false,"maintainerCanModify":true,"commits":[{"messageHeadline":"Add the parser"}]}
JSON
    ;;
  "pr checks") echo "build	pass	1m	https://example.invalid/run/1" ;;
  "repo view") echo '{"mergeCommitAllowed":true,"squashMergeAllowed":true,"rebaseMergeAllowed":true}' ;;
  "pr merge") echo "$*" >>merge.log ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
