#!/usr/bin/env bash
# A stub gh with no duplicates, no templates, and one label.
# Every gh issue create call is appended to create.log.
set -euo pipefail

git init -b main >/dev/null
echo "# demo" >README.md
git add README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "auth status") echo "github.com: Logged in" ;;
  "repo view")
    cat <<'JSON'
{"nameWithOwner":"example/widgets","isSecurityPolicyEnabled":false,"securityPolicyUrl":"","hasIssuesEnabled":true,"isBlankIssuesEnabled":true,"issueTemplates":[],"contactLinks":[],"parent":null}
JSON
    ;;
  "issue list"|"search issues") echo "[]" ;;
  "label list") echo '[{"name":"bug","description":"Something is broken"}]' ;;
  "issue create")
    echo "$*" >>create.log
    echo "https://example.invalid/example/widgets/issues/42"
    ;;
  "api repos/example/widgets/private-vulnerability-reporting") echo "false" ;;
  "api repos/example/widgets/contents/.github/ISSUE_TEMPLATE")
    echo '{"message":"Not Found","status":"404"}' >&2
    exit 1
    ;;
  "api --method") echo "<p>preview</p>" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
