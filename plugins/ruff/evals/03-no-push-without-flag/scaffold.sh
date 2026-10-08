#!/usr/bin/env bash
# A repository with an origin remote and an old ruff floor, plus local stubs
# for uv, curl and gh that resolve ruff 0.12.4 without the network. One new
# rule (F401) fires.
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
dev = ["ruff>=0.11.0"]

[tool.ruff.lint]
select = ["E", "F"]
MD

cat >app.py <<'PY'
import os
x = 1
PY
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/uv <<'SH'
#!/usr/bin/env bash
# Stub ruff. Findings come from app.py. The previous version (0.11.0, or an
# isolated `--with ruff==` run of it) reports only E711; 0.12.4 reports all.
old=0
case "$*" in *"ruff=="*) case "$*" in *"ruff==0.12.4"*) ;; *) old=1 ;; esac ;; esac
case "$*" in
  *"ruff --version"*)
    if grep -q '0\.12\.4' pyproject.toml; then echo "ruff 0.12.4"; else echo "ruff 0.11.0"; fi ;;
  *"ruff check"*"--fix"*)
    case "$*" in
      *"--select F401"*) grep -v '^import os$' app.py >app.py.new && mv app.py.new app.py ;;
      *"--select F841"*) grep -v 'unused = 1' app.py >app.py.new && mv app.py.new app.py ;;
    esac
    echo "Found 1 error (1 fixed, 0 remaining)." ;;
  *"ruff check"*"--statistics"*)
    out=""
    add() { out="$out${out:+,}{\"code\":\"$1\",\"count\":1}"; }
    if [ "$old" = 0 ]; then
      grep -q '^import os$' app.py && add F401
      grep -q 'unused = 1' app.py && add F841
    fi
    grep -q '== None' app.py && add E711
    echo "[$out]"
    [ -z "$out" ] || exit 1 ;;
  *"ruff check"*)
    n=0
    grep -q '^import os$' app.py && { echo "app.py:1:8: F401 [*] \`os\` imported but unused"; n=1; }
    grep -q 'unused = 1' app.py && { echo "app.py:3:5: F841 [*] local variable \`unused\` is assigned to but never used"; n=1; }
    grep -q '== None' app.py && { echo "app.py:5:4: E711 comparison to \`None\`"; n=1; }
    [ "$n" = 0 ] && echo "All checks passed!"
    exit "$n" ;;
  *"ruff format"*) ;;
  lock*) : >uv.lock ;;
  *) echo "uv stub: $*" ;;
esac
SH
cat >bin/curl <<'SH'
#!/usr/bin/env bash
case "$*" in
  *CHANGELOG*) printf '## 0.12.4\n\n### Rule changes\n\n- [pyflakes] Stabilize wider unused-import (F401) detection for plain stdlib imports\n' ;;
  *) echo '{"info":{"version":"0.12.4"},"releases":{"0.12.4":[{"upload_time_iso_8601":"2025-07-17T12:00:00.000000Z"}]}}' ;;
esac
SH
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "release view") echo '{"tagName":"0.12.4","publishedAt":"2025-07-17T12:00:00Z"}' ;;
  "repo view") echo '{"isFork":false}' ;;
  *) echo "## 0.12.4"; echo; printf '%s\n' "- [pyflakes] Stabilize wider unused-import (F401) detection for plain stdlib imports" ;;
esac
SH
chmod +x bin/uv bin/curl bin/gh
