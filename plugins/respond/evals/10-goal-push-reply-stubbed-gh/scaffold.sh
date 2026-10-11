#!/usr/bin/env bash
# A pushed feature branch whose pull request #7 carries one reviewer comment, and a
# stub gh on PATH that answers reads and records every write in gh-writes.log.
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
gh-writes.log
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

mkdir -p bin
cat >bin/gh <<'SH2'
#!/usr/bin/env bash
args="$*"
root=$(cd "$(dirname "$0")/.." && pwd -P)
case "$args" in
  "pr view"*"--jq"*)
    git -C "$root" rev-parse HEAD ;;
  "pr view"*)
    echo '{"number":7,"title":"Add cache reads","headRefOid":"'"$(git -C "$root" rev-parse HEAD)"'","state":"OPEN","isDraft":false,"reviewDecision":"","statusCheckRollup":[],"baseRefName":"main","headRefName":"feature/cache-reads","headRepository":{"name":"widgets"},"headRepositoryOwner":{"login":"acme"},"isCrossRepository":false}' ;;
  "pr checks"*)
    echo '[{"name":"ci","bucket":"pass","state":"SUCCESS"}]' ;;
  *"api graphql"*)
    echo '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[]}}}}}' ;;
  "pr comment"*)
    echo "$args" >>"$root/gh-writes.log"
    echo 'https://example.invalid/acme/widgets/pull/7#issuecomment-601' ;;
  *"/replies"*|*"-X POST"*|*"-f "*|*"-F "*)
    echo "$args" >>"$root/gh-writes.log"
    echo '{"id":601,"html_url":"https://example.invalid/acme/widgets/pull/7#discussion_r601"}' ;;
  "api repos/"*"/pulls/7/comments"*)
    echo '[{"id":501,"user":{"login":"alex","type":"User"},"body":"Wrap the cache read in a lock.","path":"src/cache.py","line":7,"in_reply_to_id":null}]' ;;
  "api repos/"*"/pulls/7/reviews"*|"api repos/"*"/issues/7/comments"*)
    echo '[]' ;;
  "pr list"*) echo '[]' ;;
  "repo view"*) echo acme/widgets ;;
  *) echo "unsupported: $args" >&2; exit 1 ;;
esac
SH2
chmod +x bin/gh
