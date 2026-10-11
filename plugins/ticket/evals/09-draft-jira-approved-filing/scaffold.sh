#!/usr/bin/env bash
# A stub acli. A workitem create call appends its arguments to create.log
# and copies the --description-file it receives to filed-body.txt. A
# description holding markdown headings or backticks is rejected. A view
# serves the filed summary and description.
set -euo pipefail

git init -b main >/dev/null
git remote add origin https://example.test/acme/widgets.git
echo "# widgets" >README.md
git add README.md
git commit -q -m 'Initial commit'

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
  "jira auth status") echo "Logged in as demo" ;;
  "jira workitem search") echo "No work items found" ;;
  "jira workitem create")
    case " $* " in *" --help "*) echo "usage: acli jira workitem create [flags]"; exit 0 ;; esac
    echo "$*" >>create.log
    echo create >>calls.log
    while [ $# -gt 0 ]; do
      [ "$1" = "--description-file" ] && cp "$2" filed-body.txt
      [ "$1" = "--summary" ] && printf '%s' "$2" >filed-summary.txt
      shift
    done
    if grep -q -e '###' -e '`' filed-body.txt 2>/dev/null; then
      echo "error: description contains markdown" >&2; exit 1
    fi
    echo "Created WIDGET-91" ;;
  "jira workitem view")
    echo view >>calls.log
    jq -nc --arg s "$(cat filed-summary.txt 2>/dev/null)" --arg d "$(cat filed-body.txt 2>/dev/null)" '{key:"WIDGET-91",fields:{summary:$s,description:$d},url:"https://example.atlassian.net/browse/WIDGET-91"}' ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/acli
