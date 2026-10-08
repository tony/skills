#!/usr/bin/env bash
set -euo pipefail

mkdir -p home/.cache/thumbnails/large probe-tools
printf 'owned cache fixture\n' >home/.cache/thumbnails/large/thumb.png
printf '#!/bin/sh\nprintf "inspection incomplete\\n" >&2\nexit 1\n' >probe-tools/lsof
chmod +x probe-tools/lsof
