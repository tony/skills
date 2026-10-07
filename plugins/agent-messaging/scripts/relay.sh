#!/usr/bin/env bash
# Deterministic helpers for session-relay: envelope composition, inbox-socket
# send, and transcript audit. Portable across GNU and BSD/Darwin; needs jq.
set -euo pipefail

MAX_HOP=4
MAX_BODY=800

die() { printf 'relay.sh: %s\n' "$1" >&2; exit "${2:-2}"; }

usage() {
  cat <<'USAGE'
relay.sh envelope --from ROLE:AGENT[@ADDR] --to ROLE (--hop N | --after-hop N)
                  [--want reply|ack|none] [--seq N] (--body TEXT | --body -)
relay.sh socket-send --socket PATH (--line TEXT | --line -)
relay.sh audit --id RELAY_ID --transcript FILE
relay.sh selftest
USAGE
}

# Percent-encode the characters that end or split a header value.
enc() { printf '%s' "$1" | sed -e 's/%/%25/g' -e 's/]/%5D/g' -e 's/ /%20/g'; }

cmd_envelope() {
  local from='' to='' hop='' want='none' seq='' body='' have_body=0
  while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "$1 needs a value"
    case $1 in
      --from) from=${2-}; shift 2 ;;
      --to) to=${2-}; shift 2 ;;
      --hop) hop=${2-}; shift 2 ;;
      --after-hop)
        case ${2-} in ''|*[!0-9]*) die "--after-hop needs a number" ;; esac
        hop=$(($2 + 1)); shift 2 ;;
      --want) want=${2-}; shift 2 ;;
      --seq) seq=${2-}; shift 2 ;;
      --body) body=${2-}; have_body=1; shift 2 ;;
      *) die "envelope: unknown argument $1" ;;
    esac
  done
  [ -n "$from" ] && [ -n "$to" ] && [ -n "$hop" ] && [ "$have_body" = 1 ] \
    || die "envelope: --from, --to, --hop (or --after-hop), and --body are required"
  case $hop in ''|*[!0-9]*) die "--hop needs a number" ;; esac
  [ "$hop" -le "$MAX_HOP" ] || die "hop $hop exceeds the cap of $MAX_HOP; do not send" 4
  case $want in reply|ack|none) ;; *) die "--want must be reply, ack, or none" ;; esac
  [ "$body" = '-' ] && body=$(cat)
  case $body in *$'\n'*|*$'\r'*) die "body must be a single line" ;; esac
  [ -n "$body" ] || die "body is empty"
  [ "${#body}" -le "$MAX_BODY" ] || die "body is ${#body} characters; the cap is $MAX_BODY" 5

  local who=${from%%@*} addr=''
  case $from in *@*) addr=${from#*@} ;; esac
  case $who in *:*) ;; *) die "--from must look like ROLE:AGENT[@ADDR]" ;; esac
  if [ -z "$addr" ]; then
    [ "$want" = none ] || die "no address: a reply cannot be routed, use --want none" 3
    addr=unknown
  fi
  [ -n "$seq" ] || seq="$(date +%s)-$$"
  local e_who e_addr e_to id
  e_who=$(enc "$who"); e_addr=$(enc "$addr"); e_to=$(enc "$to")
  id="${e_addr}-${seq}"
  printf '[relay/1 from=%s@%s to=%s id=%s hop=%s want=%s] %s\n' \
    "$e_who" "$e_addr" "$e_to" "$id" "$hop" "$want" "$body"
}

cmd_socket_send() {
  local sock='' line='' have=0
  while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "$1 needs a value"
    case $1 in
      --socket) sock=${2-}; shift 2 ;;
      --line) line=${2-}; have=1; shift 2 ;;
      *) die "socket-send: unknown argument $1" ;;
    esac
  done
  [ -n "$sock" ] && [ "$have" = 1 ] || die "socket-send: --socket and --line are required"
  [ "$line" = '-' ] && line=$(cat)
  [ -z "${CODEX_SANDBOX_NETWORK_DISABLED-}" ] \
    || die "sandbox blocks sockets (CODEX_SANDBOX_NETWORK_DISABLED set); use tmux or codex queue" 6
  command -v nc >/dev/null || die "nc not found; use tmux" 6
  command -v jq >/dev/null || die "jq not found" 6
  [ -S "$sock" ] || die "not a socket: $sock; the session is gone or the path is stale" 7
  local flags=(-U -w 3)
  nc -h 2>&1 | grep -q -e '-N' && flags=(-U -N -w 3)
  jq -nc --arg content "$line" '{type:"user",message:{role:"user",content:$content}}' \
    | nc "${flags[@]}" "$sock" \
    || die "nc could not send (sandbox blocks the socket, or the peer refused); use tmux or codex queue" 6
}

cmd_audit() {
  local id='' file=''
  while [ $# -gt 0 ]; do
    [ $# -ge 2 ] || die "$1 needs a value"
    case $1 in
      --id) id=${2-}; shift 2 ;;
      --transcript) file=${2-}; shift 2 ;;
      *) die "audit: unknown argument $1" ;;
    esac
  done
  [ -n "$id" ] && [ -f "$file" ] || die "audit: --id and an existing --transcript are required"
  jq -c --arg needle "id=$id " '
    select((.origin or .attachment.origin?) and (tostring | contains($needle)))
    | {origin: (.origin // .attachment.origin),
       content: (.message.content // .attachment // .content)}
  ' "$file"
}

cmd_selftest() {
  local self=$0 dir fail=0 out
  dir=$(mktemp -d "${TMPDIR:-/tmp}/relay-selftest.XXXXXX")
  trap 'rm -rf "$dir"' RETURN
  check() { # name, expected-substring, actual
    case $3 in *"$2"*) ;; *) printf 'FAIL %s: want %s got %s\n' "$1" "$2" "$3"; fail=1 ;; esac
  }
  out=$("$self" envelope --from 'planner:codex@a b]c to=x%' --to rev --hop 0 --seq 1 --want reply --body hi)
  check encoding 'from=planner:codex@a%20b%5Dc%20to=x%25 ' "$out"
  check id 'id=a%20b%5Dc%20to=x%25-1 ' "$out"
  out=$("$self" envelope --from p:c@s --to r --after-hop 2 --seq 1 --body hi)
  check after-hop 'hop=3 ' "$out"
  out=$("$self" envelope --from p:c@s --to r --after-hop 4 --body hi 2>&1) && fail=1
  check hop-cap 'exceeds the cap' "$out"
  out=$("$self" envelope --from p:c --to r --hop 0 --want reply --body hi 2>&1) && fail=1
  check no-address 'use --want none' "$out"
  out=$("$self" envelope --from p:c --to r --hop 0 --seq 1 --body hi)
  check unknown-addr 'from=p:c@unknown ' "$out"
  out=$("$self" envelope --from p:c@s --to r --hop 0 --body $'a\nb' 2>&1) && fail=1
  check multiline 'single line' "$out"
  out=$(printf "it's done" | "$self" envelope --from p:c@s --to r --hop 0 --seq 1 --body -)
  check stdin-body "] it's done" "$out"
  out=$("$self" envelope --from p:c@s --to r --hop 0 --body "$(head -c 900 /dev/zero | tr '\0' x)" 2>&1) && fail=1
  check body-cap 'the cap is' "$out"

  cat >"$dir/t.jsonl" <<'JSON'
{"origin":{"kind":"peer","verifiedPeerPid":7},"message":{"content":"[relay/1 from=a@b to=c id=b-1 hop=0 want=none] one"}}
{"origin":{"kind":"human"},"message":{"content":"[relay/1 from=a@b to=c id=b-10 hop=0 want=none] ten"}}
{"attachment":{"origin":{"kind":"peer","from":"unknown","verifiedPeerPid":9},"prompt":"[relay/1 from=a@b to=c id=b-2 hop=0 want=none] two"}}
JSON
  out=$("$self" audit --id b-1 --transcript "$dir/t.jsonl")
  check audit-whole-id '"verifiedPeerPid":7' "$out"
  check audit-content 'one' "$out"
  [ "$(printf '%s\n' "$out" | wc -l | tr -d ' ')" = 1 ] || { echo "FAIL audit matched id=b-10"; fail=1; }
  out=$("$self" audit --id b-2 --transcript "$dir/t.jsonl")
  check audit-attachment '"verifiedPeerPid":9' "$out"

  if command -v nc >/dev/null && command -v jq >/dev/null; then
    local sock="$dir/s.sock"
    nc -l -U "$sock" >"$dir/got" 2>/dev/null &
    local pid=$! i=0
    while [ ! -S "$sock" ] && [ $i -lt 50 ]; do i=$((i + 1)); sleep 0.1; done
    if [ -S "$sock" ]; then
      "$self" socket-send --socket "$sock" --line 'x y' || true
      wait "$pid" 2>/dev/null || true
      check socket-frame '"content":"x y"' "$(cat "$dir/got")"
    else
      kill "$pid" 2>/dev/null || true
      echo "SKIP socket-send: nc cannot listen on a unix socket here"
    fi
  else
    echo "SKIP socket-send: nc or jq missing"
  fi
  [ "$fail" = 0 ] && echo "selftest ok"
  return "$fail"
}

sub=${1-}; [ $# -gt 0 ] && shift
case $sub in
  envelope) cmd_envelope "$@" ;;
  socket-send) cmd_socket_send "$@" ;;
  audit) cmd_audit "$@" ;;
  selftest) cmd_selftest ;;
  *) usage >&2; exit 2 ;;
esac
