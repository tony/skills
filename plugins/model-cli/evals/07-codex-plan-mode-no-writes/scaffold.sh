#!/usr/bin/env bash
# Builds a fixture file and a stub `codex` that records every invocation
# and prints a canned plan, so the case can prove which flags were used.
set -euo pipefail

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$(dirname "$0")/../codex-calls.log"
echo "PLAN: validate that payload is a dict with a string name in app.py:handle."
SH
chmod +x bin/codex

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.profile
.zprofile
.zshrc
MD
