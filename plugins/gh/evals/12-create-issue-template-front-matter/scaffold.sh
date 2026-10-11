#!/usr/bin/env bash
# A stub gh with one markdown bug template carrying a title prefix and a
# label. Every gh issue create call is appended to create.log.
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
    echo '{"nameWithOwner":"example/widgets","isSecurityPolicyEnabled":false,"securityPolicyUrl":"","hasIssuesEnabled":true,"issueTemplates":[],"contactLinks":[],"parent":null}'
    ;;
  "issue list"|"search issues") echo "[]" ;;
  "label list") echo '[{"name":"bug","description":"Something is broken"}]' ;;
  "issue create")
    echo "$*" >>create.log
    echo "https://example.invalid/example/widgets/issues/42"
    ;;
  "issue view") echo '{"number":42,"title":"[Bug]: x","state":"OPEN","url":"https://example.invalid/example/widgets/issues/42"}' ;;
  "api repos/example/widgets/private-vulnerability-reporting") echo "false" ;;
  "api repos/example/widgets/contents/.github/ISSUE_TEMPLATE") printf 'bug_report.md\n' ;;
  "api repos/example/widgets/contents/.github/ISSUE_TEMPLATE/bug_report.md")
    printf -- "---\nname: Bug report\nabout: Report a bug\ntitle: '[Bug]: '\nlabels: bug\nassignees: ''\n---\n\n### What happened\n\n### Steps to reproduce\n"
    ;;
  "api --method") echo "<p>preview</p>" ;;
  *) echo '{"message":"Not Found","status":"404"}' >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
