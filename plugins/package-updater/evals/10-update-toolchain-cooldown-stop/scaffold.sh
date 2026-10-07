#!/usr/bin/env bash
# A repository with a configured uv cooldown, a stale uv pin, and stubs that
# report uv 0.8.4 as published a moment ago, so it sits inside the window.
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

printf 'uv 0.7.8\n' >.tool-versions
cat >pyproject.toml <<'TOML'
[project]
name = "demo"
version = "0.1.0"

[tool.uv]
exclude-newer = "7 days"
TOML
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$*" in
  *astral-sh/uv/releases/latest*) echo "0.8.4" ;;
  *releases/tags/*) date -u +%Y-%m-%dT%H:%M:%SZ ;;
  *) echo "gh stub: $*" >&2; exit 1 ;;
esac
SH
cat >bin/curl <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"%{http_code}"*) printf 200 ;;
  *pypi.org*) printf '{"urls":[{"upload_time_iso_8601":"%s"}]}\n' "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)" ;;
  *) echo "curl stub: $*" >&2; exit 1 ;;
esac
SH
cat >bin/mise <<'SH'
#!/usr/bin/env bash
case "$1" in
  outdated) printf 'Tool  Current  Latest\nuv    0.7.8    0.8.4\n' ;;
  *) echo "mise stub: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh bin/curl bin/mise
