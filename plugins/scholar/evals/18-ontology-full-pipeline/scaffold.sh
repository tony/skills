#!/usr/bin/env bash
# Builds a tiny checked-out corpus and a tag the ontology pipeline can pin
# and harvest end to end.
set -euo pipefail

git init --quiet

mkdir -p tiny-lib/src
cat >tiny-lib/src/ports.py <<'PY'
class PortAdapter:
    """Wraps a third-party client behind the port interface."""


class EventBus:
    """Publishes domain events to subscribed handlers."""


class EventHandler:
    """Receives one domain event and acts on it."""
PY
git -C tiny-lib init --quiet
git -C tiny-lib add .
git -C tiny-lib -c user.name=eval -c user.email=eval@example.com commit --quiet -m "Add ports"
git -C tiny-lib tag v1.0.0

git -C tiny-lib remote add origin https://github.com/example/tiny-lib

mkdir -p .eval-state
cat >verify-brief.sh <<'SH'
#!/usr/bin/env bash
python3 "$1" notes/ontology/tiny-lib/ --check-brief >.eval-state/brief-gate.txt 2>&1
gate_status=$?
printf '%s\n' "$gate_status" >.eval-state/brief-gate.exit
cat .eval-state/brief-gate.txt
exit "$gate_status"
SH
chmod +x verify-brief.sh

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
