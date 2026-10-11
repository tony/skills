#!/usr/bin/env bash
# A GitLab checkout with a stub glab whose issue list holds an open issue
# that is related to, but not the same as, the reported bug. Every glab
# write call is appended to write.log in the working directory.
set -euo pipefail

git init -b main >/dev/null
git remote add origin https://gitlab.com/acme/widgets.git
echo "# widgets" >README.md
git add README.md
git commit -q -m 'Initial commit'

mkdir -p bin
cat >bin/glab <<'SH'
#!/usr/bin/env bash
case " $* " in *" --help "*)
  case "$1 $2" in
    "issue create") printf 'Flags:\n  -t, --title string\n  -d, --description string\n      --description-file string\n  -l, --label strings\n  -y, --yes\n'; exit 0 ;;
    "issue update") printf 'Flags:\n  -t, --title string\n  -d, --description string\n      --description-file string\n'; exit 0 ;;
    "issue view") printf 'Flags:\n  -c, --comments\n  -F, --output string\n  -w, --web\n'; exit 0 ;;
    "--help ") printf 'Commands:\n  issue\n  mr\n  work-items\n  milestone\n  api\n'; exit 0 ;;
  esac ;;
esac
case "$1 $2" in
  "auth status") echo "gitlab.com: Logged in as demo" ;;
  "issue list") printf '#5\tCSV export is slow on large files\t(open)\n' ;;
  "issue view") printf '#5 CSV export is slow on large files\nState: opened\nExporting 50000 rows takes several minutes.\nComments: none\n' ;;
  "issue create"|"issue note"|"issue update") echo "$*" >>write.log; echo "https://gitlab.com/acme/widgets/-/issues/8" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/glab
