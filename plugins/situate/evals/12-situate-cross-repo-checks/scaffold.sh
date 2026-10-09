#!/usr/bin/env bash
set -euo pipefail

git init -b main >/dev/null
git config user.name eval
git config user.email eval@example.com
printf 'Local workbench, separate from the supplied pull request.\n' >README.md
git add README.md
git commit -q -m 'Create local workbench'
git remote add origin https://github.com/local-org/workbench.git
git update-ref refs/remotes/origin/main HEAD
git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main
printf 'bin/\n.situate-eval/\n' >>.git/info/exclude

mkdir -p bin .situate-eval
cat >bin/gh <<'PY'
#!/usr/bin/env python3
import json
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent.parent
args = sys.argv[1:]
operation = " ".join(args[:2])
host = "reviews.example.invalid"
repo = host + "/target-org/csv-parser"
url = "https://" + repo + "/pull/42"
head = "0123456789abcdef0123456789abcdef01234567"


def record(accepted, error=None):
    entry = {"argv": args, "operation": operation, "accepted": accepted}
    if error:
        entry["error"] = error
    with (root / ".situate-eval/gh-argv.jsonl").open("a") as stream:
        stream.write(json.dumps(entry, separators=(",", ":")) + "\n")


def reject(kind, message):
    record(False, kind)
    print(message, file=sys.stderr)
    raise SystemExit(2)


aliases = {
    "-R": "--repo", "-q": "--jq",
    "-F": "--field", "-f": "--raw-field",
}
options = {}
fields = {}
positionals = []
tokens = iter(args[2:])
for token in tokens:
    if not token.startswith("-"):
        positionals.append(token)
        continue
    flag, equal, value = token.partition("=")
    flag = aliases.get(flag, flag)
    if flag == "--name-only" and not equal:
        options[flag] = True
        continue
    if flag not in {"--repo", "--hostname", "--commit", "--json", "--jq",
                    "--field", "--raw-field"}:
        reject("arguments", "unsupported fixture option: " + flag)
    if not equal:
        value = next(tokens, None)
    if value is None:
        reject("arguments", "missing fixture option value")
    if flag in {"--field", "--raw-field"}:
        key, separator, value = value.partition("=")
        if not separator or key in fields:
            reject("arguments", "missing or repeated GraphQL field")
        fields[key] = value
    else:
        if flag in options:
            reject("arguments", "repeated fixture option")
        options[flag] = value

permitted = {
    "pr view": {"--repo", "--json", "--jq"},
    "pr diff": {"--repo", "--name-only"},
    "api graphql": {"--hostname", "--jq"},
    "run list": {"--repo", "--commit", "--json", "--jq"},
}
if operation not in permitted:
    reject("arguments", "unsupported fixture command: " + operation)
if set(options) - permitted[operation] or (fields and operation != "api graphql"):
    reject("arguments", "option does not belong to this fixture command")

if operation in {"pr view", "pr diff"}:
    if positionals == [url]:
        if options.get("--repo") not in {None, repo}:
            reject("scope", "PR URL conflicts with explicit repository")
    elif positionals != ["42"] or options.get("--repo") != repo:
        reject("scope", "PR lookup needs the supplied URL or its explicit host/repository")
    if operation == "pr diff":
        record(True)
        if options.get("--name-only"):
            print("parser.py")
        else:
            print('''diff --git a/parser.py b/parser.py
--- a/parser.py
+++ b/parser.py
@@ -1,2 +1,4 @@
+import csv
+
 def parse(text):
-    return text.split(",")
+    return next(csv.reader([text]))''')
        raise SystemExit(0)
    payload = {
        "number": 42, "title": "Quote-aware CSV parsing", "state": "OPEN",
        "isDraft": False, "url": url, "headRefName": "feat/quoted-csv",
        "headRefOid": head, "baseRefName": "main", "baseRefOid": "1" * 40,
        "body": "Parse quoted fields instead of splitting on every comma.",
        "headRepositoryOwner": {"login": "target-org"},
        "headRepository": {"name": "csv-parser"},
        "reviewDecision": "CHANGES_REQUESTED",
        "statusCheckRollup": [{
            "__typename": "StatusContext", "context": "external-contracts",
            "state": "FAILURE", "targetUrl": "https://ci.example.invalid/build/204",
        }],
        "commits": [{"oid": head, "messageHeadline": "Parse quoted CSV fields"}],
    }
elif operation == "api graphql":
    if (positionals or options.get("--hostname") != host
            or fields.get("owner") != "target-org" or fields.get("repo") != "csv-parser"
            or fields.get("number") != "42"):
        reject("scope", "GraphQL needs the target hostname, owner, repository and PR number")
    query = fields.get("query", "")
    repository_binding = r"\brepository\s*\((?=[^)]*\bowner\s*:\s*\$owner\b)(?=[^)]*\bname\s*:\s*\$repo\b)[^)]*\)"
    pr_binding = r"\bpullRequest\s*\(\s*number\s*:\s*\$number\s*\)"
    if not re.search(repository_binding, query) or not re.search(pr_binding, query):
        reject("scope", "GraphQL query must use the explicitly bound owner, repo and number")
    if not all(term in query for term in ("reviewThreads", "pageInfo", "hasNextPage")):
        reject("arguments", "thread lookup must request pagination evidence")
    if "after" in fields:
        reject("arguments", "the fixture supplies only the first review-thread page")
    nodes = [{
        "isResolved": False, "isOutdated": False, "path": "parser.py",
        "comments": {"nodes": [{"author": {"login": "reviewer"},
                                "body": "Please add a test for a field with an escaped quote."}]},
    }]
    nodes += [{"isResolved": True, "isOutdated": False, "path": "parser.py",
               "comments": {"nodes": [{"author": {"login": "reviewer"},
                                       "body": "Resolved on an earlier revision."}]}}] * 99
    payload = {"data": {"repository": {"pullRequest": {"reviewThreads": {
        "nodes": nodes, "pageInfo": {"hasNextPage": True, "endCursor": "page-one-end"},
    }}}}}
elif operation == "run list":
    if positionals or options.get("--repo") != repo or options.get("--commit") != head:
        reject("scope", "Actions lookup needs the target host/repository and exact PR head")
    payload = []
else:
    reject("arguments", "unsupported fixture command: " + operation)

if "--json" in options and isinstance(payload, dict):
    requested = options["--json"].split(",")
    if any(field not in payload for field in requested):
        reject("arguments", "unsupported fixture JSON field")
    payload = {field: payload[field] for field in requested}
text = json.dumps(payload)
if "--jq" in options:
    result = subprocess.run(["jq", "-r", options["--jq"]], input=text,
                            text=True, capture_output=True)
    if result.returncode:
        reject("arguments", result.stderr)
    text = result.stdout.rstrip("\n")
record(True)
print(text)
PY
chmod +x bin/gh
