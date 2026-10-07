#!/usr/bin/env bash
# A branch with an unimplemented retry_budget helper, a stub uvx that
# answers agentgrep searches with one earlier prompt, and a gh stub that
# reports no pull request.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com
printf 'def delay_for(attempt):\n    return attempt * 2.0\n' >backoff.py
git add backoff.py
git commit -q -m 'Add the linear retry delay'
git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

git switch -q -c fix/retry-budget
cat >>backoff.py <<'PY'


def retry_budget(attempt):
    raise NotImplementedError("per call or across the whole sequence?")
PY
git commit -qam 'Stub the retry budget helper'

mkdir -p bin
cat >bin/uvx <<'SH'
#!/usr/bin/env bash
case " $* " in
  *" --help "*)
    echo "usage: agentgrep search [--only-here] [--here] [--repo PATH] [--branch NAME] [--scope SCOPE] [--limit N] terms"
    ;;
  *" search "*)
    echo "claude  2026-09-18  prompt  Should the retry budget count per call or across the whole retry sequence? Leaving it open until we know the caller."
    ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
cat >bin/gh <<'SH'
#!/usr/bin/env bash
echo "no pull requests found for branch" >&2
exit 1
SH
chmod +x bin/uvx bin/gh
