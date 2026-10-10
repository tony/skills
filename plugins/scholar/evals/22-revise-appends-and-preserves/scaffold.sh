#!/usr/bin/env bash
set -euo pipefail

proposal_case_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p notes/ontology/port-guide
cp -R "$proposal_case_dir/seed/notes/ontology/port-guide/." notes/ontology/port-guide/
cp "$proposal_case_dir/seed/USER-NOTES.txt" USER-NOTES.txt
