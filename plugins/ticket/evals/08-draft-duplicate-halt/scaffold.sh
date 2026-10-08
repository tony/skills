#!/usr/bin/env bash
# A GitLab checkout with a stub glab whose issue list holds a closed match.
# Every glab write call is appended to write.log in the working directory.
set -euo pipefail

git init -b main >/dev/null
git remote add origin https://gitlab.com/acme/widgets.git
echo "# widgets" >README.md
git add README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/glab <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "auth status") echo "gitlab.com: Logged in as demo" ;;
  "issue list")
    case " $* " in
      *" --all "*|*" -A "*|*" --closed "*|*" -c "*)
        printf '#3\tCSV export drops the last row on large files\t(closed)\n' ;;
      *) echo "No open issues match your search" ;;
    esac ;;
  "issue view") printf '#3 CSV export drops the last row on large files\nState: closed\nThe export loses its final row when the file is large.\nComments: none\n' ;;
  "issue create"|"issue note"|"issue update") echo "$*" >>write.log; echo "https://gitlab.com/acme/widgets/-/issues/8" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/glab
