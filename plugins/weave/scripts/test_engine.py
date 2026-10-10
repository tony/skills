"""Integration tests for engine.py: real git repositories, stub model CLIs on PATH."""

# ruff: noqa: S101, S603, INP001, PLR2004, D103, ARG001
# pyright: reportAny=false, reportUnusedParameter=false, reportUnusedCallResult=false
from __future__ import annotations

import io
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import engine  # pyright: ignore[reportImplicitRelativeImport]
import pytest

pytestmark = pytest.mark.integration


def sh(cwd: Path, *argv: str) -> str:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture(scope="module")
def repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("weave-repo")
    sh(root, "git", "init", "-q", "-b", "main")
    sh(root, "git", "config", "user.email", "t@example.com")
    sh(root, "git", "config", "user.name", "t")
    (root / "sub").mkdir()
    for name, text in (("a.txt", "one\n"), ("B", "b1\n"), ("C", "c1\n"), ("sub/S", "s1\n")):
        (root / name).write_text(text)
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def repo(tmp_path: Path, repo_template: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "work" / "Demo Repo"
    shutil.copytree(repo_template, root)
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.setenv("WEAVE_REPO", str(root))
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def bindir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "bin"
    path.mkdir()
    monkeypatch.setenv("PATH", f"{path}:/usr/bin:/bin")
    return path


def stub(bindir: Path, name: str, body: str) -> None:
    script = bindir / name
    script.write_text(f"#!/bin/sh\n{body}\n")
    script.chmod(0o755)


def init(
    command: str = "ask",
    backend: str = "subagents",
    *,
    mutating: bool = False,
    variants: int | None = None,
) -> engine.Json:
    return engine.init_session(
        command=command,
        backend=backend,
        repo=".",
        prompt_summary="q" * 200,
        passes=1,
        timeout="default",
        mutating=mutating,
        variants=variants,
    )


def prompt_file(session: engine.Json) -> Path:
    path = Path(session["session_dir"]) / "prompt.md"
    path.write_text("Question?")
    return path


def read_only_session(backend: str = "model-clis") -> tuple[Path, engine.Json]:
    doc = init(backend=backend)
    return Path(doc["session_dir"]), doc


def dispatch(sdir: Path, lane: str, **kw: object) -> engine.Json:
    kw.setdefault("timeout", 5)
    kw.setdefault("mutating", False)
    kw.setdefault("rate_wait", 0)
    return engine.dispatch_lane(
        sdir,
        lane,
        n=1,
        prompt_file=prompt_file({"session_dir": str(sdir)}),
        **kw,  # pyright: ignore[reportArgumentType]
    )


def user_state(repo: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    for p in sorted(repo.rglob("*")):
        if ".git" in p.relative_to(repo).parts or not p.is_file():
            continue
        state[str(p.relative_to(repo))] = p.read_text()
    return state


# --- session setup ---------------------------------------------------------


def test_init_writes_session_files(repo: Path) -> None:
    doc = init()
    sdir = Path(doc["session_dir"])
    session = json.loads((sdir / "session.json").read_text())
    assert session["participants"] == ["maintainer", "skeptic", "builder"]
    assert session["executors"]["skeptic"] == "host-native"
    assert session["worker_backend"] == "subagents"
    assert "models" not in session
    assert len(session["prompt_summary"]) == 120
    assert (sdir / "pass-0001" / "outputs").is_dir()
    assert not (sdir / "pass-0001" / "diffs").exists()
    assert (sdir / "metadata.md").is_file()
    event = json.loads((sdir / "events.jsonl").read_text().splitlines()[0])
    assert event["event"] == "session_start"
    assert event["worker_backend"] == "subagents"
    assert event["participants"] == ["maintainer", "skeptic", "builder"]
    assert (sdir.parents[2] / "repo.json").is_file()
    assert doc["trunk"] == "main"
    assert len(doc["baseline_sha"]) == 40
    assert doc["repo_dir"].startswith("demo-repo--")


def test_init_variants_lists_artifacts(repo: Path) -> None:
    doc = init(command="brainstorm", variants=2)
    assert doc["artifacts"][:3] == ["maintainer-v1", "maintainer-v2", "skeptic-v1"]
    assert (Path(doc["session_dir"]) / "outputs").is_dir()


def test_init_model_clis_roster_follows_installed_clis(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    stub(bindir, "agent", "exit 0")
    doc = init(backend="model-clis")
    assert doc["participants"] == ["claude", "agy", "gpt"]
    assert doc["executors"] == {"claude": "host", "agy": "agent", "gpt": "codex"}
    session = json.loads((Path(doc["session_dir"]) / "session.json").read_text())
    assert "agy: gemini-3.1-pro" in session["models"]


def test_update_drops_participant_and_links_latest(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    sdir = Path(init(backend="model-clis")["session_dir"])
    engine.update_session(
        sdir, status="completed", completed_passes=1, event="session_complete",
        event_json='{"x": 1}', drop=["claude"], sets=[], link_latest=True,
    )  # fmt: skip
    session = engine.load_session(sdir)
    assert session["status"] == "completed"
    assert session["participants"] == ["gpt"]
    assert "claude" not in session["executors"]
    assert (sdir.parent / "latest").resolve() == sdir.resolve()
    last = json.loads((sdir / "events.jsonl").read_text().splitlines()[-1])
    assert last["event"] == "session_complete"
    assert last["x"] == 1


def test_detect_reports_clis_and_search_tools(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    doc = engine.detect()
    assert doc["clis"] == {"agy": False, "codex": True, "agent": False}
    assert doc["lanes"]["agy"] is None
    assert doc["lanes"]["gpt"]["executor"] == "codex"
    assert doc["search"]["files"] in ("fd", "find")


# --- repo guard ------------------------------------------------------------

DIRTY_A = "one\nUSER-DIRTY-A\n"


def guarded_session(repo: Path) -> Path:
    (repo / "a.txt").write_text(DIRTY_A)
    (repo / "U").write_text("user untracked\n")
    return Path(init(backend="model-clis")["session_dir"])


def cli_writes(repo: Path) -> None:
    (repo / "B").write_text("b1\nCLI-B\n")
    (repo / "N").write_text("cli new\n")
    (repo / "newdir").mkdir()
    (repo / "newdir" / "M").write_text("x\n")
    with (repo / "a.txt").open("a") as fh:
        fh.write("CLI-A\n")


def test_guard_pin_and_index_untouched(repo: Path) -> None:
    (repo / "a.txt").write_text(DIRTY_A)
    sh(repo, "git", "add", "a.txt")
    index_before = (repo / ".git" / "index").read_bytes()
    sdir = Path(init(backend="model-clis")["session_dir"])
    session = engine.load_session(sdir)
    ref = f"refs/weave-guard/{session['session_id']}/pre"
    assert sh(repo, "git", "rev-parse", ref).strip() == session["guard"]["pre"]
    assert sh(repo, "git", "show", f"{ref}:a.txt") == DIRTY_A
    assert engine.guard_check(sdir)["violation"] is False
    assert (repo / ".git" / "index").read_bytes() == index_before


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_guard_rehashes_live_bytes_behind_index_shortcuts(repo: Path, flag: str) -> None:
    (repo / ".gitignore").write_text("a.txt\n")
    sh(repo, "git", "update-index", flag, "a.txt")
    sdir = Path(init()["session_dir"])
    index = (repo / ".git/index").read_bytes()
    (repo / "a.txt").write_text("hidden working edit\n")
    found = engine.guard_check(sdir)
    assert found["violation"] is True
    assert found["touched"] == {"a.txt": "M"}
    assert found["index_changed"] is False
    assert (repo / ".git/index").read_bytes() == index
    assert (Path(found["dir"]) / "post-copy/a.txt").read_text() == "hidden working edit\n"


def test_guard_detects_further_edit_of_dirty_file_and_never_mutates(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    after = user_state(repo)
    found = engine.guard_check(sdir, "agy")
    assert found["violation"] is True
    assert found["touched"] == {"a.txt": "M", "B": "M", "N": "A", "newdir/M": "A"}
    assert "U" not in found["touched"]
    vdir = Path(found["dir"])
    assert "CLI-A" in (vdir / "violation.patch").read_text()
    assert (vdir / "post-copy" / "a.txt").read_text() == DIRTY_A + "CLI-A\n"
    post_ref = f"refs/weave-guard/{engine.load_session(sdir)['session_id']}/post-{found['id']}"
    assert sh(repo, "git", "rev-parse", "--verify", post_ref).strip()
    assert user_state(repo) == after
    events = (sdir / "guard-events.jsonl").read_text()
    assert '"repo_guard_violation"' in events
    assert '"reverted": false' in events
    assert engine.guard_check(sdir, "gpt").get("repeat") is True


def test_guard_and_capture_survive_non_utf8_files(repo: Path) -> None:
    latin1 = b"caf\xe9\n"
    sdir = guarded_session(repo)
    (repo / "latin.txt").write_bytes(latin1)
    found = engine.guard_check(sdir, "agy")
    assert found["violation"] is True
    assert (Path(found["dir"]) / "violation.patch").read_bytes().count(b"caf") >= 1
    assert (Path(found["dir"]) / "post-copy" / "latin.txt").read_bytes() == latin1
    engine.guard_resolve(sdir, "revert")
    assert not (repo / "latin.txt").exists()
    wdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(wdir, ["maintainer"])
    wt = Path(engine.load_session(wdir)["worktrees"]["maintainer"]["path"])
    (wt / "latin.txt").write_bytes(latin1)
    cap = engine.capture_tree(wdir, 1, "maintainer", None)
    assert cap["changed"] == ["latin.txt"]
    assert latin1 in Path(cap["patch"]).read_bytes()


def test_guard_clean_run_has_no_violation(repo: Path) -> None:
    sdir = guarded_session(repo)
    assert engine.guard_check(sdir)["violation"] is False
    assert engine.guard_resolve(sdir, "revert")["action"] == "none"


def test_guard_keep_changes_nothing(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    after = user_state(repo)
    assert engine.guard_resolve(sdir, "keep")["action"] == "keep"
    assert user_state(repo) == after


def test_guard_revert_restores_only_touched_paths(repo: Path) -> None:
    sdir = guarded_session(repo)
    pre_tree = engine.load_session(sdir)["guard"]["tree"]
    (repo / "sub" / "S").write_text("s1\n")
    cli_writes(repo)
    done = engine.guard_resolve(sdir, "revert")
    assert done["clean"] is True
    assert (repo / "a.txt").read_text() == DIRTY_A
    assert (repo / "B").read_text() == "b1\n"
    assert not (repo / "N").exists()
    assert not (repo / "newdir").exists()
    assert (repo / "U").read_text() == "user untracked\n"
    assert engine.snapshot_tree(repo) == pre_tree
    assert sh(repo, "git", "diff", "--cached", "--name-only") == ""


def test_guard_revert_keeps_concurrent_user_edit_recoverable(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    (repo / "C").write_text("c1\nUSER-C-EDIT\n")
    found = engine.guard_check(sdir, "agy")
    assert found["touched"]["C"] == "M"
    engine.guard_resolve(sdir, "revert")
    assert (repo / "C").read_text() == "c1\n"
    sid = engine.load_session(sdir)["session_id"]
    post = sh(repo, "git", "show", f"refs/weave-guard/{sid}/post-{found['id']}:C")
    assert "USER-C-EDIT" in post
    assert "USER-C-EDIT" in (Path(found["dir"]) / "post-copy" / "C").read_text()
    assert (repo / "a.txt").read_text() == DIRTY_A


def test_guard_quarantine_stashes_everything_by_name(repo: Path) -> None:
    sdir = guarded_session(repo)
    cli_writes(repo)
    (repo / "C").write_text("c1\nUSER-C-EDIT\n")
    done = engine.guard_resolve(sdir, "quarantine")
    assert sh(repo, "git", "status", "--porcelain") == ""
    assert "weave-guard-" in sh(repo, "git", "stash", "list")
    assert "USER-C-EDIT" in sh(repo, "git", "show", "stash@{0}:C")
    assert "USER-DIRTY-A" in sh(repo, "git", "show", "stash@{0}:a.txt")
    assert "user untracked" in sh(repo, "git", "show", "stash@{0}^3:U")
    pre = engine.load_session(sdir)["guard"]["pre"]
    assert sh(repo, "git", "show", f"{pre}:a.txt") == DIRTY_A
    assert done["stash"]["sha"]


def test_guard_head_move_is_reported_not_undone(repo: Path) -> None:
    sdir = guarded_session(repo)
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", "escape")
    head = sh(repo, "git", "rev-parse", "HEAD")
    found = engine.guard_check(sdir)
    assert found["head_changed"] is True
    engine.guard_resolve(sdir, "revert")
    assert sh(repo, "git", "rev-parse", "HEAD") == head


def test_guard_finish_prunes_only_clean_sessions(repo: Path) -> None:
    sdir = guarded_session(repo)
    sid = engine.load_session(sdir)["session_id"]
    assert engine.guard_finish(sdir)["refs_pruned"] is True
    assert sh(repo, "git", "for-each-ref", f"refs/weave-guard/{sid}/") == ""
    dirty = guarded_session(repo)
    cli_writes(repo)
    done = engine.guard_finish(dirty)
    assert done["clean"] is False
    assert done["refs_pruned"] is False
    assert sh(repo, "git", "for-each-ref", "refs/weave-guard/")
    assert engine.guard_prune(".", 0.0)["dropped"]
    assert sh(repo, "git", "for-each-ref", "refs/weave-guard/") == ""


def test_dispatch_cli_sees_uncommitted_work_in_disposable_worktree(
    repo: Path, bindir: Path
) -> None:
    stub(bindir, "agy", 'cat a.txt U; echo "$PWD" >&2; echo scribble > scribble.txt')
    sdir = guarded_session(repo)
    doc = dispatch(sdir, "agy")
    assert doc["ok"], doc
    text = Path(doc["output"]).read_text()
    assert "USER-DIRTY-A" in text
    assert "user untracked" in text
    assert "agy-ro" in Path(doc["stderr"]).read_text()
    assert doc["guard_violations"] == []
    assert not (repo / "scribble.txt").exists()
    assert not list((sdir / "worktrees").glob("*"))
    assert len(sh(repo, "git", "worktree", "list").splitlines()) == 1


def test_dispatch_reports_an_escaped_write_without_reverting(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo escaped > "$WEAVE_REPO/escape.txt"; printf answer')
    sdir = guarded_session(repo)
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert len(doc["guard_violations"]) == 1
    assert (repo / "escape.txt").read_text() == "escaped\n"
    assert (repo / "a.txt").read_text() == DIRTY_A


# --- dispatch --------------------------------------------------------------


def test_dispatch_ok_composes_prompt(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'printf "%s" "$*" | grep -q read-only && printf "answer"')
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert Path(doc["output"]).read_text() == "answer"
    composed = (sdir / "pass-0001" / "prompts" / "gpt.md").read_text()
    assert composed.startswith("You are the Builder.")
    assert "READ-ONLY" in composed


def test_dispatch_variant_and_judge_paths(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'printf "%s" "$*"')
    sdir, _ = read_only_session()
    task = engine.lane_task(sdir, "gpt", n=1, variant=2, of=3)
    doc = dispatch(sdir, "gpt", task=task)
    assert doc["output"] == str(sdir / "outputs" / "gpt-v2.md")
    composed = (sdir / "pass-0001" / "prompts" / "gpt-v2.md").read_text()
    assert composed.startswith(engine.VARIANT_DIRECTIVE)
    assert "You are the Builder" not in composed
    judge = dispatch(sdir, "gpt", task=engine.lane_task(sdir, "gpt", n=1, judge=True))
    assert judge["output"] == str(sdir / "pass-0001" / "judges" / "gpt.md")
    assert not (sdir / "pass-0001" / "prompts" / "judge-gpt.md").read_text().startswith("You are")


def test_dispatch_credit_falls_back_to_agent_without_retry(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo "insufficient_quota" >&2; exit 1')
    stub(bindir, "agent", 'printf "from-agent"')
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert [a["class"] for a in doc["attempts"]] == ["credit", "ok"]
    assert doc["executor"] == "agent"
    assert doc["model"] == "gpt-5.4-high"


CREDIT_SAMPLES = (
    "RESOURCE_EXHAUSTED",
    "quota exceeded",
    "quota_exceeded",
    "insufficient_quota",
    "exceeded your current quota",
    "billing limit reached",
    "capacity exhausted",
    "usage limit",
)


def test_credit_samples_cover_every_pattern() -> None:
    for pattern in engine.CREDIT_PATTERNS:
        assert any(re.search(pattern, s, re.IGNORECASE) for s in CREDIT_SAMPLES), pattern


@pytest.mark.parametrize("text", CREDIT_SAMPLES)
def test_every_credit_string_is_classified(text: str) -> None:
    got = engine.classify(returncode=1, timed_out=False, output_size=0, stderr=f"x {text} y")
    assert got == "credit"


def test_bare_billing_is_not_credit() -> None:
    got = engine.classify(returncode=1, timed_out=False, output_size=0, stderr="billing")
    assert got == "crash"


def test_dispatch_rate_limit_retries_then_falls_back(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo "429 Too Many Requests" >&2; exit 1')
    stub(bindir, "agent", "exit 0")
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    classes = [a["class"] for a in doc["attempts"]]
    assert classes == ["rate-limit", "rate-limit", "empty", "empty", "empty", "empty"]
    assert doc["ok"] is False
    assert doc["failure_class"] == "empty"


def test_dispatch_crash_stops_lane(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "echo boom >&2; exit 3")
    stub(bindir, "agent", 'printf "never"')
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt")
    assert doc["failure_class"] == "crash"
    assert len(doc["attempts"]) == 1


def test_dispatch_timeout_grows_then_kills(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exec sleep 30")
    sdir, _ = read_only_session()
    doc = dispatch(sdir, "gpt", timeout=0.2)
    assert doc["failure_class"] == "timeout"
    assert "timeout=0.2" in Path(doc["stderr"]).read_text()
    assert "timeout=0.3" in Path(doc["stderr"]).read_text()


def test_lane_without_cli_is_unavailable(repo: Path, bindir: Path) -> None:
    sdir, _ = read_only_session()
    assert dispatch(sdir, "agy")["failure_class"] == "unavailable"


def test_argv_contract() -> None:
    wd = Path("/w")
    agy = engine.build_command("agy", "M", "P", mutating=False, workdir=wd)
    assert agy == ["agy", "--model", "M", "--add-dir", "/w", "--dangerously-skip-permissions",
                   "-p", "P"]  # fmt: skip
    codex = engine.build_command("codex", None, "P", mutating=False, workdir=wd)
    assert codex[:7] == ["codex", "exec", "-s", "read-only", "-C", "/w", "--skip-git-repo-check"]
    agent = engine.build_command("agent", "M", "P", mutating=False, workdir=wd)
    assert agent[:4] == ["agent", "-p", "--mode", "plan"]
    assert "-f" not in agent
    assert "--dangerously-bypass-approvals-and-sandbox" in engine.build_command(
        "codex", None, "P", mutating=True, workdir=wd
    )


# --- mutating sessions -----------------------------------------------------


def test_mutating_lane_runs_in_registered_worktree(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'echo built > made.txt; printf "explained"')
    doc = init(command="execute", backend="model-clis", mutating=True)
    sdir = Path(doc["session_dir"])
    made = engine.create_worktrees(sdir, ["gpt"], "20000101-000000")
    wt = Path(made["worktrees"]["gpt"]["path"])
    assert made["worktrees"]["gpt"]["branch"] == "weave/gpt/20000101-000000"
    result = dispatch(sdir, "gpt", mutating=True)
    assert result["ok"], result
    assert (wt / "made.txt").exists()
    assert not (repo / "made.txt").exists()
    index = (wt / ".git").read_text()
    cap = engine.capture_tree(sdir, 1, "gpt", None)
    assert cap["changed"] == ["made.txt"]
    assert "made.txt" in Path(cap["patch"]).read_text()
    assert sh(wt, "git", "diff", "--cached", "--name-only") == ""
    assert (wt / ".git").read_text() == index
    adopted = engine.adopt_files(sdir, 1, ["made.txt=gpt"], [])
    assert adopted["copied"] == ["made.txt"]
    assert (repo / "made.txt").read_text() == "built\n"
    with pytest.raises(engine.EngineError):
        engine.adopt_files(sdir, 1, ["../evil=gpt"], [])
    engine.remove_worktrees(sdir, None)
    assert not wt.exists()
    assert "weave/gpt" not in sh(repo, "git", "branch", "--list")
    assert engine.load_session(sdir)["worktrees"] == {}


@pytest.mark.parametrize(
    ("backend", "participant"), [("subagents", "maintainer"), ("model-clis", "claude")]
)
def test_capture_and_adopt_whole_participant(repo: Path, backend: str, participant: str) -> None:
    (repo / "B").write_text("staged user edit\n")
    sh(repo, "git", "add", "B")
    (repo / "B").write_text("working user edit\n")
    staged = sh(repo, "git", "diff", "--cached", "--binary")
    sdir = Path(init(command="execute", backend=backend, mutating=True)["session_dir"])
    engine.create_worktrees(sdir, [participant])
    wt = Path(engine.load_session(sdir)["worktrees"][participant]["path"])
    (wt / "a.txt").unlink()
    (wt / "sub" / "new.py").write_text("x = 1\n")
    sh(wt, "git", "add", "-A")
    sh(wt, "git", "commit", "-q", "-m", "worker ignored the no-commit protocol")
    worker_head = sh(wt, "git", "rev-parse", "HEAD")
    source_head = sh(repo, "git", "rev-parse", "HEAD")
    (wt / "sub/new.py").write_text("x = 2\n")
    sh(wt, "git", "add", "sub/new.py")
    (wt / "sub/new.py").write_text("x = 3\n")
    (wt / "uncaptured").symlink_to("missing-target")
    worker_index = Path(sh(wt, "git", "rev-parse", "--git-path", "index").strip())
    index = worker_index.read_bytes()
    source_index = (repo / ".git/index").read_bytes()
    registered = engine.load_session(sdir)["worktrees"][participant]
    for when in (None, "a-later-pass"):
        reused = engine.create_worktrees(sdir, [participant], when=when)["worktrees"][participant]
        assert reused == registered
        assert worker_index.read_bytes() == index
        assert (repo / ".git/index").read_bytes() == source_index
        assert sh(wt, "git", "rev-parse", "HEAD") == worker_head
        assert sh(wt, "git", "branch", "--show-current").strip() == registered["branch"]
        assert (wt / "sub/new.py").read_text() == "x = 3\n"
        assert (wt / "uncaptured").readlink() == Path("missing-target")
    cap = engine.capture_tree(sdir, 1, participant, None)
    assert cap["deleted"] == ["a.txt"]
    assert cap["changed"] == ["sub/new.py", "uncaptured"]
    done = engine.adopt_files(sdir, 1, [], [], whole=participant)
    assert done["copied"] == ["sub/new.py", "uncaptured"]
    assert not (repo / "a.txt").exists()
    assert (repo / "sub" / "new.py").read_text() == "x = 3\n"
    assert (repo / "uncaptured").readlink() == Path("missing-target")
    assert sh(wt, "git", "rev-parse", "HEAD") == worker_head
    assert sh(repo, "git", "rev-parse", "HEAD") == source_head
    assert engine.latest_session(str(repo), "execute")["applied"] is True
    engine.remove_worktrees(sdir, None)
    assert engine.restore_stash(sdir)["restored"] is True
    assert (repo / "B").read_text() == "working user edit\n"
    assert sh(repo, "git", "diff", "--cached", "--binary") == staged


def test_participant_paths_are_rejected_before_worktree_mutation(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sentinel = sdir.parent / "keep"
    sentinel.write_text("owned recovery marker\n")
    for name in ("..", "../..", "/absolute", "worker/child"):
        with pytest.raises(engine.EngineError, match="unsafe participant"):
            engine.create_worktrees(sdir, ["maintainer", name])
        with pytest.raises(engine.EngineError, match="unsafe participant"):
            engine.capture_tree(sdir, 1, name, None)
        with pytest.raises(engine.EngineError, match="unsafe participant"):
            engine.remove_worktrees(sdir, [name])
        assert not (sdir / "worktrees").exists()
        assert sentinel.read_text() == "owned recovery marker\n"


@pytest.mark.parametrize("state", ["missing", "replaced", "symlink", "unregistered"])
def test_repeated_create_refuses_changed_registration_without_removal(
    repo: Path, state: str
) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    entry = engine.create_worktrees(sdir, ["maintainer"])["worktrees"]["maintainer"]
    wt = Path(entry["path"])
    (wt / "a.txt").write_text("uncaptured\n")
    saved = wt if state == "unregistered" else wt.with_name("preserved-worker")
    if state == "unregistered":
        session = engine.load_session(sdir)
        session["worktrees"] = {}
        engine.save_session(sdir, session)
    else:
        wt.rename(saved)
        if state == "symlink":
            wt.symlink_to(saved, target_is_directory=True)
        elif state == "replaced":
            wt.mkdir()
            sh(wt, "git", "init", "-q", "-b", "unrelated")
            (wt / "keep").write_text("replacement data\n")
    session_bytes = (sdir / "session.json").read_bytes()
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    with pytest.raises(engine.EngineError, match="worktree"):
        engine.create_worktrees(sdir, ["builder", "maintainer"], when="repeat")
    assert not (sdir / "worktrees/builder").exists()
    assert (sdir / "session.json").read_bytes() == session_bytes
    assert (repo / ".git/index").read_bytes() == index
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert (saved / "a.txt").read_text() == "uncaptured\n"
    if state == "replaced":
        assert (wt / "keep").read_text() == "replacement data\n"
    if state == "symlink":
        assert wt.is_symlink()


def test_read_only_worktrees_start_from_the_snapshot(repo: Path) -> None:
    (repo / "a.txt").write_text(DIRTY_A)
    sdir = Path(init()["session_dir"])
    made = engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(made["worktrees"]["maintainer"]["path"])
    assert made["worktrees"]["maintainer"]["branch"] is None
    assert (wt / "a.txt").read_text() == DIRTY_A
    protocol = made["worktrees"]["maintainer"]["worker_instructions"]
    prefix = "cd -- " + shlex.quote(str(wt)) + " && "
    assert prefix in protocol
    assert "Every Read, Write, Edit, Glob, or Grep path must be absolute" in protocol
    for name in ("first", "second"):
        sh(repo, "sh", "-c", prefix + "touch " + name)
        assert (wt / name).exists()
        assert not (repo / name).exists()
    assert engine.create_worktrees(sdir, ["maintainer"])["worktrees"] == made["worktrees"]
    with pytest.raises(engine.EngineError, match="identity/base"):
        engine.create_worktrees(sdir, ["maintainer"], base="head")
    assert (wt / "first").exists()
    engine.remove_worktrees(sdir, None)
    assert not wt.exists()


def test_mutating_init_stashes_and_restore_pops_own_entry(repo: Path) -> None:
    (repo / "a.txt").write_text("user edit\n")
    (repo / "new.txt").write_text("untracked\n")
    doc = init(command="execute", backend="model-clis", mutating=True)
    sdir = Path(doc["session_dir"])
    assert doc["stash"]["state"] == "stashed"
    assert sh(repo, "git", "status", "--porcelain") == ""
    (repo / "other.txt").write_text("o")
    sh(repo, "git", "stash", "push", "-q", "--include-untracked", "-m", "unrelated")
    (repo / "synth.txt").write_text("synth\n")
    assert engine.restore_stash(sdir)["restored"] is True
    assert (repo / "synth.txt").read_text() == "synth\n"
    assert (repo / "a.txt").read_text() == "user edit\n"
    assert (repo / "new.txt").exists()


def test_reset_main_is_not_a_command_and_preserves_checkout(repo: Path) -> None:
    (repo / "a.txt").write_text("staged user edit\n")
    sh(repo, "git", "add", "a.txt")
    (repo / "a.txt").write_text("working user edit\n")
    (repo / "notes").symlink_to("missing-target")
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    branch = sh(repo, "git", "symbolic-ref", "HEAD")
    with pytest.raises(SystemExit) as exc:
        engine.main(["reset-main", "--session", str(repo / "absent-session")])
    assert exc.value.code == 2
    assert (repo / ".git/index").read_bytes() == index
    assert (repo / "a.txt").read_text() == "working user edit\n"
    assert (repo / "notes").is_symlink()
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert sh(repo, "git", "symbolic-ref", "HEAD") == branch


def test_clean_tree_mutating_init_needs_no_stash(repo: Path) -> None:
    doc = init(command="execute", backend="model-clis", mutating=True)
    assert doc["stash"] == {"state": "none-needed"}
    assert engine.restore_stash(Path(doc["session_dir"]))["restored"] is False


@pytest.mark.parametrize(
    ("backend", "participant"), [("subagents", "maintainer"), ("model-clis", "claude")]
)
@pytest.mark.parametrize("worker_exit", [0, 1])
def test_no_adoption_restores_partial_staging_and_attests_original(
    repo: Path, backend: str, participant: str, worker_exit: int
) -> None:
    (repo / "a.txt").write_text("staged\n")
    sh(repo, "git", "add", "a.txt")
    (repo / "a.txt").write_text("working\n")
    (repo / "notes").symlink_to("missing-target")
    before_index = sh(repo, "git", "ls-files", "--stage", "-v")
    original_head = sh(repo, "git", "rev-parse", "HEAD")
    sdir = Path(init(command="execute", backend=backend, mutating=True)["session_dir"])
    made = engine.create_worktrees(sdir, [participant])["worktrees"][participant]
    worktree = Path(made["path"])
    prefix = "cd -- " + shlex.quote(str(worktree)) + " && "
    assert prefix in made["worker_instructions"]
    dispatch_index = (repo / ".git/index").read_bytes()
    command = prefix + f"printf 'worker output\\n' > worker.txt; exit {worker_exit}"
    worker = subprocess.run(
        ["/bin/sh", "-c", command], cwd=repo, capture_output=True, text=True, check=False
    )
    assert worker.returncode == worker_exit
    assert not (repo / "worker.txt").exists()
    assert (worktree / "worker.txt").read_text() == "worker output\n"
    assert (repo / ".git/index").read_bytes() == dispatch_index
    assert sh(repo, "git", "rev-parse", "HEAD") == original_head
    captured = engine.capture_tree(sdir, 1, participant, None)
    assert captured["changed"] == ["worker.txt"]
    assert engine.guard_check(sdir)["violation"] is False
    engine.remove_worktrees(sdir, None)
    assert engine.restore_stash(sdir)["restored"] is True
    assert sh(repo, "git", "ls-files", "--stage", "-v") == before_index
    assert (repo / "a.txt").read_text() == "working\n"
    assert (repo / "notes").is_symlink()
    assert engine.guard_finish(sdir)["clean"] is True


@pytest.mark.parametrize("drift", ["working", "index", "branch"])
@pytest.mark.parametrize(
    ("backend", "participant"), [("subagents", "builder"), ("model-clis", "claude")]
)
def test_checkout_drift_halts_without_repair(
    repo: Path, drift: str, backend: str, participant: str
) -> None:
    sdir = Path(init(command="execute", backend=backend, mutating=True)["session_dir"])
    made = engine.create_worktrees(sdir, [participant])
    worktree = Path(made["worktrees"][participant]["path"])
    (worktree / "a.txt").write_text("approved worker result\n")
    engine.capture_tree(sdir, 1, participant, None)
    if drift == "working":
        (repo / "escaped").symlink_to("missing-target")
    elif drift == "index":
        (repo / "B").write_text("concurrent staged edit\n")
        sh(repo, "git", "add", "B")
        (repo / "B").write_text("b1\n")
    else:
        sh(repo, "git", "checkout", "-q", "-b", "concurrent-branch")
    before = sh(repo, "git", "status", "--porcelain")
    index = (repo / ".git/index").read_bytes()
    with pytest.raises(engine.EngineError, match="checkout changed"):
        engine.adopt_files(sdir, 1, [f"a.txt={participant}"], [])
    with pytest.raises(SystemExit) as exc:
        engine.main(["reset-main", "--session", str(sdir)])
    assert exc.value.code == 2
    done = engine.guard_finish(sdir)
    assert done["ok"] is False
    assert done["clean"] is False
    assert not done["refs_pruned"]
    assert done["index_changed"] is (drift == "index")
    assert done["head_changed"] is (drift == "branch")
    assert (repo / "a.txt").read_text() == "one\n"
    assert (repo / ".git/index").read_bytes() == index
    assert sh(repo, "git", "status", "--porcelain") == before
    assert worktree.is_dir()
    assert sh(repo, "git", "for-each-ref", "refs/weave-guard/")


# --- flags, prompts, labels, judges ---------------------------------------


def test_profiles_keep_the_timeout_menu_at_half_and_one_and_a_half() -> None:
    for command, prof in engine.PROFILES.items():
        menu = engine.parse_flags("x", command)["timeout_menu"]
        assert menu["default"] == prof.timeout
        assert menu["quick"] == prof.timeout // 2
        assert menu["long"] == prof.timeout + prof.timeout // 2


def test_cli_flags_and_labels(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO('--mode=deep --cascade why it\'s "odd" $HOME'))
    code = engine.main(["flags", "--command", "ask"])
    doc = json.loads(capsys.readouterr().out)
    assert code == 0
    assert doc["prompt"] == 'why it\'s "odd" $HOME'
    assert doc["flags"] == ["cascade"]
    assert doc["passes"] == 2
    assert doc["timeout"] == 675

    sdir = Path(init()["session_dir"])
    for name in ("maintainer", "skeptic", "builder"):
        (sdir / "pass-0001" / "outputs" / f"{name}.md").write_text(f"from {name}")
    engine.main(["labels", "--session", str(sdir), "--participants", "maintainer,skeptic,builder"])
    labels = json.loads(capsys.readouterr().out)["labels"]
    assert sorted(labels) == ["A", "B", "C"]
    blind = sdir / "pass-0001" / "blind"
    assert (blind / "response-A.md").read_text() == f"from {labels['A']}"
    assert json.loads((sdir / "pass-0001" / "label-map.json").read_text()) == labels


def test_labels_read_variant_outputs_from_the_session_root(repo: Path) -> None:
    sdir = Path(init(command="brainstorm", variants=2)["session_dir"])
    for name in ("maintainer-v1", "maintainer-v2"):
        (sdir / "outputs" / f"{name}.md").write_text(name)
    doc = engine.label_participants(
        sdir, 1, ["maintainer-v1", "maintainer-v2"], outputs=sdir / "outputs"
    )
    blind = sdir / "pass-0001" / "blind"
    assert {(blind / f"response-{k}.md").read_text() for k in doc["labels"]} == {
        "maintainer-v1",
        "maintainer-v2",
    }


def test_bad_flags_exit_nonzero(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("--passes=zero"))
    assert engine.main(["flags", "--command", "ask"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_context_sections_with_full_diff(repo: Path) -> None:
    (repo / "dirty.txt").write_text("x")
    assert "dirty.txt" in engine.context_sections(str(repo))
    sh(repo, "git", "checkout", "-q", "-b", "feature")
    (repo / "B").write_text("b2\n")
    sh(repo, "git", "commit", "-q", "-am", "feature")
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "main")
    text = engine.context_sections(str(repo), full_diff=True, diff_limit=3)
    assert "## Full diff" in text
    assert "truncated at 3" in text


def test_not_a_repo_reports_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    code = engine.main(["init", "--command", "execute", "--backend", "subagents", "--mutating"])
    assert code == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_cli_init_reads_prompt_and_prompt_composes_variants(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("what\n  does  $X do?"))
    args = ["init", "--command", "ask", "--backend", "subagents", "--prompt-stdin"]
    assert engine.main(args) == 0
    sdir = Path(json.loads(capsys.readouterr().out)["session_dir"])
    assert engine.load_session(sdir)["prompt_summary"] == "what does $X do?"
    body = sdir / "body.md"
    body.write_text("Q")
    out = sdir / "pass-0001" / "prompts" / "builder.md"
    assert engine.main(["prompt", "--lane", "builder", "--file", str(body), "--out", str(out)]) == 0
    text = out.read_text()
    assert text.startswith("You are the Builder.")
    assert "\n\nQ\n\n---\nCRITICAL" in text
    pre = sdir / "pre.md"
    pre.write_text("Be\n  bold.")
    out2 = sdir / "v.md"
    argv = ["prompt", "--lane", "gpt", "--file", str(body), "--out", str(out2), "--variant", "2"]
    assert engine.main([*argv, "--of", "3", "--preamble-file", str(pre)]) == 0
    assert out2.read_text().splitlines()[2] == "Variant 2 of 3: Be bold."


def test_judge_plan_modes(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", "exit 0")
    stub(bindir, "agent", "exit 0")
    sdir = Path(init(backend="model-clis")["session_dir"])
    rr = [engine.plan_judges(sdir, "round-robin", n)["judges"][0] for n in (1, 2, 3, 4)]
    assert [j["judge"] for j in rr] == ["claude", "agy", "gpt", "claude"]
    assert [j["how"] for j in rr] == ["host", "external", "external", "host"]
    panel = engine.plan_judges(sdir, "panel", 1)
    assert panel["feasibility"] == "full"
    native = Path(init()["session_dir"])
    assert engine.plan_judges(native, "round-robin", 2)["judges"][0]["how"] == "native"
    engine.update_session(
        sdir, status=None, completed_passes=None, event=None, event_json=None,
        drop=["agy"], sets=[], link_latest=False,
    )  # fmt: skip
    assert engine.plan_judges(sdir, "panel", 1)["feasibility"] == "degraded"
    engine.update_session(
        sdir, status=None, completed_passes=None, event=None, event_json=None,
        drop=["gpt"], sets=[], link_latest=False,
    )  # fmt: skip
    assert engine.plan_judges(sdir, "panel", 1)["mode"] == "host"
    assert engine.plan_judges(sdir, "round-robin", 2)["mode"] == "host"


def judge_text(winner: str, rows: dict[str, dict[str, int]]) -> str:
    cols = list(rows)
    dims = list(next(iter(rows.values())))
    lines = ["| Dimension | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    lines += [f"| {d} | " + " | ".join(str(rows[c][d]) for c in cols) + " |" for d in dims]
    totals = {c: sum(rows[c].values()) for c in cols}
    lines.append("| **Total** | " + " | ".join(str(totals[c]) for c in cols) + " |")
    return (
        "\n".join(lines) + f"\n\n## Winner\n\n**{winner}** with a score of {totals[winner]}/20.\n"
    )


def test_judge_parse_rejects_bad_totals_and_unknown_winner() -> None:
    good = judge_text("a", {"a": {"Q": 9, "C": 8}, "b": {"Q": 5, "C": 5}})
    assert engine.parse_judge(good)["winner_score"] == 17
    bad = good.replace("| 17 | 10 |", "| 18 | 10 |")
    slip = engine.parse_judge(bad)
    assert slip["ok"] is True
    assert slip["totals"]["a"] == 17
    assert slip["winner_score"] == 17
    assert "recomputed as 17" in slip["warnings"][0]
    assert not engine.parse_judge(good.replace("**a** with", "**z** with"))["ok"]
    assert not engine.parse_judge(good.replace("| 9 |", "| 11 |"))["ok"]


def test_judge_parse_flags_a_winner_that_did_not_improve(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    new, old = tmp_path / "new.md", tmp_path / "old.md"
    new.write_text(judge_text("a", {"a": {"Q": 7, "C": 7}, "b": {"Q": 1, "C": 1}}))
    old.write_text(judge_text("a", {"a": {"Q": 8, "C": 7}, "b": {"Q": 1, "C": 1}}))
    assert engine.main(["judge-parse", "--file", str(new), "--prior", str(old)]) == 0
    assert json.loads(capsys.readouterr().out)["not_improved"] is True


def test_panel_merge_is_peer_only(tmp_path: Path) -> None:
    files: dict[str, Path] = {}
    for judge, scores in {
        "claude": {"claude-v1": {"Q": 10, "C": 10}, "agy-v1": {"Q": 6, "C": 6}},
        "agy": {"claude-v1": {"Q": 6, "C": 6}, "agy-v1": {"Q": 10, "C": 10}},
    }.items():
        path = tmp_path / f"{judge}.md"
        path.write_text(judge_text("claude-v1", scores))
        files[judge] = path
    broken = tmp_path / "gpt.md"
    broken.write_text("garbage")
    files["gpt"] = broken
    doc = engine.merge_panel(files)
    assert doc["judges_succeeded"] == ["agy", "claude"]
    assert "gpt" in doc["judges_failed"]
    assert doc["peers"]["claude-v1"] == ["agy"]
    assert doc["totals"] == {"claude-v1": 12.0, "agy-v1": 12.0}
    assert doc["tied"] == ["agy-v1", "claude-v1"]
    assert doc["winner"] is None


def test_pass_dir_creates_mutating_subdirs(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    done = engine.make_pass(sdir, 2)
    assert (Path(done["pass_dir"]) / "diffs").is_dir()


def test_bare_session_has_no_workers_or_guard(repo: Path) -> None:
    doc = engine.init_session(
        command="fix-review", backend=None, repo=".", prompt_summary="", passes=1,
        timeout="default", mutating=False, bare=True,
    )  # fmt: skip
    session = engine.load_session(doc["session_dir"])
    assert session["worker_backend"] is None
    assert session["participants"] == []
    assert "guard" not in session
    with pytest.raises(engine.EngineError, match="no guard snapshot"):
        engine.guard_check(Path(doc["session_dir"]))
    with pytest.raises(engine.EngineError, match="needs --backend"):
        engine.init_session(
            command="ask", backend=None, repo=".", prompt_summary="", passes=1,
            timeout="default", mutating=False,
        )  # fmt: skip


def test_adopted_session_finish_skips_the_comparison_and_drops_refs(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sid = engine.load_session(sdir)["session_id"]
    made = engine.create_worktrees(sdir, ["builder"])
    (Path(made["worktrees"]["builder"]["path"]) / "adopted.txt").write_text("synthesis\n")
    engine.capture_tree(sdir, 1, "builder", None)
    engine.adopt_files(sdir, 1, [], [], whole="builder")
    done = engine.guard_finish(sdir)
    assert done["clean"] is None
    assert done["refs_pruned"] is True
    assert sh(repo, "git", "for-each-ref", f"refs/weave-guard/{sid}/") == ""


def test_context_reports_trunk_branch_and_commits(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sh(repo, "git", "update-ref", "refs/remotes/origin/main", "main")
    sh(repo, "git", "checkout", "-q", "-b", "feature")
    (repo / "B").write_text("b2\n")
    sh(repo, "git", "commit", "-q", "-am", "change b")
    assert engine.main(["context", "--full-diff"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (doc["trunk"], doc["branch"]) == ("main", "feature")
    assert doc["commits"][0].endswith("change b")
    assert "+b2" in doc["markdown"]


# --- safety: stash, unsafe toplevel, no-repo mode, recovery pins -------------


def test_failed_stash_pop_keeps_the_stash_and_never_advises_dropping_it(repo: Path) -> None:
    (repo / "a.txt").write_text("user edit\n")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    sha = engine.load_session(sdir)["stash"]["sha"]
    (repo / "a.txt").write_text("synthesis\n")
    doc = engine.restore_stash(sdir)
    assert doc["ok"] is False
    assert doc["stash_kept"] is True
    assert doc["stash_sha"] == sha
    assert engine.stash_entry(str(repo), sha) is not None
    assert "drop" not in json.dumps(doc)
    assert doc["overlap"] == ["a.txt"]
    for cmd in doc["recover"]:
        sh(repo, *cmd.split())
    assert (repo / "a.txt").read_text() == "user edit\n"
    assert "synthesis" in sh(repo, "git", "stash", "list")
    assert engine.stash_entry(str(repo), sha) is not None


def test_adopt_then_restore_leaves_synthesis_and_user_changes_before_any_panel(
    repo: Path,
) -> None:
    (repo / "b.txt").write_text("user edit\n")
    (repo / "u.txt").write_text("user untracked\n")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "sub" / "new.py").write_text("x = 1\n")
    engine.capture_tree(sdir, 1, "maintainer", None)
    engine.adopt_files(sdir, 1, [], [], whole="maintainer")
    engine.remove_worktrees(sdir, None)
    assert engine.restore_stash(sdir)["restored"] is True
    assert (repo / "sub" / "new.py").read_text() == "x = 1\n"
    assert (repo / "b.txt").read_text() == "user edit\n"
    assert (repo / "u.txt").exists()
    assert sh(repo, "git", "stash", "list") == ""


@pytest.mark.parametrize("skill", ["execute", "prompt", "architecture"])
def test_write_skills_restore_the_stash_before_presenting_results(skill: str) -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.index("stash-restore") < text.index("present-results.md")


def test_no_skill_or_reference_advises_stash_drop() -> None:
    root = Path(__file__).resolve().parents[1]
    hits = [
        str(p.relative_to(root))
        for folder in ("skills", "references")
        for p in (root / folder).rglob("*.md")
        if "stash drop" in p.read_text(encoding="utf-8")
    ]
    assert hits == []


def fake_home_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, nested: bool) -> Path:
    outer = tmp_path / "homes"
    home = outer / "me" if nested else outer
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    (outer / "f.txt").write_text("x\n")
    sh(outer, "git", "init", "-q", "-b", "main")
    sh(outer, "git", "config", "user.email", "t@example.com")
    sh(outer, "git", "config", "user.name", "t")
    sh(outer, "git", "add", "-A")
    sh(outer, "git", "commit", "-q", "-m", "init")
    return home if not nested else outer


@pytest.mark.parametrize(
    "nested", [False, True], ids=["home-is-toplevel", "toplevel-contains-home"]
)
def test_unsafe_toplevel_is_refused_for_mutating_and_unguarded_when_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, nested: bool
) -> None:
    top = fake_home_repo(tmp_path, monkeypatch, nested=nested)
    monkeypatch.chdir(top)
    (top / "dirty.txt").write_text("keep me\n")
    with pytest.raises(engine.EngineError, match="needs a git repository"):
        init(command="execute", mutating=True)
    assert not (tmp_path / "aip").exists()
    assert sh(top, "git", "stash", "list") == ""
    assert (top / "dirty.txt").read_text() == "keep me\n"
    doc = init(command="brainstorm")
    assert doc["unguarded"] is True
    assert "No repository" in doc["note"]
    assert sh(top, "git", "for-each-ref", "refs/weave-guard/") == ""
    for call in (engine.stash_user_changes, engine.take_guard_snapshot):
        with pytest.raises(engine.EngineError, match="refusing to snapshot"):
            call(str(top), "x")


def test_unsafe_toplevel_rule() -> None:
    assert engine.unsafe_toplevel("/") == "the filesystem root"
    assert engine.unsafe_toplevel("/a/b", {"HOME": "/a/b"}) == "your home directory"
    assert engine.unsafe_toplevel("/a/b/c", {"HOME": "/a/b"}) is None


def test_no_repo_mode_runs_read_only_commands_unguarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bindir: Path
) -> None:
    work = tmp_path / "plain"
    work.mkdir()
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.chdir(work)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    stub(bindir, "codex", "pwd > cwd.txt; ls -A | grep -v cwd.txt > ls.txt; echo ok")
    doc = init(command="refine", backend="model-clis")
    sdir = Path(doc["session_dir"])
    assert doc["repo"] is False
    assert doc["trunk"] is None
    assert engine.guard_check(sdir) == {"ok": True, "violation": False, "unguarded": True}
    assert engine.main(["guard", "check", "--session", str(sdir)]) == 0
    assert engine.guard_resolve(sdir, "revert")["violation"] is False
    assert engine.guard_finish(sdir)["unguarded"] is True
    other = init(command="refine")
    assert other["session_dir"].split("sessions")[0] == doc["session_dir"].split("sessions")[0]
    got = dispatch(sdir, "gpt")
    assert got["ok"] is True
    assert Path(sdir / "scratch").is_dir()
    ctx = engine.context_doc(".", full_diff=True, diff_limit=0)
    assert ctx["repo"] is False
    assert "No repository" in ctx["markdown"]
    made = engine.create_worktrees(sdir, ["maintainer"])["worktrees"]
    assert Path(made["maintainer"]["path"]).is_dir()
    assert not any(Path(made["maintainer"]["path"]).iterdir())
    marker = Path(made["maintainer"]["path"]) / "uncaptured"
    marker.write_text("worker\n")
    assert engine.create_worktrees(sdir, ["maintainer"])["worktrees"] == made
    assert marker.read_text() == "worker\n"
    engine.remove_worktrees(sdir, None)


def test_no_repo_mode_also_covers_a_repository_without_commits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "fresh"
    work.mkdir()
    sh(work, "git", "init", "-q", "-b", "main")
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.chdir(work)
    assert init(command="ask")["unguarded"] is True


@pytest.mark.parametrize("command", ["execute", "prompt", "architecture", "review"])
def test_commands_that_need_commits_refuse_without_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    work = tmp_path / "plain"
    work.mkdir()
    monkeypatch.setenv("AI_AIP_ROOT", str(tmp_path / "aip"))
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(work)
    with pytest.raises(engine.EngineError, match="needs a git repository with at least one"):
        init(command=command)
    with pytest.raises(engine.EngineError, match="needs a git repository"):
        engine.init_session(
            command="fix-review", backend=None, repo=".", prompt_summary="", passes=1,
            timeout="default", mutating=False, bare=True,
        )  # fmt: skip


def test_failed_init_leaves_no_session_directory_and_returns_the_stash(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "a.txt").write_text("user edit\n")

    def boom(*_a: object, **_k: object) -> engine.Json:
        msg = "snapshot failed"
        raise engine.EngineError(msg)

    monkeypatch.setattr(engine, "take_guard_snapshot", boom)
    with pytest.raises(engine.EngineError, match="snapshot failed"):
        init(command="execute", mutating=True)
    aip = Path(engine.aip_root())
    assert not list(aip.rglob("session.json"))
    assert not list(aip.rglob("repo.json"))
    assert not any(p.is_dir() for p in aip.rglob("sessions/*/*"))
    assert (repo / "a.txt").read_text() == "user edit\n"
    assert sh(repo, "git", "stash", "list") == ""


def test_guard_finish_keeps_existing_recovery_pins(repo: Path) -> None:
    (repo / "a.txt").write_text("user edit\n")
    sdir = Path(init(command="execute", backend="model-clis", mutating=True)["session_dir"])
    session = engine.load_session(sdir)
    sid = session["session_id"]
    initial = session["initial_guard"]
    engine.pin_tree(str(repo), sid, "pre-reset-existing", initial["tree"], initial["head"])
    engine.restore_stash(sdir)
    assert engine.guard_finish(sdir)["refs_pruned"] is True
    refs = sh(repo, "git", "for-each-ref", "--format=%(refname)", f"refs/weave-guard/{sid}/")
    pins = [r for r in refs.split() if "/pre-reset-" in r]
    assert len(pins) == 1
    assert len(refs.split()) == 1
    assert sh(repo, "git", "show", f"{pins[0]}:a.txt") == "user edit\n"


# --- judge parsing, flags, errors, context -----------------------------------


def test_judge_parse_accepts_decimals_and_a_missing_winner_section() -> None:
    text = (
        "| Dimension | claude | agy |\n|---|---|---|\n| Q | 8.5 | 7 |\n| C | 9 | 6.5 |\n"
        "| **Total** | 17.5 | 13.5 |\n"
    )
    doc = engine.parse_judge(text)
    assert doc["ok"], doc["errors"]
    assert doc["totals"] == {"claude": 17.5, "agy": 13.5}
    assert (doc["winner"], doc["winner_declared"], doc["winner_score"]) == ("claude", False, 17.5)
    assert engine.parse_judge(text.replace("17.5", "18.5"))["totals"]["claude"] == 17.5


def test_judge_columns_normalize_role_suffixes_and_blind_labels(tmp_path: Path) -> None:
    named = (
        "| Dimension | claude (Maintainer) | agy - Skeptic |\n|---|---|---|\n| Q | 9 | 5 |\n"
        "| **Total** | 9 | 5 |\n\n## Winner\n\n**claude (Maintainer)** with a score of 9.\n"
    )
    assert engine.parse_judge(named)["columns"] == ["claude", "agy"]
    assert engine.parse_judge(named)["winner"] == "claude"
    blind = (
        "| Dimension | Response A | Response B |\n|---|---|---|\n| Q | 4 | 9 |\n"
        "| **Total** | 4 | 9 |\n\n## Winner\n\nResponse B with a score of 9.\n"
    )
    doc = engine.parse_judge(blind, {"A": "claude-v1", "B": "agy-v1"})
    assert (doc["columns"], doc["winner"]) == (["claude-v1", "agy-v1"], "agy-v1")
    files: dict[str, Path] = {}
    for judge, rows in (("claude", "| Q | 10 | 3 |"), ("agy", "| Q | 2 | 8 |")):
        f = tmp_path / f"{judge}.md"
        cells = [c.strip() for c in rows.split("|")]
        head = f"| Dimension | Response A ({judge}) | Response B |\n|---|---|---|\n{rows}\n"
        f.write_text(head + f"| **Total** | {cells[2]} | {cells[3]} |\n")
        files[judge] = f
    doc2 = engine.merge_panel(files, {"A": "claude-v1", "B": "agy-v1"})
    assert doc2["peers"] == {"agy-v1": ["claude"], "claude-v1": ["agy"]}


def test_flags_are_consumed_only_from_the_leading_block() -> None:
    doc = engine.parse_flags("tool --mode=fast --timeout=30 x", "refine")
    assert doc["prompt"] == "tool --mode=fast --timeout=30 x"
    assert doc["mode"] is None
    assert doc["timeout"] is None
    doc = engine.parse_flags("--mode=fast refine tool --timeout=30", "refine")
    assert (doc["mode"], doc["timeout"], doc["prompt"]) == ("fast", 225, "refine tool --timeout=30")


def test_bad_inputs_report_json_not_tracebacks(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    cases = [
        ["prompt", "--lane", "gpt", "--file", "/nonexistent/x", "--out", str(sdir / "o.md")],
        ["update", "--session", str(sdir), "--set", "x=bad"],
        ["update", "--session", str(sdir), "--set", "novalue"],
        ["update", "--session", str(sdir), "--event", "e", "--event-json", "{"],
        ["capture", "--session", str(sdir), "--participant", "nobody"],
        ["judge-parse", "--file", "/nonexistent/j.md"],
        ["pass-dir", "--session", str(sdir / "missing"), "--pass", "2"],
    ]
    for argv in cases:
        assert engine.main(argv) == 1
        assert json.loads(capsys.readouterr().out)["ok"] is False
    body = sdir / "p.md"
    body.write_text("q")
    assert (
        engine.main(
            [
                "dispatch",
                "--session",
                str(sdir),
                "--lane",
                "gpt",
                "--prompt-file",
                str(body),
                "--mutating",
            ]
        )
        == 1
    )
    assert "no worktree registered" in json.loads(capsys.readouterr().out)["error"]


def test_context_falls_back_to_a_local_trunk_without_origin(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sh(repo, "git", "checkout", "-q", "-b", "feature")
    (repo / "B").write_text("b2\n")
    sh(repo, "git", "commit", "-q", "-am", "change b")
    assert engine.main(["context"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["base"] == "main"
    assert doc["commits"][0].endswith("change b")
    assert " B " in doc["markdown"] or "B |" in doc["markdown"]


def test_classification_ignores_task_text_echoed_on_stderr(repo: Path, bindir: Path) -> None:
    stub(bindir, "codex", 'for a in "$@"; do echo "$a" >&2; done; echo boom >&2; exit 2')
    sdir, _ = read_only_session()
    sdir_prompt = sdir / "prompt.md"
    sdir_prompt.write_text("Fix the billing rate limit 429 quota exceeded bug")
    got = engine.dispatch_lane(
        sdir, "gpt", n=1, prompt_file=sdir_prompt, timeout=5, mutating=False, rate_wait=0
    )
    assert got["failure_class"] == "crash"
    assert len(got["attempts"]) == 1


def test_plan_judges_with_every_participant_dropped(repo: Path) -> None:
    sdir = Path(init()["session_dir"])
    engine.update_session(
        sdir, status=None, completed_passes=None, event=None, event_json=None,
        drop=["maintainer", "skeptic", "builder"], sets=[], link_latest=False,
    )  # fmt: skip
    for mode in ("round-robin", "panel"):
        assert engine.plan_judges(sdir, mode, 1)["mode"] == "host"


def test_latest_session_reports_snapshots_and_paths_dirtied_since(repo: Path) -> None:
    with pytest.raises(engine.EngineError, match="no execute session"):
        engine.latest_session(".", "execute")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "sub" / "new.py").write_text("x = 1\n")
    (wt / "a.txt").unlink()
    engine.capture_tree(sdir, 1, "maintainer", None)
    engine.remove_worktrees(sdir, None)
    engine.restore_stash(sdir)
    (repo / "sub").mkdir(exist_ok=True)
    (repo / "sub" / "new.py").write_text("user\n")
    found = engine.latest_session(".", "execute")
    assert found["session_dir"] == str(sdir)
    assert found["pass"] == 1
    assert found["captured"]["maintainer"] == {"changed": ["sub/new.py"], "deleted": ["a.txt"]}
    assert found["dirty"] == ["sub/new.py"]
    assert found["applied"] is False


@pytest.fixture
def recorded_session(repo: Path) -> Path:
    (repo / "B").write_text("staged user edit\n")
    sh(repo, "git", "add", "B")
    (repo / "B").write_text("working user edit\n")
    sdir = Path(init(command="execute", backend="model-clis", mutating=True)["session_dir"])
    entry = engine.create_worktrees(sdir, ["claude"])["worktrees"]["claude"]
    wt = Path(entry["path"])
    (wt / "a.txt").write_text("approved worker result\n")
    (wt / "[literal]").write_text("new worker file\n")
    (wt / "C").unlink()
    engine.capture_tree(sdir, 1, "claude", None)
    engine.remove_worktrees(sdir, None)
    assert engine.restore_stash(sdir)["restored"] is True
    assert engine.guard_finish(sdir)["clean"] is True
    engine.update_session(
        sdir, status="completed", completed_passes=1, event="session_complete",
        event_json="{}", drop=[], sets=[], link_latest=True,
    )  # fmt: skip
    return sdir


@pytest.mark.parametrize(
    "change", ["edit", "edit-branch", "mode", "removed", "delete", "add-literal"]
)
def test_recorded_adoption_refuses_committed_target_drift(
    repo: Path, recorded_session: Path, change: str
) -> None:
    sdir = recorded_session
    if "branch" in change:
        sh(repo, "git", "checkout", "-q", "-b", "user-branch")
    target = "a.txt"
    if change in {"edit", "edit-branch"}:
        (repo / target).write_text("newer committed user implementation\n")
    elif change == "mode":
        (repo / target).chmod(0o755)
    elif change == "removed":
        (repo / target).unlink()
    elif change == "delete":
        target = "C"
        (repo / target).write_text("newer committed deletion target\n")
    else:
        target = "[literal]"
        (repo / target).write_text("committed user file\n")
    sh(repo, "git", "--literal-pathspecs", "add", "--", target)
    sh(
        repo,
        "git",
        "--literal-pathspecs",
        "commit",
        "-q",
        "-m",
        "user work",
        "--only",
        "--",
        target,
    )
    before = user_state(repo)
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    branch = sh(repo, "git", "symbolic-ref", "HEAD")
    mode = (repo / "a.txt").stat().st_mode if change != "removed" else None
    found = engine.latest_session(str(repo), "execute")
    assert found["dirty"] == [target]
    assert "session base" in found["conflicts"][target]
    selections: list[tuple[list[str], list[str], str | None]] = [
        ([], [], "claude"),
        (["a.txt=claude", "[literal]=claude"], ["C"], None),
    ]
    for picks, deletes, whole in selections:
        with pytest.raises(engine.EngineError, match="session base"):
            engine.adopt_files(sdir, 1, picks, deletes, whole=whole)
        assert user_state(repo) == before
        if mode is not None:
            assert (repo / "a.txt").stat().st_mode == mode
    assert engine.load_session(sdir).get("applied") is not True
    clean_path = "a.txt" if target == "[literal]" else "[literal]"
    engine.adopt_files(sdir, 1, [f"{clean_path}=claude"], [])
    before[clean_path] = (
        "approved worker result\n" if clean_path == "a.txt" else "new worker file\n"
    )
    assert user_state(repo) == before
    assert (repo / ".git/index").read_bytes() == index
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert sh(repo, "git", "symbolic-ref", "HEAD") == branch


@pytest.mark.parametrize("switch_branch", [False, True])
def test_recorded_adoption_allows_unrelated_commits_and_preserves_staging(
    repo: Path, recorded_session: Path, switch_branch: bool
) -> None:
    sdir = recorded_session
    if switch_branch:
        sh(repo, "git", "checkout", "-q", "-b", "user-branch")
    (repo / "l").write_text("unrelated user file\n")
    sh(repo, "git", "add", "l")
    sh(repo, "git", "commit", "-q", "-m", "unrelated user work", "--only", "--", "l")
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    branch = sh(repo, "git", "symbolic-ref", "HEAD")
    assert engine.latest_session(str(repo), "execute")["dirty"] == []
    engine.adopt_files(sdir, 1, ["a.txt=claude", "[literal]=claude"], ["C"])
    assert (repo / "a.txt").read_text() == "approved worker result\n"
    assert (repo / "[literal]").read_text() == "new worker file\n"
    assert not (repo / "C").exists()
    assert (repo / "B").read_text() == "working user edit\n"
    assert (repo / "l").read_text() == "unrelated user file\n"
    (repo / "a.txt").write_text("user edit after adoption\n")
    with pytest.raises(engine.EngineError, match="already applied"):
        engine.adopt_files(sdir, 1, [], [], whole="claude")
    assert (repo / "a.txt").read_text() == "user edit after adoption\n"
    assert (repo / ".git/index").read_bytes() == index
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert sh(repo, "git", "symbolic-ref", "HEAD") == branch


@pytest.mark.parametrize("hidden", ["mode", "stat-cache", "unreadable"])
def test_recorded_adoption_rehashes_selected_paths(
    repo: Path, recorded_session: Path, hidden: str, capsys: pytest.CaptureFixture[str]
) -> None:
    target = repo / "a.txt"
    if hidden == "mode":
        sh(repo, "git", "config", "core.filemode", "false")
        target.chmod(0o755)
    elif hidden == "stat-cache":
        sh(repo, "git", "config", "core.trustctime", "false")
        os.utime(target, (1, 1))
        sh(repo, "git", "status", "--porcelain")
        target.write_text("two\n")
        os.utime(target, (1, 1))
    else:
        target.chmod(0)
    mode = target.stat().st_mode
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    try:
        code = engine.main(["latest", "--repo", str(repo), "--command", "execute"])
        found = json.loads(capsys.readouterr().out)
        if code == 1:
            assert hidden == "unreadable"
            assert "Permission denied" in found["error"]
        else:
            assert code == 0
            assert found["dirty"] == ["a.txt"]
        with pytest.raises(engine.EngineError):
            engine.adopt_files(recorded_session, 1, [], [], whole="claude")
        assert target.stat().st_mode == mode
        assert (repo / ".git/index").read_bytes() == index
        assert sh(repo, "git", "rev-parse", "HEAD") == head
        assert not (repo / "[literal]").exists()
        assert (repo / "C").read_text() == "c1\n"
    finally:
        target.chmod(0o644)
    assert target.read_text() == ("two\n" if hidden == "stat-cache" else "one\n")


def test_capture_and_adopt_keep_symlinks_as_links(repo: Path) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "target.txt").write_text("real\n")
    (wt / "live").symlink_to("target.txt")
    (wt / "dangling").symlink_to("missing/nowhere")
    cap = engine.capture_tree(sdir, 1, "maintainer", None)
    assert sorted(cap["changed"]) == ["dangling", "live", "target.txt"]
    assert cap["links"] == {"dangling": "missing/nowhere", "live": "target.txt"}
    engine.adopt_files(sdir, 1, [], [], whole="maintainer")
    assert (repo / "live").is_symlink()
    assert (repo / "live").readlink() == Path("target.txt")
    assert (repo / "dangling").is_symlink()
    assert (repo / "dangling").readlink() == Path("missing/nowhere")
    assert (repo / "target.txt").read_text() == "real\n"


def test_adopt_replaces_a_symlink_without_writing_through_it(repo: Path) -> None:
    outside = repo.parent / "outside.txt"
    outside.write_text("keep\n")
    (repo / "n.txt").symlink_to(outside)
    sh(repo, "git", "add", "n.txt")
    sh(repo, "git", "commit", "-q", "-m", "track link")
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "n.txt").unlink()
    (wt / "n.txt").write_text("from worker\n")
    engine.capture_tree(sdir, 1, "maintainer", None)
    outside.chmod(0)
    try:
        engine.adopt_files(sdir, 1, ["n.txt=maintainer"], [])
    finally:
        outside.chmod(0o644)
    assert not (repo / "n.txt").is_symlink()
    assert (repo / "n.txt").read_text() == "from worker\n"
    assert outside.read_text() == "keep\n"


@pytest.mark.parametrize(
    "state",
    [
        "staged",
        "unstaged",
        "untracked",
        "ignored",
        "symlink-parent",
        "assume-unchanged",
        "skip-worktree",
    ],
)
def test_adopt_refuses_dirty_targets_before_any_write(
    repo: Path, state: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "a.txt").write_text("worker\n")
    (wt / "B").unlink()
    target = "sub/new.txt" if state in {"untracked", "ignored", "symlink-parent"} else "B"
    if state == "symlink-parent":
        outside = repo.parent / "outside"
        outside.mkdir()
        (repo / "sub" / "S").unlink()
        (repo / "sub").rmdir()
        (repo / "sub").symlink_to(outside, target_is_directory=True)
    (wt / "sub" / "new.txt").write_text("worker\n")
    engine.capture_tree(sdir, 1, "maintainer", None)
    session = engine.load_session(sdir)
    session["status"] = "completed"
    engine.save_session(sdir, session)
    (repo / target).write_text("user\n")
    if state == "staged":
        sh(repo, "git", "add", target)
    if state == "ignored":
        (repo / ".gitignore").write_text("sub/new.txt\n")
    if state in {"assume-unchanged", "skip-worktree"}:
        sh(repo, "git", "update-index", f"--{state}", target)
    before = sh(repo, "git", "status", "--porcelain", "--ignored")
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    root = repo if state == "symlink-parent" else repo / "sub"
    assert engine.main(["check-paths", "--repo", str(root), "--", target]) == 1
    assert json.loads(capsys.readouterr().out)["clean"] is False
    with pytest.raises(engine.EngineError, match="refusing"):
        engine.adopt_files(sdir, 1, [], [], whole="maintainer")
    assert (repo / "a.txt").read_text() == "one\n"
    assert (repo / target).read_text() == "user\n"
    assert (repo / ".git/index").read_bytes() == index
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert sh(repo, "git", "status", "--porcelain", "--ignored") == before


def test_edit_preflight_distinguishes_new_files_links_and_literal_names(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "link").symlink_to("a.txt")
    (repo / "[literal]").write_text("one\n")
    sh(repo, "git", "add", "link", "[literal]")
    sh(repo, "git", "commit", "-q", "-m", "tracked paths")
    (repo / "B").write_text("unrelated user edit\n")
    index = (repo / ".git/index").read_bytes()
    assert engine.main(["check-paths", "--", "a.txt", "new-test", "[literal]"]) == 0
    assert json.loads(capsys.readouterr().out)["clean"] is True
    assert engine.main(["check-paths", "--", "link", ".git/config", ".", "B/new"]) == 1
    assert set(json.loads(capsys.readouterr().out)["conflicts"]) == {
        "link",
        ".git/config",
        ".",
        "B/new",
    }
    assert (repo / ".git/index").read_bytes() == index


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_recorded_adoption_refuses_hidden_edits_for_explicit_picks(
    repo: Path, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "a.txt").write_text("worker\n")
    engine.capture_tree(sdir, 1, "maintainer", None)
    session = engine.load_session(sdir)
    session["status"] = "completed"
    engine.save_session(sdir, session)
    sh(repo, "git", "update-index", flag, "a.txt")
    (repo / "a.txt").write_text("hidden user bytes\n")
    index = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    assert engine.latest_session(".", "execute")["dirty"] == ["a.txt"]
    for spelling in ("a.txt", "./a.txt", "a.txt/"):
        assert engine.main(["check-paths", "--", spelling]) == 1
        assert json.loads(capsys.readouterr().out)["clean"] is False
        with pytest.raises(engine.EngineError, match="index flag"):
            engine.adopt_files(sdir, 1, [f"{spelling}=maintainer"], [])
    assert (repo / "a.txt").read_text() == "hidden user bytes\n"
    assert (repo / ".git/index").read_bytes() == index
    assert sh(repo, "git", "rev-parse", "HEAD") == head


@pytest.mark.parametrize("split", [False, True])
def test_commit_takes_only_named_paths_and_keeps_other_staged_files(
    repo: Path, tmp_path: Path, split: bool
) -> None:
    if split:
        sh(repo, "git", "config", "core.splitIndex", "true")
        sh(repo, "git", "update-index", "--split-index")
    (repo / "unrelated.txt").write_text("user work\n")
    sh(repo, "git", "add", "unrelated.txt")
    (repo / "unrelated.txt").write_text("user work plus unstaged addition\n")
    (repo / "B").write_text("another unstaged edit\n")
    staged = sh(repo, "git", "diff", "--cached", "--binary")
    (repo / "a.txt").write_text("fixed\n")
    (repo / "new.py").write_text("x = 1\n")
    msg = tmp_path / "msg.txt"
    msg.write_text("fix(a) Reset\n\nCOMMIT_MSG_END\ntouch injected\n$(touch injected)\n")
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\ngit add B\n")
    hook.chmod(0o700)
    done = engine.commit_paths(".", str(msg), ["a.txt", "new.py"])
    assert sorted(done["committed"]) == ["a.txt", "new.py"]
    assert done["still_staged"] == ["unrelated.txt"]
    assert sh(repo, "git", "diff", "--cached", "--name-only").split() == ["unrelated.txt"]
    assert sh(repo, "git", "diff", "--cached", "--binary") == staged
    assert (repo / "unrelated.txt").read_text() == "user work plus unstaged addition\n"
    assert (repo / "B").read_text() == "another unstaged edit\n"
    assert not (repo / "injected").exists()
    assert sh(repo, "git", "show", "--name-only", "--format=", "HEAD").split() == [
        "a.txt",
        "new.py",
    ]


@pytest.mark.parametrize("trailer", ["Co-Authored-By: Bot <b@x.io>", "Generated with a tool"])
def test_commit_refuses_tool_trailers(repo: Path, tmp_path: Path, trailer: str) -> None:
    (repo / "a.txt").write_text("fixed\n")
    msg = tmp_path / "msg.txt"
    msg.write_text(f"fix(a) Reset\n\n{trailer}\n")
    head = sh(repo, "git", "rev-parse", "HEAD")
    with pytest.raises(engine.EngineError, match="trailer"):
        engine.commit_paths(".", str(msg), ["a.txt"])
    assert sh(repo, "git", "rev-parse", "HEAD") == head


def test_commit_literal_paths_and_failed_hook_preserve_the_index(
    repo: Path, tmp_path: Path
) -> None:
    (repo / "[ab].txt").write_text("fix\n")
    (repo / "a.txt").write_text("user staged\n")
    sh(repo, "git", "add", "a.txt")
    (repo / "a.txt").write_text("user unstaged\n")
    msg = tmp_path / "msg.txt"
    msg.write_text("fix(a) Reset the counter\n")
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    before = sh(repo, "git", "diff", "--cached", "--binary")
    with pytest.raises(engine.EngineError):
        engine.commit_paths(".", str(msg), ["[ab].txt"])
    assert sh(repo, "git", "diff", "--cached", "--binary") == before
    assert (repo / "a.txt").read_text() == "user unstaged\n"
    assert (repo / "[ab].txt").read_text() == "fix\n"
    hook.unlink()
    done = engine.commit_paths(".", str(msg), ["[ab].txt"])
    assert done["committed"] == ["[ab].txt"]
    assert sh(repo, "git", "diff", "--cached", "--binary") == before


@pytest.mark.parametrize("change", ["staged", "unstaged", "trailer", "parent"])
def test_commit_refuses_hook_changes_and_retains_approved_bytes(
    repo: Path, tmp_path: Path, change: str
) -> None:
    (repo / "a.txt").write_text("approved\n")
    message = tmp_path / "message"
    message.write_text("fix(a) Approved\n")
    head = sh(repo, "git", "rev-parse", "HEAD")
    before = (repo / ".git/index").read_bytes()
    hook_name = "pre-commit"
    bodies = {
        "staged": "echo hook >a.txt; git add a.txt",
        "unstaged": "echo hook >a.txt",
        "trailer": 'printf "\\nCo-Authored-By: Bot <b@example.test>\\n" >>"$1"',
        "parent": 'git -c core.hooksPath=/dev/null commit --allow-empty -qm "extra commit"',
    }
    if change == "trailer":
        hook_name = "commit-msg"
    hook = repo / ".git/hooks" / hook_name
    hook.write_text("#!/bin/sh\n" + bodies[change] + "\n")
    hook.chmod(0o700)
    with pytest.raises(engine.EngineError, match="recovery retained"):
        engine.commit_paths(".", str(message), ["a.txt"])
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert (repo / ".git/index").read_bytes() == before
    assert (repo / "a.txt").read_text() == "approved\n"
    saved = next((tmp_path / "aip/commit-recovery").glob("*/recovery.json"))
    metadata = json.loads(saved.read_text())
    assert sh(repo, "git", "show", metadata["recovery_ref"] + ":a.txt") == "approved\n"
    assert (saved.parent / "worktree").is_dir()
    assert not metadata["published"]


@pytest.mark.parametrize("change", ["index", "branch", "working"])
def test_commit_preserves_concurrent_source_changes(
    repo: Path, tmp_path: Path, change: str
) -> None:
    (repo / "a.txt").write_text("approved\n")
    (repo / "B").write_text("user staged later\n")
    message = tmp_path / "message"
    message.write_text("fix(a) Approved\n")
    head = sh(repo, "git", "rev-parse", "HEAD").strip()
    source = shlex.quote(str(repo))
    bodies = {
        "index": f"git -C {source} add B",
        "branch": "; ".join(
            (
                f"git -C {source} update-ref refs/heads/moved {head}",
                f"git -C {source} symbolic-ref HEAD refs/heads/moved",
            )
        ),
        "working": f"printf 'new user edit\\n' >{source}/a.txt",
    }
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text(
        "#!/bin/sh\nunset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR\n"
        + bodies[change]
        + "\n"
    )
    hook.chmod(0o700)
    if change == "working":
        engine.commit_paths(".", str(message), ["a.txt"])
        assert sh(repo, "git", "show", "HEAD:a.txt") == "approved\n"
        assert (repo / "a.txt").read_text() == "new user edit\n"
        assert " M a.txt" in sh(repo, "git", "status", "--porcelain")
    else:
        with pytest.raises(engine.EngineError, match=r"source .* changed"):
            engine.commit_paths(".", str(message), ["a.txt"])
        assert sh(repo, "git", "rev-parse", "HEAD").strip() == head
        if change == "index":
            assert sh(repo, "git", "show", ":B") == "user staged later\n"
        else:
            assert sh(repo, "git", "symbolic-ref", "HEAD").strip() == "refs/heads/moved"


def test_commit_preserves_new_deleted_executable_symlink_bytes(repo: Path, tmp_path: Path) -> None:
    (repo / "B").unlink()
    (repo / "binary").write_bytes(b"binary\x00data")
    (repo / "binary").chmod(0o755)
    (repo / "link").symlink_to("missing-target")
    message = tmp_path / "message"
    message.write_text("fix(files) Approved\n")
    done = engine.commit_paths(".", str(message), ["B", "binary", "link"])
    assert done["committed"] == ["B", "binary", "link"]
    assert engine.git_bytes(repo, "show", "HEAD:binary") == b"binary\x00data"
    assert sh(repo, "git", "show", "HEAD:link") == "missing-target"
    assert sh(repo, "git", "ls-tree", "HEAD", "binary").startswith("100755")
    assert (repo / "link").is_symlink()


def test_commit_retains_index_recovery_after_publication_failure(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repo / "a.txt").write_text("approved\n")
    message = tmp_path / "message"
    message.write_text("fix(a) Approved\n")
    before = (repo / ".git/index").read_bytes()
    replace = Path.replace

    def failed_replace(source: Path, destination: Path) -> Path:
        if destination == repo / ".git/index":
            msg = "simulated index publication failure"
            raise OSError(msg)
        return replace(source, destination)

    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(
        engine.EngineError, match="commit published; source index may need recovery"
    ):
        engine.commit_paths(".", str(message), ["a.txt"])
    assert sh(repo, "git", "show", "HEAD:a.txt") == "approved\n"
    assert (repo / ".git/index").read_bytes() == before
    saved = next((tmp_path / "aip/commit-recovery").glob("*/recovery.json"))
    assert json.loads(saved.read_text())["published"]
    assert (saved.parent / "index-after").is_file()
    assert not (repo / ".git/index.lock").exists()


@pytest.mark.parametrize("lock_name", ["index.lock", "HEAD.lock"])
def test_commit_never_removes_a_foreign_lock(repo: Path, tmp_path: Path, lock_name: str) -> None:
    (repo / "a.txt").write_text("approved\n")
    message = tmp_path / "message"
    message.write_text("fix(a) Approved\n")
    lock = repo / ".git" / lock_name
    lock.write_text("another Git operation\n")
    before = (repo / ".git/index").read_bytes()
    head = sh(repo, "git", "rev-parse", "HEAD")
    with pytest.raises(engine.EngineError, match="not published"):
        engine.commit_paths(".", str(message), ["a.txt"])
    assert lock.read_text() == "another Git operation\n"
    assert sh(repo, "git", "rev-parse", "HEAD") == head
    assert (repo / ".git/index").read_bytes() == before


def test_commit_locks_source_head_during_publication(repo: Path, tmp_path: Path) -> None:
    (repo / "a.txt").write_text("approved\n")
    message = tmp_path / "message"
    message.write_text("fix(a) Approved\n")
    attempt = tmp_path / "attempt"
    hook = repo / ".git/hooks/reference-transaction"
    source = shlex.quote(str(repo))
    hook.write_text(
        "\n".join(
            (
                "#!/bin/sh",
                "read old new ref",
                'if [ "$1" = prepared ] && [ "$ref" = refs/heads/main ]; then',
                "unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR",
                f"git -C {source} symbolic-ref HEAD refs/heads/moved >/dev/null 2>&1",
                f'printf "%s\\n" "$?" >{shlex.quote(str(attempt))}',
                "fi",
                "exit 0",
                "",
            )
        )
    )
    hook.chmod(0o700)
    engine.commit_paths(".", str(message), ["a.txt"])
    assert int(attempt.read_text()) != 0
    assert sh(repo, "git", "symbolic-ref", "HEAD").strip() == "refs/heads/main"
    assert not (repo / ".git/HEAD.lock").exists()


# --- alias safety: engine-owned writes never reach another file -------------


def link_alias(kind: str, link: Path, live: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    link.unlink(missing_ok=True)
    if kind == "symlink":
        link.symlink_to(live)
    else:
        os.link(live, link)


def staged_plus_working(repo: Path) -> Path:
    live = repo / "a.txt"
    live.write_text("staged\n")
    sh(repo, "git", "add", "a.txt")
    live.write_text("staged plus working\n")
    return live


def checkout_state(repo: Path) -> tuple[bytes, str, str]:
    return (
        (repo / ".git/index").read_bytes(),
        sh(repo, "git", "rev-parse", "HEAD"),
        (repo / "a.txt").read_text(),
    )


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
@pytest.mark.parametrize("site", ["blind", "label-map", "prompt", "session", "events"])
def test_session_writes_replace_aliases_instead_of_writing_through(
    repo: Path, kind: str, site: str
) -> None:
    live = staged_plus_working(repo)
    sdir = Path(init(backend="model-clis")["session_dir"])
    base = sdir / "pass-0001"
    (base / "outputs").mkdir(parents=True, exist_ok=True)
    (base / "outputs" / "x.md").write_text("answer\n")
    before = checkout_state(repo)
    target = {
        "blind": base / "blind" / "response-A.md",
        "label-map": base / "label-map.json",
        "prompt": base / "prompts" / "gpt.md",
        "session": sdir / "session.json",
        "events": sdir / "events.jsonl",
    }[site]
    link_alias(kind, target, live)
    if site in {"blind", "label-map"}:
        engine.label_participants(sdir, 1, ["x"])
    elif site == "prompt":
        body = prompt_file({"session_dir": str(sdir)})
        assert (
            engine.main(["prompt", "--lane", "gpt", "--file", str(body), "--out", str(target)]) == 0
        )
    elif site == "session":
        engine.save_session(sdir, {"x": 1})
    else:
        engine.append_jsonl(target, {"event": "x"})
    assert checkout_state(repo) == before
    assert not target.is_symlink()
    assert target.stat().st_nlink == 1
    assert live.stat().st_nlink == 1


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_dispatch_outputs_replace_aliases_instead_of_writing_through(
    repo: Path, bindir: Path, kind: str
) -> None:
    stub(bindir, "codex", "printf answer; echo warn >&2")
    live = staged_plus_working(repo)
    sdir, _ = read_only_session()
    before = checkout_state(repo)
    base = sdir / "pass-0001"
    for name in ("outputs/gpt.md", "stderr/gpt.txt", "prompts/gpt.md"):
        link_alias(kind, base / name, live)
    doc = dispatch(sdir, "gpt")
    assert doc["ok"], doc
    assert Path(doc["output"]).read_text() == "answer"
    assert checkout_state(repo) == before


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_capture_copies_replace_aliases(repo: Path, kind: str) -> None:
    live = staged_plus_working(repo)
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "made.txt").write_text("worker\n")
    base = sdir / "pass-0001"
    before = checkout_state(repo)
    for name in ("files/maintainer/made.txt", "diffs/maintainer.patch", "diffs/maintainer.json"):
        link_alias(kind, base / name, live)
    engine.capture_tree(sdir, 1, "maintainer", None)
    assert checkout_state(repo) == before
    assert (base / "files" / "maintainer" / "made.txt").read_text() == "worker\n"


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_guard_records_replace_aliases(repo: Path, kind: str) -> None:
    sdir = Path(init(backend="model-clis")["session_dir"])
    other = repo.parent / "outside.txt"
    other.write_text("keep\n")
    (repo / "B").write_text("changed\n")
    index = (repo / ".git/index").read_bytes()
    link_alias(kind, sdir / "guard-events.jsonl", other)
    found = engine.guard_check(sdir, "probe")
    assert found["violation"] is True
    assert (Path(found["dir"]) / "post-copy" / "B").read_text() == "changed\n"
    assert other.read_text() == "keep\n"
    assert (repo / ".git/index").read_bytes() == index


@pytest.mark.parametrize("name", ["blind", "files", "diffs", "prompts"])
def test_symlinked_session_subdirectory_is_refused(repo: Path, name: str) -> None:
    staged_plus_working(repo)
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "made.txt").write_text("worker\n")
    base = sdir / "pass-0001"
    (base / "outputs").mkdir(parents=True, exist_ok=True)
    (base / "outputs" / "x.md").write_text("answer\n")
    before = checkout_state(repo)
    inside = repo / "sub"
    link = base / name
    if link.exists():
        shutil.rmtree(link)
    link.symlink_to(inside, target_is_directory=True)
    listing = sorted(p.name for p in inside.iterdir())
    if name == "prompts":
        body = prompt_file({"session_dir": str(sdir)})
        out = str(link / "gpt.md")
        assert engine.main(["prompt", "--lane", "gpt", "--file", str(body), "--out", out]) == 1
    else:
        call = (
            (lambda: engine.label_participants(sdir, 1, ["x"]))
            if name == "blind"
            else (lambda: engine.capture_tree(sdir, 1, "maintainer", None))
        )
        with pytest.raises(engine.EngineError, match="symlink"):
            call()
    assert sorted(p.name for p in inside.iterdir()) == listing
    assert checkout_state(repo) == before


def test_edit_preflight_refuses_hard_linked_files(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = repo.parent / "alias.txt"
    os.link(repo / "B", outside)
    assert engine.main(["check-paths", "--", "B", "C"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert set(doc["conflicts"]) == {"B"}
    assert outside.read_text() == "b1\n"


def test_adopt_breaks_a_hard_link_without_changing_the_other_name(repo: Path) -> None:
    outside = repo.parent / "alias.txt"
    os.link(repo / "B", outside)
    sdir = Path(init(command="execute", mutating=True)["session_dir"])
    engine.create_worktrees(sdir, ["maintainer"])
    wt = Path(engine.load_session(sdir)["worktrees"]["maintainer"]["path"])
    (wt / "B").write_text("worker\n")
    engine.capture_tree(sdir, 1, "maintainer", None)
    engine.adopt_files(sdir, 1, [], [], whole="maintainer")
    assert (repo / "B").read_text() == "worker\n"
    assert outside.read_text() == "b1\n"


@pytest.mark.parametrize("swap", ["file", "directory"])
def test_guard_revert_replaces_symlink_swaps_without_writing_through(repo: Path, swap: str) -> None:
    sdir = Path(init(backend="model-clis")["session_dir"])
    outside = repo.parent / "outside"
    outside.mkdir()
    (outside / "S").write_text("keep\n")
    (outside / "B").write_text("keep\n")
    if swap == "file":
        (repo / "B").unlink()
        (repo / "B").symlink_to(outside / "B")
    else:
        shutil.rmtree(repo / "sub")
        (repo / "sub").symlink_to(outside, target_is_directory=True)
    engine.guard_resolve(sdir, "revert")
    assert not (repo / "B").is_symlink()
    assert not (repo / "sub").is_symlink()
    assert (repo / "B").read_text() == "b1\n"
    assert (repo / "sub" / "S").read_text() == "s1\n"
    assert (outside / "S").read_text() == "keep\n"
    assert (outside / "B").read_text() == "keep\n"
