"""Tests for tier_plan.py."""

# ruff: noqa: S101, S603, INP001, D103
# pyright: reportUnusedCallResult=false, reportAny=false
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("tier_plan.py")


def run(
    tmp_path: Path, tiers: list[str], *ran: str, extra: tuple[str, ...] = ()
) -> dict[str, object]:
    """Run the planner with ledger rows given as N:class:elapsed."""
    prompt = tmp_path / "prompt"
    prompt.write_text("x")
    ledger = tmp_path / "prompt.ledger"
    ledger.write_text(
        "".join(
            json.dumps({"tier": int(n), "class": cls, "elapsed": float(el)}) + "\n"
            for n, cls, el in (row.split(":") for row in ran)
        )
    )
    command = [sys.executable, str(SCRIPT), "--prompt-file", str(prompt), *extra]
    command += [arg for tier in tiers for arg in ("--tier", tier)]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.fixture
def tiers(tmp_path: Path) -> dict[str, list[str]]:
    """Real executables so the missing-binary check passes."""
    agy, agent, codex = (tmp_path / name for name in ("agy", "agent", "codex"))
    for path in (agy, agent, codex):
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
    return {
        "agy": [str(agy), str(agent), str(agy)],
        "codex": [str(codex), str(agent), str(agent)],
    }


@pytest.mark.parametrize(
    "cls", ["rate-limit", "auth", "untrusted", "credit", "crash", "unsupported-flag"]
)
def test_binary_failures_skip_same_binary_tier(
    tmp_path: Path, tiers: dict[str, list[str]], cls: str
) -> None:
    assert run(tmp_path, tiers["agy"], f"1:{cls}:1") == {"next": 2, "stop": None}
    assert run(tmp_path, tiers["agy"], f"1:{cls}:1", "2:timeout:5") == {
        "next": None,
        "stop": "no-tier",
    }


def test_timeout_and_unknown_model_keep_same_binary_tier(
    tmp_path: Path, tiers: dict[str, list[str]]
) -> None:
    codex = tiers["codex"]
    assert run(tmp_path, codex, "1:auth:1", "2:timeout:9") == {"next": 3, "stop": None}
    assert run(tmp_path, codex, "1:auth:1", "2:unknown-model:1") == {"next": 3, "stop": None}


def test_budget_is_twice_the_timeout(tmp_path: Path, tiers: dict[str, list[str]]) -> None:
    agy = tiers["agy"]
    extra = ("--timeout", "10")
    assert run(tmp_path, agy, "1:timeout:10", "2:timeout:10", extra=extra) == {
        "next": 3,
        "stop": None,
    }
    over = run(tmp_path, agy, "1:timeout:10", "2:timeout:10", "3:timeout:0.5", extra=extra)
    assert over["stop"] == "budget"
    assert run(tmp_path, agy, "1:timeout:99999", extra=("--timeout", "none")) == {
        "next": 2,
        "stop": None,
    }


def test_empty_normal_stops_and_empty_plan_moves_on_once(
    tmp_path: Path, tiers: dict[str, list[str]]
) -> None:
    codex = tiers["codex"]
    assert run(tmp_path, codex, "1:empty:1")["stop"] == "empty"
    assert run(tmp_path, codex, "1:empty:1", extra=("--plan",)) == {"next": 2, "stop": None}
    both = run(tmp_path, codex, "1:empty:1", "2:empty:1", extra=("--plan",))
    assert both["stop"] == "empty"


def test_no_ledger_starts_at_tier_one_and_missing_binaries_are_skipped(
    tmp_path: Path, tiers: dict[str, list[str]]
) -> None:
    prompt = tmp_path / "p"
    prompt.write_text("x")
    cmd = [sys.executable, str(SCRIPT), "--prompt-file", str(prompt)]
    first = subprocess.run(
        [*cmd, *(a for t in tiers["agy"] for a in ("--tier", t))],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(first.stdout) == {"next": 1, "stop": None}
    gone = ["/nonexistent/agy", tiers["agy"][1], "/nonexistent/agy"]
    second = subprocess.run(
        [*cmd, *(a for t in gone for a in ("--tier", t))],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(second.stdout) == {"next": 2, "stop": None}
    only = subprocess.run(
        [*cmd, "--tier", "/nonexistent/agy"], capture_output=True, text=True, check=True
    )
    assert json.loads(only.stdout) == {"next": None, "stop": "no-tier"}


def test_retry_is_allowed_once_and_refused_after_two_rows(
    tmp_path: Path, tiers: dict[str, list[str]]
) -> None:
    agent = tiers["codex"]
    once = run(tmp_path, agent, "2:unknown-model:1", extra=("--retry", "2"))
    assert once == {"next": 2, "stop": None}
    twice = run(tmp_path, agent, "2:unknown-model:1", "2:unknown-model:1", extra=("--retry", "2"))
    assert twice == {"next": None, "stop": "retry-cap"}
    third = run(tmp_path, agent, "2:crash:1", "2:crash:1", "2:crash:1")
    assert third == {"next": None, "stop": "retry-cap"}
