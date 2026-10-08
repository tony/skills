#!/usr/bin/env bash
# A git repo plus a stub gh that serves saved GraphQL pull-request pages, so the
# collection path never depends on the runner's login or network.
set -euo pipefail

git init -b main >/dev/null
echo "# widgets" >README.md
git add README.md
git -c user.name=Test -c user.email=test@example.com commit -q -m 'Initial commit'

mkdir -p bin fixtures
cat >fixtures/pr-pages.json <<'JSON'
{"data":{"repository":{"pullRequests":{"pageInfo":{"hasNextPage":true,"endCursor":"c1"},"nodes":[
{"number":1,"createdAt":"2026-04-02T00:00:00Z","mergedAt":"2026-04-03T12:00:00Z","additions":40,"deletions":5,"author":{"login":"ann-dev"},"reviews":{"pageInfo":{"hasNextPage":false},"nodes":[{"submittedAt":"2026-04-02T01:00:00Z","author":{"login":"ann-dev","__typename":"User"}},{"submittedAt":"2026-04-02T06:00:00Z","author":{"login":"bo-rev","__typename":"User"}}]},"reopened":{"filteredCount":0}},
{"number":2,"createdAt":"2026-04-10T00:00:00Z","mergedAt":"2026-04-10T10:00:00Z","additions":3,"deletions":1,"author":{"login":"ann-dev"},"reviews":{"pageInfo":{"hasNextPage":true},"nodes":[{"submittedAt":"2026-04-10T02:00:00Z","author":{"login":"ann-dev","__typename":"User"}}]},"reopened":{"filteredCount":1}}]}}}}
{"data":{"repository":{"pullRequests":{"pageInfo":{"hasNextPage":false,"endCursor":"c2"},"nodes":[
{"number":3,"createdAt":"2026-06-28T00:00:00Z","mergedAt":"2026-07-02T00:00:00Z","additions":9,"deletions":9,"author":{"login":"bo-rev"},"reviews":{"pageInfo":{"hasNextPage":false},"nodes":[]},"reopened":{"filteredCount":0}},
{"number":4,"createdAt":"2026-05-01T00:00:00Z","mergedAt":null,"additions":1,"deletions":0,"author":{"login":"bo-rev"},"reviews":{"pageInfo":{"hasNextPage":false},"nodes":[]},"reopened":{"filteredCount":0}}]}}}}
JSON

cat >bin/gh <<'SH'
#!/usr/bin/env bash
here=$(cd "$(dirname "$0")/.." && pwd)
case "$1 ${2:-}" in
  "auth status") echo "github.com: Logged in as stub-user" ;;
  "api rate_limit") echo '{"resources":{"graphql":{"limit":5000,"remaining":4990}}}' ;;
  "api graphql") cat "$here/fixtures/pr-pages.json" ;;
  "--version "*) echo "gh version 2.60.1 (stub)" ;;
  *) echo "stub gh: unsupported: $*" >&2; exit 1 ;;
esac
SH
chmod +x bin/gh
