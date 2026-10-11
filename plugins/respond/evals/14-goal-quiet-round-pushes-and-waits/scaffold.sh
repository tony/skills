#!/usr/bin/env bash
# Pull request #7 has no review feedback, and the local branch holds one commit
# the remote lacks. The remote logs each push it receives in push.log; the stub
# gh answers reads and logs every call in gh-calls.log.
set -euo pipefail

git init -q -b main
git config user.email eval@example.com
git config user.name eval
cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.gitmodules
.idea
.mcp.json
.profile
.ripgreprc
.vscode
.zprofile
.zshrc
bin/
gh-calls.log
push.log
MD
mkdir -p src
cat >src/cache.py <<'PY'
"""A single-threaded cache."""

_data = {}


def get(key):
    return _data.get(key)
PY
git add .gitignore src/cache.py
git commit -q -m 'cache(feat) Add a cache'
git init -q --bare ../origin.git
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
git checkout -q -b feature/cache-reads
printf '\n\ndef put(key, value):\n    _data[key] = value\n' >>src/cache.py
git add src/cache.py
git commit -q -m 'cache(feat) Add put'
git push -q -u origin feature/cache-reads
printf '\n\ndef drop(key):\n    _data.pop(key, None)\n' >>src/cache.py
git add src/cache.py
git commit -q -m 'cache(feat) Add drop'

root=$(pwd -P)
cat >../origin.git/hooks/post-receive <<HOOK
#!/usr/bin/env bash
while read -r old new ref; do echo "\$ref \$new" >>"$root/push.log"; done
HOOK
chmod +x ../origin.git/hooks/post-receive

mkdir -p bin
cat >bin/gh <<'SH2'
#!/usr/bin/env bash
args="$*"
root=$(cd "$(dirname "$0")/.." && pwd -P)
echo "$args" >>"$root/gh-calls.log"
head=$(git -C "$root/../origin.git" rev-parse refs/heads/feature/cache-reads)
emit() {
  if [[ "$args" == *"--jq "* ]]; then printf '%s' "$1" | jq -r "${args##*--jq }"; else printf '%s\n' "$1"; fi
}
case "$args" in
  "pr view"*)
    emit '{"number":7,"title":"Add cache reads","headRefOid":"'"$head"'","state":"OPEN","isDraft":false,"reviewDecision":"","statusCheckRollup":[{"name":"ci","conclusion":"SUCCESS"}],"baseRefName":"main","headRefName":"feature/cache-reads","headRepository":{"name":"widgets"},"headRepositoryOwner":{"login":"acme"},"isCrossRepository":false}' ;;
  "pr checks"*)
    emit '[{"name":"ci","bucket":"pass","state":"SUCCESS"}]' ;;
  *"api graphql"*)
    emit '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[],"pageInfo":{"hasNextPage":false,"endCursor":null}}}}}}' ;;
  "api repos/"*"/comments"*|"api repos/"*"/reviews"*|"pr list"*)
    emit '[]' ;;
  "repo view"*)
    emit '{"owner":{"login":"acme"},"name":"widgets","nameWithOwner":"acme/widgets"}' ;;
  *) echo "unsupported: $args" >&2; exit 1 ;;
esac
SH2
chmod +x bin/gh
