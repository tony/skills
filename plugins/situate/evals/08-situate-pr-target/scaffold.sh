#!/usr/bin/env bash
# A stub gh for pull request #42, whose head exists only on the remote:
# one failing check, one unresolved review thread, no ticket.
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com
printf 'def parse(text):\n    return text.split(",")\n' >parser.py
git add parser.py
git commit -q -m 'Add the parser'
git init --bare -b main ../origin.git >/dev/null
git remote add origin ../origin.git
git push -q -u origin main
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

mkdir -p bin
cat >bin/gh <<'SH'
#!/usr/bin/env bash
case "$1 $2" in
  "pr view")
    cat <<'JSON'
{"number":42,"title":"Quote-aware CSV parsing","state":"OPEN","isDraft":false,"url":"https://example.invalid/pull/42","headRefName":"feat/quoted-csv","headRefOid":"0123456789abcdef0123456789abcdef01234567","baseRefName":"main","body":"Parse quoted fields instead of splitting on every comma.","reviewDecision":"CHANGES_REQUESTED","statusCheckRollup":[{"name":"unit-tests","status":"COMPLETED","conclusion":"FAILURE"},{"name":"lint","status":"COMPLETED","conclusion":"SUCCESS"}],"commits":[{"oid":"0123456","messageHeadline":"Parse quoted CSV fields"}]}
JSON
    ;;
  "pr diff")
    cat <<'DIFF'
diff --git a/parser.py b/parser.py
--- a/parser.py
+++ b/parser.py
@@ -1,2 +1,4 @@
+import csv
+
 def parse(text):
-    return text.split(",")
+    return next(csv.reader([text]))
DIFF
    ;;
  "api graphql")
    cat <<'JSON'
{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"isResolved":false,"isOutdated":false,"path":"parser.py","comments":{"nodes":[{"author":{"login":"reviewer"},"body":"Please add a test for a field with an escaped quote."}]}}]}}}}}
JSON
    ;;
  "run list") echo '[{"name":"unit-tests","status":"completed","conclusion":"failure"}]' ;;
  *) echo "unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
