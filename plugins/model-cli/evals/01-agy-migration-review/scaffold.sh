#!/usr/bin/env bash
# Stub CLIs under ./bin so no real model CLI runs.
set -euo pipefail

mkdir -p bin

cat >bin/agy <<'SH'
#!/usr/bin/env bash
echo "ANSWER: dropping legacy_status breaks any query or ORM model that still reads it."
SH
chmod +x bin/agy

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
