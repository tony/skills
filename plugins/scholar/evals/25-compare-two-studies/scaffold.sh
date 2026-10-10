#!/usr/bin/env bash
# Builds two small distilled studies with a planted mapping (adapter /
# connector), a planted collision (bus) and one-sided coverage (retry, cache).
set -euo pipefail

mkdir -p notes/ontology/alpha notes/ontology/beta
cat >notes/ontology/alpha/terms.jsonl <<'JSON'
{"schema":1,"term":"role","definition":"names the part a module plays","kind":"type","parent":"root","cites":[{"source":"alpha","locator":"README:1","quote":"every module plays one role"}]}
{"schema":1,"term":"adapter","definition":"wraps a third-party client behind the port interface","kind":"role","parent":"role","cites":[{"source":"alpha","locator":"src/a.py:1","quote":"wraps a client behind the port"}]}
{"schema":1,"term":"bus","definition":"publishes domain events to subscribed handlers","kind":"role","parent":"role","cites":[{"source":"alpha","locator":"src/a.py:5","quote":"delivers events to subscribers"}]}
{"schema":1,"term":"retry","definition":"sends a failed request again after a delay","kind":"verb","parent":"role","cites":[{"source":"alpha","locator":"src/a.py:9","quote":"sends the request again"}]}
JSON
cat >notes/ontology/beta/terms.jsonl <<'JSON'
{"schema":1,"term":"role","definition":"names the part a module plays","kind":"type","parent":"root","cites":[{"source":"beta","locator":"README:1","quote":"every module plays one role"}]}
{"schema":1,"term":"connector","definition":"wraps a third-party client behind the port interface","kind":"role","parent":"role","cites":[{"source":"beta","locator":"src/b.py:1","quote":"wraps a client behind the port"}]}
{"schema":1,"term":"bus","definition":"a shared memory region that carries data between processes","kind":"role","parent":"role","cites":[{"source":"beta","locator":"src/b.py:5","quote":"shared region carrying data"}]}
{"schema":1,"term":"cache","definition":"keeps a computed value to avoid computing it twice","kind":"role","parent":"role","cites":[{"source":"beta","locator":"src/b.py:9","quote":"keeps the computed value"}]}
JSON

cat >.gitignore <<'MD'
.bash_profile
.bashrc
.claude
.eval-artifacts
.gitconfig
.profile
.zprofile
.zshrc
MD
