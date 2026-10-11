#!/usr/bin/env bash
# A stub acli serving one Jira work item that a teammate edits right after
# the first fetch, changing one number: every later view returns the edited
# body. Each edit call is appended to edit.log.
set -euo pipefail

mkdir -p bin
cat >bin/acli <<'SH'
#!/usr/bin/env bash
base=$'Changed retryQueue.js (+142/-38 lines) to add a circuit breaker.\nDefinition of done:\n- Backoff capped at 30 seconds\n- Breaker opens after 5 consecutive failures'
case "$1 $2 $3" in
  "jira workitem view")
    if [ -f .viewed ]; then
      body=${base/after 5 consecutive/after 3 consecutive}
    else
      : >.viewed
      body="$base"
    fi
    case " $* " in
      *" --json "*) jq -nc --arg b "$body" '{key:"WIDGET-482",fields:{summary:"Add a circuit breaker to the retry queue",description:$b}}' ;;
      *) printf 'WIDGET-482\nTitle: Add a circuit breaker to the retry queue\nType: Task\nBody:\n%s\nComments: none\n' "$body" ;;
    esac ;;
  "jira workitem comment") [ "${4:-}" = "list" ] && echo "No comments" || { echo "unsupported: $*" >&2; exit 1; } ;;
  "jira workitem edit")
    case " $* " in *" --help "*) echo "usage: acli jira workitem edit [flags]"; exit 0 ;; esac
    echo "$*" >>edit.log
    echo "Updated WIDGET-482" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/acli
