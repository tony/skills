"""Smoke test: a rendered apply.sh creates a fixup on a temp repo."""

# ruff: noqa: S101, S603, S607, INP001, D103
# pyright: reportAny=false, reportUnusedCallResult=false

import os
import subprocess
from pathlib import Path

import pytest
import render_apply  # pyright: ignore[reportImplicitRelativeImport]

EXIT_APPLY_FAILED = 3
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=ENV,
        check=True,
        capture_output=True,
        text=True,
    )
    return done.stdout.strip()


def run_sh(script: Path, repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(script)],
        cwd=repo,
        env=ENV,
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration(reason="uses owned Git repositories and rendered apply.sh")
def test_apply_creates_fixup_for_dotted_finding_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("robust line\nkeep\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "add a")
    target = git(repo, "rev-parse", "--short", "HEAD")
    base_a = base = git(repo, "rev-parse", "HEAD")

    registry = tmp_path / "signatures.yml"
    registry.write_text("version: 1\n")
    run_dir = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "deslop" / "t-1"
    run_dir.mkdir(parents=True)
    (run_dir / "0000-PLAN.md").write_text("plan\n")
    patch = run_dir / f"0001-fixup-{target}-ai-slop.flagship-phrases.patch"
    patch.write_text("--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n-robust line\n+line\n keep\n")

    rc = render_apply.main(
        [
            "--run-dir",
            str(run_dir),
            "--registry",
            str(registry),
            "--baseline",
            base,
            "--trunk-ref",
            "origin/main",
        ]
    )
    assert rc == 0
    script = run_dir / "apply.sh"
    assert "__REGISTRY" not in script.read_text()

    first = run_sh(script, repo)
    assert first.returncode == 0, first.stderr
    backup = first.stdout.split("Backup branch: ", 1)[1].split()[0]
    assert backup.startswith("main-pre-deslop-")
    assert git(repo, "rev-parse", backup) == base
    assert git(repo, "log", "-1", "--format=%s") == f"fixup! {base_a}"
    assert (repo / "a.txt").read_text() == "line\nkeep\n"
    assert git(repo, "status", "--porcelain") == ""

    again = run_sh(script, repo)
    assert again.returncode == 0, again.stderr
    assert f"Backup branch: {backup}" in again.stdout
    assert git(repo, "branch", "--list", "*-pre-deslop-*").count("pre-deslop") == 1
    assert git(repo, "rev-list", "--count", "HEAD") == "2"

    registry.write_text("version: 2\n")
    locked = run_sh(script, repo)
    assert locked.returncode == 1


def test_render_rejects_unsafe_value() -> None:
    try:
        render_apply.render("x", 'a"b', "h", "b", "t")
    except ValueError:
        return
    raise AssertionError


@pytest.mark.integration(reason="uses owned Git repositories and rendered apply.sh")
def test_second_fixup_in_one_file_applies_only_when_cut_after_the_first(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("one\ntwo\nthree\nfour\n")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "add a")
    target = git(repo, "rev-parse", "--short", "HEAD")
    base = git(repo, "rev-parse", "HEAD")

    def cut(edits: list[tuple[str, str]], *, sequential: bool) -> list[str]:
        scratch = tmp_path / ("seq" if sequential else "indep")
        git(repo, "worktree", "add", "-q", "--detach", str(scratch), "HEAD")
        patches: list[str] = []
        for old, new in edits:
            path = scratch / "a.txt"
            path.write_text(path.read_text().replace(old, new))
            patches.append(git(scratch, "diff"))
            if sequential:
                git(scratch, "add", "a.txt")
            else:
                git(scratch, "checkout", "--", "a.txt")
        return patches

    edits = [("one\n", ""), ("three\n", "")]

    def run(patches: list[str], name: str) -> subprocess.CompletedProcess[str]:
        run_dir = tmp_path / name
        run_dir.mkdir()
        registry = tmp_path / "signatures.yml"
        registry.write_text("version: 1\n")
        for n, text in enumerate(patches, start=1):
            (run_dir / f"{n:04d}-fixup-{target}-x.y.patch").write_text(text + "\n")
        argv = ["--run-dir", str(run_dir), "--registry", str(registry)]
        assert render_apply.main([*argv, "--baseline", base, "--trunk-ref", "origin/main"]) == 0
        return run_sh(run_dir / "apply.sh", repo)

    bad = run(cut(edits, sequential=False), "bad")
    assert bad.returncode == EXIT_APPLY_FAILED
    git(repo, "reset", "-q", "--hard", base)
    good = run(cut(edits, sequential=True), "good")
    assert good.returncode == 0, good.stderr
    assert (repo / "a.txt").read_text() == "two\nfour\n"


@pytest.mark.integration(reason="uses owned Git repositories and rendered apply.sh")
def test_apply_stages_a_non_ascii_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    name = "café.md"
    (repo / name).write_text("robust line\n")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", "add notes")
    base = git(repo, "rev-parse", "HEAD")

    registry = tmp_path / "signatures.yml"
    registry.write_text("version: 1\n")
    run_dir = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "deslop" / "t-1"
    run_dir.mkdir(parents=True)
    (run_dir / "0000-PLAN.md").write_text("plan\n")
    patch = run_dir / f"0001-fixup-{base[:7]}-ai-slop.flagship-phrases.patch"
    patch.write_text(f"--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-robust line\n+line\n")
    argv = ["--run-dir", str(run_dir), "--registry", str(registry), "--baseline", base]
    assert render_apply.main([*argv, "--trunk-ref", "origin/main"]) == 0

    done = run_sh(run_dir / "apply.sh", repo)
    assert done.returncode == 0, done.stderr
    assert git(repo, "log", "-1", "--format=%s") == f"fixup! {base}"
    assert git(repo, "status", "--porcelain") == ""


@pytest.mark.integration(reason="uses owned Git repositories and rendered apply.sh")
@pytest.mark.parametrize("overlaps", [False, True])
def test_failed_hook_retains_concurrent_edits_and_backup(tmp_path: Path, overlaps: bool) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "a.txt").write_text("robust line\n")
    (repo / "user.txt").write_text("original\n")
    git(repo, "add", "a.txt", "user.txt")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD")
    run_dir = repo / ".git" / "deslop"
    run_dir.mkdir()
    registry = tmp_path / "registry.yml"
    registry.write_text("version: 1\n")
    (run_dir / f"0001-fixup-{base}-x.patch").write_text(
        "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-robust line\n+line\n"
    )
    hook = repo / ".git/hooks/pre-commit"
    target_edit = "printf 'concurrent target\\n' > a.txt\n" if overlaps else ""
    hook.write_text(
        f"""#!/bin/sh
printf 'concurrent staged\\n' > user.txt
git add -- user.txt
printf 'concurrent unstaged\\n' >> user.txt
{target_edit}exit 1
"""
    )
    hook.chmod(0o755)
    args = ["--run-dir", str(run_dir), "--registry", str(registry), "--baseline", base]
    assert render_apply.main([*args, "--trunk-ref", "origin/main"]) == 0
    done = run_sh(run_dir / "apply.sh", repo)
    assert done.returncode == 6  # noqa: PLR2004
    assert git(repo, "rev-parse", "HEAD") == base
    assert git(repo, "show", ":user.txt") == "concurrent staged"
    assert (repo / "user.txt").read_text() == "concurrent staged\nconcurrent unstaged\n"
    if overlaps:
        assert "rollback refused" in done.stderr
        assert (repo / "a.txt").read_text() == "concurrent target\n"
    else:
        assert "patch rolled back" in done.stderr
        assert (repo / "a.txt").read_text() == "robust line\n"
    backup = done.stdout.split("Backup branch: ", 1)[1].split()[0]
    assert git(repo, "rev-parse", backup) == base
