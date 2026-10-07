#!/usr/bin/env bash
# Builds a fixture file and a stub `codex` that prints a canned plan.
set -euo pipefail

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
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
