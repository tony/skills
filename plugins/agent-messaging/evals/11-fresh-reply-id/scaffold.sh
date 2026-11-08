#!/usr/bin/env bash
set -euo pipefail

mkdir -p bin codex-home .eval-state
cat >bin/codex <<'PY'
#!/usr/bin/env python3
import json
import pathlib
import re
import sqlite3
import sys

root = pathlib.Path(__file__).resolve().parent.parent
args = sys.argv[1:]
if args == ["queue", "--help"]:
    print("Usage: codex queue --thread UUID --message TEXT")
    raise SystemExit(0)
thread = "00000000-0000-4000-8000-000000000011"
if len(args) != 5 or args[:3] != ["queue", "--thread", thread] or args[3] != "--message":
    raise SystemExit("unexpected fixture queue arguments")
line = args[4]
match = re.fullmatch(r"\[relay/1 ([^\]]+)\] (.*)", line)
fields = dict(item.split("=", 1) for item in match[1].split()) if match else {}
receipt = root / ".eval-state/receipt.json"
sends = json.loads(receipt.read_text())["sends"] + 1 if receipt.exists() else 1
receipt.write_text(json.dumps({
    "sends": sends,
    "fresh_id": bool(fields.get("id")) and fields["id"] != "fixture-request-11",
    "hop_incremented": fields.get("hop") == "2",
    "ack_correlated": bool(match) and match[2] == "ACK fixture-request-11",
    "reply_bounded": fields.get("want") == "none",
    "line": line,
}) + "\n")
submission = "11000000-0000-4000-8000-000000000011"
with sqlite3.connect(root / "codex-home/queue_1.sqlite") as db:
    db.execute("INSERT INTO queued_items VALUES (?, ?, ?)", (submission, sends, line))
print("Queued message " + submission + " for thread " + thread + ".")
PY

cat >bin/sqlite3 <<'PY'
#!/usr/bin/env python3
import json
import pathlib
import sqlite3
import sys

root = pathlib.Path(__file__).resolve().parent.parent
with sqlite3.connect(sys.argv[1], uri=True) as db:
    rows = db.execute(sys.argv[2]).fetchall()
(root / ".eval-state/readback.json").write_text(json.dumps({
    "matched_item": "11000000-0000-4000-8000-000000000011" in sys.argv[2],
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
