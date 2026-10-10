#!/usr/bin/env bash
# F401 fires once on the previous version and twice on 0.12.4; E711 fires
# once on both. Local stubs for uv, curl and gh.
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
import sys


def f():
    return 2


x = None
if x == None:
    pass
PY
git add .
git commit -q -m 'Initial commit'
git remote add origin ../origin.git
git push -q origin main

mkdir -p bin
cat >bin/uv <<'SH'
#!/usr/bin/env bash
# Stub ruff. The previous version (0.11.0, or an isolated `--with ruff==` run
# of it) reports one unused import; 0.12.4 reports both.
old=1
grep -q '0\.12\.4' pyproject.toml && old=0
case "$*" in *"ruff=="*) case "$*" in *"ruff==0.12.4"*) old=0 ;; *) old=1 ;; esac ;; esac
here() { grep -n -m1 -e "$1" app.py | cut -d: -f1; }
case "$*" in
  *"ruff --version"*)
    if [ "$old" = 0 ]; then echo "ruff 0.12.4"; else echo "ruff 0.11.0"; fi ;;
  *"ruff check"*"--fix"*)
    case "$*" in
      *"--select F401"*) grep -v -e '^import os$' -e '^import sys$' app.py >app.py.new && mv app.py.new app.py ;;
    esac
    echo "Found 1 error (1 fixed, 0 remaining)." ;;
  *"ruff check"*"--statistics"*)
    out=""
    add() { out="$out${out:+,}{\"code\":\"$1\",\"count\":$2}"; }
    n=$(grep -c -e '^import os$' -e '^import sys$' app.py || true)
    [ "$old" = 1 ] && [ "$n" -gt 1 ] && n=1
    [ "$n" -gt 0 ] && add F401 "$n"
    grep -q '== None' app.py && add E711 1
    echo "[$out]"
    [ -z "$out" ] || exit 1 ;;
  *"ruff check"*"--output-format json"*)
    out=""
    add() { n=$(here "$2"); [ -n "$n" ] && out="$out${out:+,}{\"code\":\"$1\",\"filename\":\"$PWD/app.py\",\"location\":{\"row\":$n,\"column\":$3}}"; return 0; }
    add F401 '^import os$' 8
    [ "$old" = 0 ] && add F401 '^import sys$' 8
    add E711 '== None' 4
    echo "[$out]"
    [ -z "$out" ] || exit 1 ;;
  *"ruff check"*)
    n=0
    grep -q '^import os$' app.py && { echo "app.py:1:8: F401 [*] \`os\` imported but unused"; n=1; }
    [ "$old" = 0 ] && grep -q '^import sys$' app.py && { echo "app.py:2:8: F401 [*] \`sys\` imported but unused"; n=1; }
    grep -q '== None' app.py && { echo "app.py:6:4: E711 comparison to \`None\`"; n=1; }
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
