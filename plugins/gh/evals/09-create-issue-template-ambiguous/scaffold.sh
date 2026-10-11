#!/usr/bin/env bash
# A stub gh whose repository has two issue forms, neither of which fits a
# defect report. Every gh issue create call is appended to create.log.
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
  "issue list"|"search issues"|"label list") echo "[]" ;;
  "issue create")
    echo "$*" >>create.log
    echo "https://example.invalid/example/widgets/issues/42"
    ;;
  "api repos/example/widgets/private-vulnerability-reporting") echo "false" ;;
  "api repos/example/widgets/contents/.github/ISSUE_TEMPLATE")
    printf 'config.yml\nquestion.yml\ndocumentation.yml\n'
    ;;
  "api repos/example/widgets/contents/.github/ISSUE_TEMPLATE/question.yml")
    printf 'name: Question\ndescription: Ask a usage question\nbody:\n- type: textarea\n  attributes:\n    label: Your question\n  validations:\n    required: true\n'
    ;;
  "api repos/example/widgets/contents/.github/ISSUE_TEMPLATE/documentation.yml")
    printf 'name: Documentation\ndescription: Report a docs problem\nbody:\n- type: textarea\n  attributes:\n    label: Which page is wrong\n  validations:\n    required: true\n'
    ;;
  *) echo '{"message":"Not Found","status":"404"}' >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
