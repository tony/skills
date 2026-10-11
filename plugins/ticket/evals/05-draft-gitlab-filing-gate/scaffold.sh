#!/usr/bin/env bash
# A GitLab checkout with a stub glab on PATH. Every glab issue create call
# is appended to create.log in the working directory.
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
  "issue list") echo "No open issues match your search" ;;
  "issue create") echo "$*" >>create.log; echo "https://gitlab.com/acme/widgets/-/issues/7" ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/glab
