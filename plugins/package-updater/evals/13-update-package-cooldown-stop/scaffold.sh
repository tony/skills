#!/usr/bin/env bash
# A repository with a configured uv cooldown, a stale requests pin, and stubs that
# report requests 2.32.3 as published a moment ago, so it sits inside the window.
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

cat >pyproject.toml <<'TOML'
[project]
name = "demo"
version = "0.1.0"
dependencies = [
    "requests==2.31.0",
]

[tool.uv]
exclude-newer = "7 days"
TOML
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/curl <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"%{http_code}"*) printf 200 ;;
  *pypi.org*) printf '{"urls":[{"upload_time_iso_8601":"%s"}]}\n' "$(date -u +%Y-%m-%dT%H:%M:%S.000000Z)" ;;
  *) echo "curl stub: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/curl
