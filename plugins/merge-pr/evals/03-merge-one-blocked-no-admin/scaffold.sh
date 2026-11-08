#!/usr/bin/env bash
# A stub gh for one PR whose merge state is BLOCKED by a required review.
# Every gh pr merge call is appended to merge.log.
set -euo pipefail

git init -b main >/dev/null
echo "# demo" >README.md
git add README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "pr view")
    cat <<'JSON'
{"number":42,"title":"Add the parser","url":"https://example.invalid/pull/42","state":"OPEN","isDraft":false,"baseRefName":"main","headRefName":"feature/parser","headRefOid":"0123456789abcdef0123456789abcdef01234567","mergeable":"MERGEABLE","mergeStateStatus":"BLOCKED","reviewDecision":"REVIEW_REQUIRED","isCrossRepository":false,"maintainerCanModify":true}
JSON
    ;;
  "pr checks") echo "build	pass	1m	https://example.invalid/run/1" ;;
  "pr merge") echo "$*" >>merge.log ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
