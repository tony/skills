#!/usr/bin/env bash
# A ruff 0.13.0 pin with an explicit select, two unused `# noqa` comments that
# RUF100 flags once the default set is adopted, and local stubs for uv, curl
# and gh that resolve ruff 0.13.1 without the network.
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
dev = ["ruff>=0.13.0"]

[tool.ruff.lint]
select = ["E", "F"]
MD

cat >app.py <<'PY'
x = 1  # noqa: E501
y = 2  # noqa: E501
PY
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/uv <<'SH'
#!/usr/bin/env bash
# Stub ruff. RUF100 fires on stale noqa comments only when the configuration
# does not pin `select` to E and F (or when the default codes are added).
adopted=0
grep -q 'select = \["E", "F"\]' pyproject.toml || adopted=1
case "$*" in *"--extend-select"*) adopted=1 ;; esac
case "$*" in
  *"ruff --version"*)
    if grep -q '0\.13\.1' pyproject.toml; then echo "ruff 0.13.1"; else echo "ruff 0.13.0"; fi ;;
  *"--show-settings"*)
    printf 'linter.rules.enabled = [\n\tunused-import (F401),\n\tunused-noqa (RUF100),\n]\n' ;;
  *"ruff check"*"--fix"*)
    case "$*" in
      *"--select RUF100"*) sed -e 's/  # noqa: E501$//' app.py >app.py.new && mv app.py.new app.py ;;
    esac
    echo "Found 2 errors (2 fixed, 0 remaining)." ;;
  *"ruff check"*"--statistics"*)
    case "$*" in *"ruff==0.13.0"*) adopted=0 ;; esac
    if [ "$adopted" = 1 ] && grep -q 'noqa' app.py; then
      echo '[{"code":"RUF100","count":2}]'; exit 1
    fi
    echo '[]' ;;
  *"ruff check"*)
    if [ "$adopted" = 1 ] && grep -q 'noqa' app.py; then
      echo "app.py:1:8: RUF100 [*] Unused \`noqa\` directive"; exit 1
    fi
    echo "All checks passed!" ;;
  *"ruff format"*) ;;
  lock*) : >uv.lock ;;
  *) echo "uv stub: $*" ;;
esac
SH
cat >bin/curl <<'SH'
#!/usr/bin/env bash
case "$*" in
  *CHANGELOG*) printf '## 0.13.1\n\n### Rule changes\n\n- Expand the default rule set with unused-noqa (RUF100)\n' ;;
  *) echo '{"info":{"version":"0.13.1"},"releases":{"0.13.1":[{"upload_time_iso_8601":"2025-09-10T12:00:00.000000Z"}]}}' ;;
esac
SH
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "release view") echo '{"tagName":"0.13.1","publishedAt":"2025-09-10T12:00:00Z"}' ;;
  "repo view") echo '{"isFork":false}' ;;
  *) echo "## 0.13.1"; echo; echo "- Expand the default rule set with unused-noqa (RUF100)" ;;
esac
SH
chmod +x bin/uv bin/curl bin/gh
