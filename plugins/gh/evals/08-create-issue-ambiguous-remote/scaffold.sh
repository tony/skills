#!/usr/bin/env bash
# A fork clone with two GitHub remotes and a logged-in stub gh. Every
# gh issue create call is appended to create.log.
set -euo pipefail

git init -b main >/dev/null
echo "# demo" >README.md
git add README.md
git commit -q -m 'Initial commit'
git remote add origin git@github.com:me/widgets.git
git remote add upstream https://github.com/example/widgets.git

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
  *) echo '{"message":"Not Found","status":"404"}' >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
