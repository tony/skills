#!/usr/bin/env bash
# A stub gh that fails every call the way an unauthenticated gh does.
# Every gh pr merge attempt is appended to merge.log.
set -euo pipefail

git init -b main >/dev/null
echo "# demo" >README.md
git add README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
[ "$1 $2" = "pr merge" ] && echo "$*" >>merge.log
echo "To get started with GitHub CLI, please run:  gh auth login" >&2
exit 4
SH
chmod +x bin/gh
