"""Copy one owned fixture and retain input hashes outside the agent's workspace."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import uuid
from pathlib import Path


def scaffold(name: str, destination: Path, case: str = "") -> Path:
    """Prepare a local-only case and return its verification record."""
    source = Path(__file__).parents[1] / "fixtures" / name
    project = destination / "project"
    _ = shutil.copytree(source, project, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (destination / "outputs").mkdir()
    _ = (destination / "CLAUDE.md").write_text(
        """# Owned README fixture

Read only the supplied project and loaded plugin. Write deliverables under outputs/.
Keep project/ inputs unchanged. Do not use network, personal history, global
configuration or another checkout. Examples refer to the project root.
Generated-font edits belong in a copy at outputs/project/.
""",
        encoding="utf-8",
    )
    hashes = {
        p.relative_to(project).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in project.rglob("*")
        if p.is_file()
    }
    output = Path(__file__).parents[1] / "results" / os.environ.get("README_EVAL_ROUND", "round-1")
    output.mkdir(parents=True, exist_ok=True)
    record = output / f"{name}-{uuid.uuid4().hex}.json"
    _ = record.write_text(
        json.dumps(
            {
                "case": case or name,
                "fixture": name,
                "root": str(destination),
                "input_sha256": hashes,
            }
        ),
        encoding="utf-8",
    )
    return record


if __name__ == "__main__":
    _ = scaffold(sys.argv[1], Path.cwd(), sys.argv[2])
