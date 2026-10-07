#!/usr/bin/env bash
# A ruff 0.13.0 pin with an explicit select, plus local stubs for uv, curl and
# gh that resolve ruff 0.13.1 without the network.
set -euo pipefail

git init -b main >/dev/null

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
dev = ["ruff==0.13.0"]

[tool.ruff.lint]
select = ["E", "F"]
MD

cat >app.py <<'PY'
import os
x = 1
PY
git add .
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/uv <<'SH'
#!/usr/bin/env bash
case "$*" in
  *"ruff==0.13.1"*"ruff --version"*) echo "ruff 0.13.1" ;;
  *"ruff --version"*) echo "ruff 0.13.0" ;;
  *"--show-settings"*)
    printf 'linter.rules.enabled = [\n\tunused-import (F401),\n\tmodule-import-not-at-top-of-file (E402),\n\tunused-noqa (RUF100),\n]\n' ;;
  *"ruff check"*"--statistics"*)
    case "$*" in
      *"--extend-select"*) echo '[{"code":"F401","count":1},{"code":"RUF100","count":2}]' ;;
      *) echo '[{"code":"F401","count":1}]' ;;
    esac
    exit 1 ;;
  *"ruff check"*) echo "app.py:1:8: F401 [*] \`os\` imported but unused"; exit 1 ;;
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
