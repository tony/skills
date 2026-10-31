"""Tests for run_tier.py using stub binaries."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004, D103
# pyright: reportUnusedCallResult=false, reportAny=false
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("run_tier.py")
SPEC = importlib.util.spec_from_file_location("run_tier", SCRIPT)
assert SPEC is not None
assert isinstance(SPEC.loader, importlib.machinery.SourceFileLoader)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_changed_state_graders_reject_added_baseline_or_status_claims() -> None:
    cases = Path(__file__).parents[1] / "evals"
    for case, target in (
        ("10-codex-timeout-dirty-tree", "app.py"),
        ("11-codex-timeout-already-dirty", "app.py"),
        ("12-codex-timeout-untracked-edit", "notes.txt"),
    ):
        pattern = next(
            line.removeprefix("    pattern: '").removesuffix("'")
            for line in (cases / case / "case.yaml").read_text().splitlines()
            if line.startswith("    pattern: '^No tier")
        )
        valid = (
            "No tier returned output.\n\n"
            f"- codex: timeout. The status check found {target} changed since the run began.\n\n"
            f"Open and review {target} before retrying.\n"
        )
        assert re.search(pattern, valid)
        for claim in ("It already had uncommitted changes.", "The file is untracked."):
            assert not re.search(
                pattern, valid.replace("Open and review", claim + " Open and review")
            )
            assert not re.search(pattern, valid + claim)


def stub(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "stub"
    path.write_text(f"#!/usr/bin/env bash\n{body}\n")
    path.chmod(0o755)
    return path


def tier(
    tmp_path: Path,
    binary: Path,
    prompt: str = "hello",
    timeout: str = "5",
    require: tuple[str, ...] = (),
) -> dict[str, object]:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(prompt)
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prompt-file",
            str(prompt_file),
            "--timeout",
            timeout,
            *[f"--require-flag={flag}" for flag in require],
            "--",
            str(binary),
            "-p",
            "--",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    return json.loads(out.stdout)


@pytest.mark.integration(reason="executes the tier CLI and a shell stub")
def test_ok_passes_prompt_as_one_last_argument(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, 'echo "$#:${@: -1}"'), prompt="two words\nline2")
    assert result["class"] == "ok"
    assert result["exit_code"] == 0
    assert result["stdout"] == "3:two words\nline2\n"


@pytest.mark.integration(reason="executes the tier CLI and shell stubs")
def test_credit_from_stderr_only(tmp_path: Path) -> None:
    failing = tier(tmp_path, stub(tmp_path, "echo RESOURCE_EXHAUSTED >&2; exit 1"))
    assert failing["class"] == "credit"
    quoted = tier(tmp_path, stub(tmp_path, "echo billing; exit 1"))
    assert quoted["class"] == "crash"
    bare = tier(tmp_path, stub(tmp_path, "echo billing >&2; exit 1"))
    assert bare["class"] == "crash"


@pytest.mark.integration(reason="executes the tier CLI and shell stubs")
def test_auth_and_unknown_model(tmp_path: Path) -> None:
    assert tier(tmp_path, stub(tmp_path, "echo 'Not logged in' >&2; exit 1"))["class"] == "auth"
    assert (
        tier(tmp_path, stub(tmp_path, "echo 'unknown model x' >&2; exit 1"))["class"]
        == "unknown-model"
    )


@pytest.mark.integration(reason="executes the tier CLI and shell stubs")
def test_empty_and_rate_limit(tmp_path: Path) -> None:
    assert tier(tmp_path, stub(tmp_path, "exit 0"))["class"] == "empty"
    assert (
        tier(tmp_path, stub(tmp_path, "echo 'rate limit exceeded' >&2; exit 1"))["class"]
        == "rate-limit"
    )


@pytest.mark.integration(reason="terminates an owned process group through the tier CLI")
def test_timeout_kills_the_process_group(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, "sleep 30 & sleep 30"), timeout="0.5")
    assert result["class"] == "timeout"
    assert result["exit_code"] is None
    assert float(str(result["elapsed"])) < 5


@pytest.mark.integration(reason="executes the tier CLI with a missing child binary")
def test_missing_binary_is_crash(tmp_path: Path) -> None:
    result = tier(tmp_path, tmp_path / "absent")
    assert result["class"] == "crash"
    assert result["exit_code"] == 127


@pytest.mark.integration(reason="executes the tier CLI and a shell stub")
def test_oversized_prompt_is_passed_as_a_file_reference(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, 'echo "${@: -1}"'), prompt="x" * 200_000)
    assert result["class"] == "ok"
    assert str(tmp_path / "prompt.txt") in str(result["stdout"])


HELP_STUB = 'if [ "$1" = --help ]; then echo "  --sandbox <MODE>"; exit 0; fi; echo ran'


@pytest.mark.integration(reason="executes the tier CLI and a shell help stub")
def test_required_flag_present_runs_the_tier(tmp_path: Path) -> None:
    result = tier(tmp_path, stub(tmp_path, HELP_STUB), require=("--sandbox",))
    assert result["class"] == "ok"


@pytest.mark.integration(reason="executes a shell help stub")
def test_codex_help_advertises_canonical_flag_not_alias(tmp_path: Path) -> None:
    flag = "--dangerously-bypass-approvals-and-sandbox"
    binary = stub(
        tmp_path,
        f'test "$1" = exec && test "$2" = --help || exit 2\necho "      {flag}"',
    )
    assert runner.missing_flags([str(binary), "exec", flag], [flag]) == []
    assert runner.missing_flags([str(binary), "exec", "--yolo"], ["--yolo"]) == ["--yolo"]


@pytest.mark.integration(reason="executes the tier CLI and a shell help stub")
def test_required_flag_missing_runs_nothing(tmp_path: Path) -> None:
    marker = tmp_path / "ran"
    body = f'if [ "$1" = --help ]; then echo "  --other"; exit 0; fi; touch {marker}; echo ran'
    result = tier(tmp_path, stub(tmp_path, body), require=("--sandbox",))
    assert result["class"] == "unsupported-flag"
    assert "--sandbox" in str(result["stderr"])
    assert not marker.exists()


@pytest.mark.integration(reason="executes the tier CLI and a shell help stub")
def test_flag_must_match_whole_word(tmp_path: Path) -> None:
    body = 'if [ "$1" = --help ]; then echo "--sandbox-mode"; exit 0; fi; echo ran'
    result = tier(tmp_path, stub(tmp_path, body), require=("--sandbox",))
    assert result["class"] == "unsupported-flag"


@pytest.mark.integration(reason="executes the tier CLI argument validation")
@pytest.mark.parametrize("timeout", ["5m", "nan", "inf", "0", "-1"])
def test_invalid_timeout_stops_before_help_or_task(tmp_path: Path, timeout: str) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hi")
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prompt-file",
            str(prompt_file),
            "--timeout",
            timeout,
            "--require-flag=--sandbox",
            "--",
            str(stub(tmp_path, "touch reached; echo --sandbox")),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert out.returncode == 2
    assert "invalid --timeout" in out.stderr
    assert "Traceback" not in out.stderr
    assert not (tmp_path / "reached").exists()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tracked.txt").write_text("original\n")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=eval",
            "-c",
            "user.email=eval@example.com",
            "commit",
            "-qm",
            "init",
        ],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "tracked.txt").write_text("user edit\n")
    (tmp_path / "notes.txt").write_text("user notes\n")
    return tmp_path


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
@pytest.mark.parametrize(
    ("edit", "path"),
    [
        ("printf changed >../tracked.txt", "tracked.txt"),
        ("printf changed >../notes.txt", "notes.txt"),
        ("git update-index --chmod=+x ../tracked.txt", "tracked.txt"),
        ("ln -s missing ../link", "link"),
    ],
)
def test_failed_tier_checks_dirty_files_and_index_from_subdirectory(
    repo: Path, edit: str, path: str
) -> None:
    subdir = repo / "src"
    subdir.mkdir()
    result = tier(
        subdir,
        stub(repo, f"{edit}; echo 'Authentication required' >&2; exit 1"),
    )
    assert result["class"] == "auth"
    assert result["state_check"] == {"status": "changed", "paths": [path], "history_changed": False}


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
def test_help_probe_edits_are_included_in_state_check(repo: Path) -> None:
    result = tier(
        repo,
        stub(repo, "printf changed >tracked.txt; echo --other"),
        require=("--sandbox",),
    )
    assert result["class"] == "unsupported-flag"
    assert result["state_check"] == {
        "status": "changed",
        "paths": ["tracked.txt"],
        "history_changed": False,
    }


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
def test_detaching_head_is_a_change_even_when_files_match(repo: Path) -> None:
    result = tier(repo, stub(repo, "git checkout --detach -q; exit 1"))
    assert result["state_check"] == {"status": "changed", "paths": [], "history_changed": True}


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
def test_unchanged_dirty_tree_allows_fallback(repo: Path) -> None:
    result = tier(repo, stub(repo, "exit 1"))
    assert result["state_check"] == {"status": "unchanged", "paths": [], "history_changed": False}


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
def test_special_file_reports_why_state_is_unavailable(repo: Path) -> None:
    (repo / "pipe").write_text("tracked\n")
    subprocess.run(["git", "add", "pipe"], cwd=repo, check=True)
    (repo / "pipe").unlink()
    os.mkfifo(repo / "pipe")
    result = tier(repo, stub(repo, "exit 1"))
    assert result["state_check"] == {
        "status": "unavailable",
        "paths": [],
        "reason": "repository state includes a submodule or special file: pipe",
    }


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
def test_tracked_configuration_is_checked_even_when_ignored(repo: Path) -> None:
    (repo / ".gitignore").write_text(".gitmodules\n")
    (repo / ".gitmodules").write_text("original\n")
    subprocess.run(["git", "add", "-f", ".gitmodules"], cwd=repo, check=True)
    result = tier(repo, stub(repo, "printf changed >.gitmodules; exit 1"))
    assert result["state_check"] == {
        "status": "changed",
        "paths": [".gitmodules"],
        "history_changed": False,
    }


@pytest.mark.integration(reason="uses an owned Git repository and the tier CLI")
@pytest.mark.parametrize("channel", ["stdout", "stderr", "help"])
def test_invalid_output_bytes_retain_state_check(repo: Path, channel: str) -> None:
    body = "printf changed >tracked.txt; printf '\\377'"
    if channel == "stderr":
        body += " >&2"
    result = tier(repo, stub(repo, body), require=("--sandbox",) if channel == "help" else ())
    assert result["state_check"] == {
        "status": "changed",
        "paths": ["tracked.txt"],
        "history_changed": False,
    }


@pytest.mark.integration(
    reason="terminates owned help-probe processes and verifies file-lock release"
)
@pytest.mark.parametrize("parent_exits", [False, True])
def test_help_probe_terminates_children(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parent_exits: bool
) -> None:
    child = tmp_path / "child.py"
    child.write_text("""import fcntl, signal
with open('child.lock', 'w') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    print('ready', flush=True)
    signal.pause()
""")
    binary = tmp_path / "help"
    binary.write_text(
        f"""#!{sys.executable}
import signal, subprocess, sys
child = subprocess.Popen([sys.executable, 'child.py'], stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
assert child.stdout.readline() == b'ready\\n'
print('--sandbox', flush=True)
"""
        + ("" if parent_exits else "signal.pause()\n")
    )
    binary.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    execute = runner._execute  # noqa: SLF001

    def short_probe(command: list[str], timeout: float) -> dict[str, object]:
        assert timeout == 30
        return execute(command, timeout=0.5)

    monkeypatch.setattr(runner, "_execute", short_probe)
    expected = [] if parent_exits else ["--sandbox"]
    assert runner.missing_flags([str(binary)], ["--sandbox"]) == expected
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import fcntl; lock = open('child.lock'); fcntl.flock(lock, fcntl.LOCK_EX)",
        ],
        timeout=0.5,
        check=True,
    )


@pytest.mark.parametrize(
    "stderr",
    [
        'raise AuthenticationError("api key missing")',
        '    raise RateLimit("429 Too Many Requests")',
        'print("quota exceeded")',
        '  File "client.py", line 429, in call',
        "assert status != 401  # unauthorized",
        "the docs say: log in first, then retry",
        "rate limit handler here",
        "authentication helper loaded",
        "usage limit docs",
        "api key rotation notes",
    ],
)
def test_echoed_code_is_a_crash_not_a_vendor_failure(stderr: str) -> None:
    got = runner.classify(exit_code=1, timed_out=False, stdout="", stderr=stderr)
    assert got == "crash"


@pytest.mark.parametrize(
    ("stderr", "want"),
    [
        ("warning: retrying\nError: 429 Too Many Requests", "rate-limit"),
        ("ERROR: You've hit your usage limit.", "credit"),
        ("Please log in to continue", "auth"),
        (
            "\u26a0 Workspace Trust Required\n\nPass --trust, --yolo, or -f to trust it",
            "untrusted",
        ),
        ("HTTP 401 Unauthorized", "auth"),
        ("Authentication required. Please run 'agent login'", "auth"),
        ("Rate limit exceeded, retry in 20s", "rate-limit"),
        ("stream error: HTTP 429 Too Many Requests", "rate-limit"),
        ("Error: Cannot use this model: x", "unknown-model"),
    ],
)
def test_error_lines_still_classify(stderr: str, want: str) -> None:
    assert runner.classify(exit_code=1, timed_out=False, stdout="", stderr=stderr) == want


@pytest.mark.integration(reason="executes the tier CLI and a shell stub")
def test_stdin_mode_keeps_the_prompt_out_of_argv(tmp_path: Path) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("secret prompt\n" + "x" * 150_000)
    binary = stub(tmp_path, 'echo "args:$#"; wc -c')
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prompt-file",
            str(prompt_file),
            "--stdin",
            "--",
            str(binary),
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    result = json.loads(out.stdout)
    assert result["class"] == "ok"
    assert str(result["stdout"]).split() == ["args:1", "150014"]


def test_permission_flags_are_derived_from_the_command() -> None:
    command = ["agent", "-p", "--mode", "plan", "--trust", "--model", "m", "--"]
    assert runner.required_flags(command, []) == ["--mode", "--trust"]
    assert runner.required_flags(["codex", "exec", "--sandbox", "read-only", "-"], ["--x"]) == [
        "--sandbox",
        "--x",
    ]


@pytest.mark.integration(reason="executes the tier CLI and a shell help stub")
def test_derived_flag_missing_from_help_runs_nothing(tmp_path: Path) -> None:
    binary = stub(tmp_path, 'case " $* " in *" --help "*) echo "  -p"; exit 0;; esac; echo ran')
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("hi")
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--prompt-file",
            str(prompt_file),
            "--tier-number",
            "2",
            "--",
            str(binary),
            "-p",
            "--sandbox",
            "read-only",
            "--",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    result = json.loads(out.stdout)
    assert result["class"] == "unsupported-flag"
    ledger = json.loads((tmp_path / "prompt.txt.ledger").read_text())
    assert ledger == {"tier": 2, "class": "unsupported-flag", "elapsed": 0.0}
