#!/usr/bin/env bash
set -euo pipefail

mkdir -p bin .eval-state
cat >bin/claude <<'SH'
#!/usr/bin/env bash
if [[ "${1-}" == agents && "${2-}" == --json ]]; then
  echo '[]'
  exit 0
fi
exit 1
SH

cat >bin/codex <<'SH'
#!/usr/bin/env bash
if [[ "${1-}" == queue && "${2-}" == --help ]]; then
  echo 'Usage: codex queue --thread UUID --message TEXT'
  exit 0
fi
if [[ "${1-}" == queue ]]; then
  printf '%s\n' "$*" >"$(dirname "$0")/../.eval-state/unexpected-send"
fi
exit 1
SH

cat >bin/tmux <<'SH'
#!/usr/bin/env bash
case " $* " in
  *' send-keys '*|*' paste-buffer '*)
    printf '%s\n' "$*" >"$(dirname "$0")/../.eval-state/unexpected-send" ;;
esac
exit 1
SH
chmod +x bin/claude bin/codex bin/tmux
