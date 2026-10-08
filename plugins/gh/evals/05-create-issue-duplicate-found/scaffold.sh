#!/usr/bin/env bash
# A stub gh whose duplicate search finds open issue #17.
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
  "api repos/example/widgets/private-vulnerability-reporting") echo "false" ;;
  "issue list"|"search issues")
    echo '[{"number":17,"title":"wasm build throws TypeError reading target","state":"OPEN","url":"https://example.invalid/example/widgets/issues/17"}]'
    ;;
  "issue view") echo "#17 wasm build throws TypeError reading target (open): widgets build --target=wasm fails on 2.4.1 with the same TypeError." ;;
  "issue create") echo "$*" >>create.log ;;
  "label list") echo "[]" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
