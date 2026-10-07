#!/usr/bin/env bash
# A repository with an origin remote and two stale toolchain pins, plus local
# stubs for gh, curl and mise that resolve uv 0.8.4 and just 1.40.0 without
# the network.
set -euo pipefail

git init -q -b main .
git init -q --bare -b main ../origin.git

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
bin
MD

printf 'uv 0.7.8\njust 1.36.0\n' >.tool-versions
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$*" in
  *releases/latest*uv*|*astral-sh/uv/releases/latest*) echo "0.8.4" ;;
  *casey/just/releases/latest*) echo "1.40.0" ;;
  *releases/tags/*) echo "2025-07-01T00:00:00Z" ;;
  *) echo "gh stub: $*" >&2; exit 1 ;;
esac
SH
cat >bin/curl <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"%{http_code}"*) printf 200 ;;
  *pypi.org*) echo '{"urls":[{"upload_time_iso_8601":"2025-07-01T00:00:00.000000Z"}]}' ;;
  *) echo "Bug fixes, new subcommands and one deprecation; nothing removed."; exit 0 ;;
esac
SH
cat >bin/mise <<'SH'
#!/usr/bin/env bash
case "$1" in
  outdated) printf 'Tool  Current  Latest\nuv    0.7.8    0.8.4\njust  1.36.0   1.40.0\n' ;;
  *) echo "mise stub: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh bin/curl bin/mise
