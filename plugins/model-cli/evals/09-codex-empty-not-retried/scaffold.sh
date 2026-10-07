#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin

cat >bin/codex <<'SH'
#!/usr/bin/env bash
n=$(cat .calls 2>/dev/null || echo 0)
echo $((n + 1)) >.calls
exit 0
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
