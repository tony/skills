#!/usr/bin/env bash
set -euo pipefail

mkdir -p bin codex-home .eval-state
cat >bin/codex <<'PY'
#!/usr/bin/env python3
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
args = sys.argv[1:]
if args == ["queue", "--help"]:
    print("Usage: codex queue --thread UUID --message TEXT")
    raise SystemExit(0)
thread = "0b6f2d1e-4c1a-4f7e-9a53-2d8e7a1c9b10"
if len(args) != 5 or args[:3] != ["queue", "--thread", thread] or args[3] != "--message":
    raise SystemExit("unexpected queue arguments")
line = args[4]
body = "It's literal: $(touch relay-injected) `touch relay-backtick` RELAY_BODY_END"
receipt = root / ".eval-state/receipt.json"
sends = json.loads(receipt.read_text())["sends"] + 1 if receipt.exists() else 1
receipt.write_text(json.dumps({
    "payload_matches": line.startswith("[relay/1 ") and line.endswith("] " + body),
    "sends": sends,
    "line": line,
}) + "\n")
print("queued item 7d1c2a90-0000-4000-8000-000000000001 for thread " + thread)
PY

cat >bin/sqlite3 <<'PY'
#!/usr/bin/env python3
import json
import pathlib
import sqlite3
import sys

root = pathlib.Path(__file__).resolve().parent.parent
if len(sys.argv) != 3:
    raise SystemExit("expected database and query")
with sqlite3.connect(sys.argv[1], uri=True) as db:
    rows = db.execute(sys.argv[2]).fetchall()
(root / ".eval-state/readback.json").write_text(json.dumps({
    "matched_item": "7d1c2a90-0000-4000-8000-000000000001" in sys.argv[2],
    "rows": len(rows),
}) + "\n")
for row in rows:
    print("|".join(str(value) for value in row))
PY

python3 - <<'PY'
import sqlite3
with sqlite3.connect("codex-home/queue_1.sqlite") as db:
    db.execute("CREATE TABLE queued_items (id TEXT, queue_order INTEGER, payload_json TEXT)")
PY
chmod +x bin/codex bin/sqlite3
