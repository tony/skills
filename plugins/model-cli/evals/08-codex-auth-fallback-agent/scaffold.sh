#!/usr/bin/env bash
# Builds a fixture file, a stub `codex` that fails to authenticate, and a
# stub `agent` that returns an answer.
set -euo pipefail

mkdir -p bin
cat >app.py <<'PY'
def handle(payload):
    return payload["name"].upper()
PY

cat >bin/codex <<'SH'
#!/usr/bin/env bash
echo "Authentication required: run codex login" >&2
exit 1
SH

cat >bin/agent <<'SH'
#!/usr/bin/env bash
echo "ANSWER: handle() upper-cases payload['name'] and raises KeyError when it is missing."
SH
chmod +x bin/codex bin/agent

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
