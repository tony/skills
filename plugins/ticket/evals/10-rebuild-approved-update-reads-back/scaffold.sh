#!/usr/bin/env bash
# A stub acli serving one Jira work item. An edit stores the new body and
# title, a later view serves them, and each view and edit appends a line
# to calls.log.
set -euo pipefail

mkdir -p bin
cat >bin/acli <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*)
  case "$1 $2 $3" in
    "jira workitem create") printf 'Flags:\n  -p, --project string\n  -t, --type string\n  -s, --summary string\n  -d, --description string\n      --description-file string\n  -a, --assignee string\n  -l, --label strings\n      --json\n'; exit 0 ;;
    "jira workitem edit") printf 'Flags:\n  -k, --key string\n  -s, --summary string\n  -d, --description string\n      --description-file string\n  -y, --yes\n      --json\n'; exit 0 ;;
    "jira workitem view") printf 'Flags:\n  -f, --fields string\n      --json\n  -w, --web\n'; exit 0 ;;
  esac ;;
esac
case "$1 $2 $3" in
  "jira workitem view")
    echo view >>calls.log
    if [ -f current-body.txt ]; then
      body=$(cat current-body.txt)
    else
      body=$'Changed retryQueue.js (+142/-38 lines) to add a circuit breaker.\nDefinition of done:\n- Backoff capped at 30 seconds\n- Breaker opens after 5 consecutive failures'
    fi
    title=$(cat current-title.txt 2>/dev/null || echo 'Add a circuit breaker to the retry queue')
    case " $* " in
      *" --json "*) jq -nc --arg t "$title" --arg b "$body" '{key:"WIDGET-482",fields:{summary:$t,description:$b}}' ;;
      *) printf 'WIDGET-482\nTitle: %s\nType: Task\nBody:\n%s\nComments: none\n' "$title" "$body" ;;
    esac ;;
  "jira workitem comment") [ "${4:-}" = "list" ] && echo "No comments" || { echo "unsupported: $*" >&2; exit 1; } ;;
  "jira workitem edit")
    case " $* " in *" --help "*) echo "usage: acli jira workitem edit [flags]"; exit 0 ;; esac
    echo edit >>calls.log
    while [ $# -gt 0 ]; do
      [ "$1" = "--description-file" ] && cp "$2" current-body.txt
      [ "$1" = "--description" ] && printf '%s' "$2" >current-body.txt
      [ "$1" = "--summary" ] && printf '%s' "$2" >current-title.txt
      shift
    done
    echo "Updated WIDGET-482" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/acli
