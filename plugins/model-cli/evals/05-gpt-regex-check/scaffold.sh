#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin

cat >bin/codex <<'SH'
#!/usr/bin/env bash
echo "ANSWER: \\w is Unicode-aware in Python 3 str patterns, so non-ASCII local parts match."
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
