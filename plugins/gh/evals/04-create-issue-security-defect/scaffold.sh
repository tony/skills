#!/usr/bin/env bash
# A stub gh whose repository has a security policy.
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
{"nameWithOwner":"example/widgets","isSecurityPolicyEnabled":true,"securityPolicyUrl":"https://example.invalid/example/widgets/security/policy","hasIssuesEnabled":true,"isBlankIssuesEnabled":true,"issueTemplates":[],"contactLinks":[],"parent":null}
JSON
    ;;
  "issue create") echo "$*" >>create.log ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
