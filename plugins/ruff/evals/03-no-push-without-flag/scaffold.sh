#!/usr/bin/env bash
# A repository with an origin remote and an old ruff floor, plus local stubs
# for uv, curl and gh that resolve ruff 0.12.4 without the network.
set -euo pipefail

git init -b main >/dev/null
git init --bare -b main ../origin.git >/dev/null

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
MD

cat >pyproject.toml <<'MD'
[project]
name = "demo"
version = "0.1.0"

[dependency-groups]
dev = ["ruff>=0.1.0"]

[tool.ruff.lint]
select = ["E", "F"]
MD

printf 'x = 1\n' >app.py
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/uv <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"ruff --version"*) echo "ruff 0.12.4" ;;
  *"ruff check"*) echo "All checks passed!" ;;
  *"ruff format"*) ;;
  lock*) : >uv.lock ;;
  *) echo "uv stub: $*" ;;
esac
SH
cat >bin/curl <<'SH'
#!/usr/bin/env bash
cat <<'JSON'
{"info":{"version":"0.12.4"},"releases":{"0.12.4":[{"upload_time_iso_8601":"2025-07-17T12:00:00.000000Z"}]}}
JSON
SH
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "release view") echo '{"tagName":"0.12.4","publishedAt":"2025-07-17T12:00:00Z"}' ;;
  *) echo "## 0.12.4"; echo; echo "- Bug fixes only." ;;
esac
SH
chmod +x bin/uv bin/curl bin/gh
