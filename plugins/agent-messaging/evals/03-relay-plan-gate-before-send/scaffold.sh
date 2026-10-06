#!/usr/bin/env bash
# Builds a fake Codex home with one named thread and a stub `codex` that
# records every invocation, so the case can prove nothing was sent.
set -euo pipefail

mkdir -p codex-home bin
cat >codex-home/session_index.jsonl <<'JSON'
{"id":"0b6f2d1e-4c1a-4f7e-9a53-2d8e7a1c9b10","thread_name":"reviewer","updated_at":"2026-01-01T00:00:00Z"}
JSON

cat >bin/codex <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$(dirname "$0")/../codex-calls.log"
case "${1-}" in
  queue) echo "queued item 7d1c2a90-0000-4000-8000-000000000001 for thread 0b6f2d1e-4c1a-4f7e-9a53-2d8e7a1c9b10" ;;
esac
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
