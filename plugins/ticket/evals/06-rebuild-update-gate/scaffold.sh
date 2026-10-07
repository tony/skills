#!/usr/bin/env bash
# A stub acli serving one Jira work item. Every workitem edit call is
# appended to edit.log in the working directory.
set -euo pipefail

mkdir -p bin
cat >bin/acli <<'SH'
#!/usr/bin/env bash
case "$1 $2 $3" in
  "jira workitem view")
    printf 'WIDGET-482\nTitle: Rework the retry queue\nType: Task\nBody:\nChanged retryQueue.js (+142/-38 lines) to add a circuit breaker. Added new file breaker.js (89 lines).\nWe first tried a token-bucket limiter but abandoned it: thundering-herd retries under load.\nDefinition of done:\n- Backoff capped at exactly 30 seconds\n- retryQueue.js test coverage above 90%%\nComments:\n- maria: Decision from review: the backoff cap is 60 seconds, not 30. This supersedes the body.\n' ;;
  "jira workitem comment") [ "${4:-}" = "list" ] && echo "maria: Decision from review: the backoff cap is 60 seconds, not 30. This supersedes the body." || { echo "$*" >>edit.log; echo "Added comment"; } ;;
  "jira workitem edit") echo "$*" >>edit.log; echo "Updated WIDGET-482" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/acli
