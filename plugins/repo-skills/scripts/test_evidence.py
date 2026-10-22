"""Tests for evidence.py: history parsing, transcript filtering, and linking."""

# ruff: noqa: S101, S603, S607, INP001, PLR2004
# pyright: reportAny=false, reportUnusedCallResult=false, reportPrivateUsage=false
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import evidence  # pyright: ignore[reportImplicitRelativeImport]
import pytest


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(path: Path, origin: str = "git@github.com:o/site.git") -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "remote", "add", "origin", origin)
    (path / "README.md").write_text("x\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-q", "-m", "docs(readme) start")
    return path


def test_zsh_continuation_lines_join_one_command() -> None:
    """A trailing backslash joins the next line into the same command."""
    text = ": 1:0;git commit -m 'a' \\\n  --amend\n: 2:0;ls\n"
    assert evidence.parse_zsh(text) == [(1, "git commit -m 'a' \\\n  --amend"), (2, "ls")]


def test_zsh_mixed_plain_and_extended_lines() -> None:
    """Plain and extended zsh lines parse in one file."""
    text = "plain one\n: 5:0;extended\nplain two\n"
    assert evidence.parse_zsh(text) == [(None, "plain one"), (5, "extended"), (None, "plain two")]


def test_zsh_metafied_bytes_decode_to_utf8() -> None:
    """Metafied non-ASCII bytes decode back to UTF-8."""
    encoded = "cd ~/wörk".encode()
    metafied = bytearray()
    for byte in encoded:
        if byte >= 0x83:
            metafied += bytes([0x83, byte ^ 0x20])
        else:
            metafied.append(byte)
    assert evidence.unmetafy(bytes(metafied)).decode() == "cd ~/wörk"


def test_attribution_matches_absolute_and_tilde_forms() -> None:
    """A repository path matches in both its absolute and its ~ form."""
    home = str(Path.home())
    entries: list[tuple[int | None, str]] = [
        (1, f"cd {home}/w/site && make"),
        (2, "make test"),
        (3, "cd -"),
        (4, "make test"),
        (5, "tmuxp load ~/w/site"),
    ]
    kept = [c for _, c in evidence.attribute(entries, ["~/w/site"])]
    assert kept == [f"cd {home}/w/site && make", "make test", "cd -", "tmuxp load ~/w/site"]


def test_unstamped_lines_in_a_stamped_history_do_not_inherit_the_directory() -> None:
    """Harness lines sharing the history file are not credited to the repository."""
    entries: list[tuple[int | None, str]] = [
        (1, "cd ~/w/site"),
        (None, "theirs=kept; trap 'x' EXIT"),
        (None, "cd /tmp/harness"),
        (2, "make test"),
        (None, "cat ~/w/site/README.md"),
    ]
    kept = [c for _, c in evidence.attribute(entries, ["~/w/site"])]
    assert kept == ["cd ~/w/site", "make test", "cat ~/w/site/README.md"]


def test_attribution_ignores_other_repositories_with_the_same_prefix() -> None:
    """A sibling checkout whose name extends the path is not attributed."""
    entries: list[tuple[int | None, str]] = [(1, "cd ~/w/site-old"), (2, "make")]
    assert evidence.attribute(entries, ["~/w/site"]) == []


def test_transcripts_keep_typed_prompts_and_drop_tool_output(tmp_path: Path) -> None:
    """Typed prompts survive; tool output and malformed lines do not."""
    home = str(Path.home())
    rows = [
        {
            "store": "claude.history",
            "text": "update packages",
            "timestamp": "2026-09-01T00:00:00Z",
            "agent": "claude",
            "session_id": "a",
            "origin": {"cwd": f"{home}/w/site/"},
        },
        {
            "store": "claude.projects",
            "text": "Shell cwd was reset to /x",
            "agent": "claude",
            "timestamp": "2026-09-02T00:00:00Z",
            "session_id": "a",
            "origin": {"cwd": f"{home}/w/site"},
        },
        {
            "store": "claude.projects",
            "text": "port that from the sibling repo",
            "agent": "claude",
            "timestamp": "2026-08-01T00:00:00Z",
            "session_id": "b",
            "metadata": {"project": f"{home}/w/old-site/"},
        },
        {"store": "claude.projects", "agent": "claude"},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows) + "\nnot json\n", encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10)

    assert report["records"] == 3
    assert report["by_cwd"] == [
        {
            "cwd": "~/w/site",
            "records": 2,
            "sessions": 1,
            "first": "2026-09-01",
            "last": "2026-09-02",
        },
        {
            "cwd": "~/w/old-site",
            "records": 1,
            "sessions": 1,
            "first": "2026-08-01",
            "last": "2026-08-01",
        },
    ]
    assert [p["text"] for p in report["prompts"]] == ["update packages"]
    assert report["history_agents"] == ["claude"]


def test_link_state_classifies_each_layout(tmp_path: Path) -> None:
    """Each .claude/skills layout gets its own state."""
    skills = tmp_path / ".claude" / "skills"
    assert evidence.link_state(skills) == ("absent", [])

    skills.mkdir(parents=True)
    (skills / "a").symlink_to("../../.agents/skills/a")
    assert evidence.link_state(skills) == ("per-skill-links", ["a"])

    (skills / "b").symlink_to("/elsewhere/b")
    assert evidence.link_state(skills) == ("foreign-links", ["b"])

    (skills / "c").mkdir()
    assert evidence.link_state(skills) == ("real-skills", ["c"])


@pytest.mark.integration(reason="executes native Git repository queries")
def test_git_summary_counts_direct_and_semi_linear_merges(tmp_path: Path) -> None:
    """Direct commits, merges, merge shape, and agent-file commits are counted."""
    repo = _repo(tmp_path / "site")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "lib").mkdir()
    (repo / "pkg" / "lib" / "a.py").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feat(lib) add a")
    _git(repo, "switch", "-q", "-c", "topic")
    (repo / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "ai(rules) add AGENTS.md")
    _git(repo, "switch", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "ai(rules) add AGENTS.md (#1)", "topic")

    report = evidence.cmd_git(repo, since="10 years ago", top_n=5)

    assert report["trunk"] == "main"
    assert report["commits"] == 3
    assert report["first_parent_direct"] == 2
    assert report["first_parent_merges"] == 1
    assert report["merges_semi_linear"] == 1
    assert report["merges_numbered"] == 1
    assert ("pkg/lib", 1) in report["hot_paths"]
    assert len(report["agent_file_commits"]) == 1


@pytest.mark.integration(reason="executes native Git repository queries")
def test_paths_finds_sibling_checkouts_of_the_same_origin(tmp_path: Path) -> None:
    """A sibling clone of the same origin is found; another origin is not."""
    repo = _repo(tmp_path / "work" / "site")
    _repo(tmp_path / "work" / "site-old", origin="https://github.com/O/site")
    _repo(tmp_path / "work" / "other", origin="git@github.com:o/other.git")

    report = evidence.cmd_paths(repo, [tmp_path / "work"])

    names = sorted(Path(p).name for p in report["checkouts"])
    assert names == ["site", "site-old"]
    assert report["cwd_globs"] == ["*site*"]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_replaces_per_skill_links_and_stages_one_link(tmp_path: Path) -> None:
    """Per-skill links become one staged directory link, idempotently."""
    repo = _repo(tmp_path / "site")
    (repo / ".agents" / "skills" / "a").mkdir(parents=True)
    (repo / ".agents" / "skills" / "a" / "SKILL.md").write_text("---\n", encoding="utf-8")
    links = repo / ".claude" / "skills"
    links.mkdir(parents=True)
    (links / "a").symlink_to("../../.agents/skills/a")
    _git(repo, "add", "--force", ".")
    _git(repo, "commit", "-q", "-m", "chore(skills) add a")

    assert evidence.cmd_link(repo, check=True)["changed"] is False
    report = evidence.cmd_link(repo, check=False)

    assert report == {"state": "per-skill-links", "entries": ["a"], "changed": True}
    assert str(links.readlink()) == "../.agents/skills"
    assert (links / "a" / "SKILL.md").is_file()
    staged = _git(repo, "diff", "--cached", "--name-status").split("\n")
    assert sorted(line for line in staged if line) == [
        "A\t.claude/skills",
        "D\t.claude/skills/a",
    ]
    assert evidence.cmd_link(repo, check=False)["changed"] is False


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_refuses_real_skill_directories(tmp_path: Path) -> None:
    """Real skill directories under .claude/skills stop the link untouched."""
    repo = _repo(tmp_path / "site")
    (repo / ".agents" / "skills").mkdir(parents=True)
    (repo / ".claude" / "skills" / "local").mkdir(parents=True)

    with pytest.raises(evidence.UsageError, match="real-skills"):
        evidence.cmd_link(repo, check=False)
    assert (repo / ".claude" / "skills" / "local").is_dir()


@pytest.mark.integration(reason="executes native Git repository queries")
def test_main_exits_2_outside_a_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Outside a repository the CLI exits 2 with a message."""
    assert evidence.main(["--repo", str(tmp_path), "git"]) == 2
    assert capsys.readouterr().err


def test_transcripts_keep_only_records_under_named_directories(tmp_path: Path) -> None:
    """Records outside the kept directories drop out of every count."""
    home = str(Path.home())
    rows = [
        {"store": "claude.history", "text": "a", "origin": {"cwd": f"{home}/w/cv"}},
        {"store": "claude.history", "text": "b", "origin": {"cwd": f"{home}/w/cv-panda"}},
        {"store": "claude.history", "text": "c", "origin": {"cwd": f"{home}/w/cv/pkg"}},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10, keep=["~/w/cv"])

    assert report["records"] == 2
    assert sorted(row["cwd"] for row in report["by_cwd"]) == ["~/w/cv", "~/w/cv/pkg"]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_check_reports_state_before_any_skill_exists(tmp_path: Path) -> None:
    """The precondition check works before commit 1 creates .agents/skills."""
    repo = _repo(tmp_path / "site")

    assert evidence.cmd_link(repo, check=True) == {
        "state": "absent",
        "entries": [],
        "changed": False,
    }
    with pytest.raises(evidence.UsageError, match="write the skills first"):
        evidence.cmd_link(repo, check=False)


def test_shell_heads_never_carry_a_secret(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Command heads are counted after redaction, like the recent samples."""
    history = tmp_path / "zsh_history"
    history.write_text(": 1:0;cd ~/w/site\n: 2:0;GH_TOKEN=ghp_SECRET123 gh pr list\n")
    monkeypatch.setattr(evidence, "_history_sources", lambda: [("zsh", history)])

    report = evidence.cmd_shell(["~/w/site"], top_n=10)

    assert "ghp_SECRET123" not in json.dumps(report)
    assert ("GH_TOKEN=… gh", 1) in report["sources"][0]["heads"]


def test_transcript_prompts_are_redacted(tmp_path: Path) -> None:
    """A credential typed into a prompt is masked before it reaches the report."""
    export = tmp_path / "export.ndjson"
    token = "ghp_" + "x" * 36
    record = {"store": "claude.history", "text": f"use {token} to push", "origin": {"cwd": "/w"}}
    export.write_text(json.dumps(record), encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10)

    assert token not in json.dumps(report)
    assert report["prompts"][0]["text"] == "use … to push"


@pytest.mark.integration(reason="executes native Git repository queries")
def test_git_summary_counts_squash_merged_pull_requests(tmp_path: Path) -> None:
    """Numbered direct commits show a squash or rebase flow, not direct pushes."""
    repo = _repo(tmp_path / "site")
    for number in (2, 3, 4):
        (repo / f"f{number}").write_text("x\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", f"feat(a) step {number} (#{number})")

    report = evidence.cmd_git(repo, since="10 years ago", top_n=5)

    assert report["first_parent_direct"] == 4
    assert report["direct_numbered"] == 3
    assert report["first_parent_merges"] == 0


@pytest.mark.integration(reason="executes native Git repository queries")
def test_trunk_is_main_when_origin_head_is_unset(tmp_path: Path) -> None:
    """On a topic branch with no origin/HEAD, history is still read from main."""
    repo = _repo(tmp_path / "site")
    _git(repo, "switch", "-q", "-c", "topic")
    (repo / "t").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "topic work")

    report = evidence.cmd_git(repo, since="10 years ago", top_n=5)

    assert report["trunk"] == "main"
    assert report["commits"] == 1


@pytest.mark.integration(reason="executes native Git repository queries")
def test_paths_from_a_worktree_name_the_primary_checkout(tmp_path: Path) -> None:
    """A worktree with a generated name reports the repository's own name."""
    repo = _repo(tmp_path / "work" / "site")
    worktree = tmp_path / "wt" / "esk"
    worktree.parent.mkdir()
    _git(repo, "worktree", "add", "-q", str(worktree), "-b", "x")

    report = evidence.cmd_paths(worktree, [])

    assert report["root_name"] == "site"
    assert report["cwd_globs"] == ["*site*", "*wt/esk*"]


def test_transcripts_report_a_bounded_scan(tmp_path: Path) -> None:
    """The summary trailer reaches the report, so a cut-short scan shows."""
    rows = [
        {"store": "claude.history", "text": "a", "origin": {"cwd": "/w"}},
        {
            "type": "summary",
            "data": {
                "status": {"state": "bounded", "reason": "result_limit"},
                "effort": {"requested": "exhaustive", "completed": "deep"},
                "coverage": {"sources_failed": 2, "sources_bounded": 1},
            },
        },
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10)

    assert report["scan"] == {
        "state": "bounded",
        "reason": "result_limit",
        "effort_requested": "exhaustive",
        "effort_completed": "deep",
        "sources_failed": 2,
        "sources_bounded": 1,
        "sources_skipped": 0,
    }
    assert report["records"] == 1


@pytest.mark.parametrize(
    ("entries", "kept"),
    [
        ([(1, 'cd "$HOME/w/site"'), (2, "make")], ['cd "$HOME/w/site"', "make"]),
        (
            [(1, "cd ~/w/site"), (2, 'cd "$HOME/other"'), (3, "make")],
            ["cd ~/w/site", 'cd "$HOME/other"'],
        ),
        ([(1, "cd ~/w/site"), (2, "cd $OTHER"), (3, "ls")], ["cd ~/w/site", "cd $OTHER"]),
        (
            [(1, "cd ~/w/site"), (2, 'cd "$(mktemp -d)"'), (3, "ls")],
            ["cd ~/w/site", 'cd "$(mktemp -d)"'],
        ),
        ([(1, "cd ~/w/site"), (2, "cd -- /tmp"), (3, "ls")], ["cd ~/w/site", "cd -- /tmp"]),
        (
            [(1, "cd ~/w/site"), (2, "make test; cd /tmp"), (3, "ls")],
            ["cd ~/w/site", "make test; cd /tmp"],
        ),
        ([(1, "cd ~/w/site/.."), (2, "make")], ["cd ~/w/site/.."]),
        ([(1, "cd ~/w"), (2, "cd 'site'"), (3, "make")], ["cd 'site'", "make"]),
    ],
)
def test_cd_tracking_reads_quotes_home_and_parents(
    entries: list[tuple[int | None, str]], kept: list[str]
) -> None:
    """Quoted, $HOME, and .. targets move the tracked directory correctly."""
    assert [c for _, c in evidence.attribute(entries, ["~/w/site"])] == kept


def test_agents_without_history_fall_back_to_screened_conversations(tmp_path: Path) -> None:
    """Conversation prompts count only for an agent that has no history store."""
    rows = [
        {"agent": "claude", "store": "claude.history", "text": "typed", "timestamp": "2026-01-02"},
        {"agent": "claude", "store": "claude.projects", "text": "OK vitest 5"},
        {"agent": "cursor", "store": "cursor.state", "text": "1. fix the bug"},
        {"agent": "cursor", "store": "cursor.state", "text": "--- branch --- main"},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10)

    assert sorted(p["text"] for p in report["prompts"]) == ["1. fix the bug", "typed"]
    assert evidence.cmd_transcripts(export, limit=0)["prompts"] == []


def test_duplicate_prompts_keep_their_earliest_timestamp(tmp_path: Path) -> None:
    """The earliest dated copy wins, and an undated copy never replaces a dated one."""
    rows = [
        {"agent": "a", "store": "a.history", "text": "same", "timestamp": "2026-09-01T10:00:00Z"},
        {"agent": "a", "store": "a.history", "text": "same", "timestamp": "2026-09-01T09:00:00Z"},
        {"agent": "a", "store": "a.history", "text": "same"},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    report = evidence.cmd_transcripts(export, limit=10)

    assert [p["date"] for p in report["prompts"]] == ["2026-09-01"]
    assert report["prompts_total"] == 1


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_stages_an_existing_untracked_link(tmp_path: Path) -> None:
    """A link already on disk but not in git is staged, then reported unchanged."""
    repo = _repo(tmp_path / "site")
    (repo / ".agents" / "skills" / "a").mkdir(parents=True)
    (repo / ".agents" / "skills" / "a" / "SKILL.md").write_text("---\n", encoding="utf-8")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "skills").symlink_to("../.agents/skills")

    assert evidence.cmd_link(repo, check=False)["changed"] is True
    assert _git(repo, "diff", "--cached", "--name-only").split() == [".claude/skills"]
    _git(repo, "commit", "-q", "-m", "link")
    assert evidence.cmd_link(repo, check=False)["changed"] is False


def test_main_exits_2_on_a_missing_export(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file the command cannot read is a usage error, not a traceback."""
    assert evidence.main(["transcripts", str(tmp_path / "missing.ndjson")]) == 2
    assert "missing.ndjson" in capsys.readouterr().err


def test_unreadable_history_is_listed_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable history file is named while the rest are still read."""
    locked = tmp_path / "locked_history"
    locked.write_text("ls\n")
    locked.chmod(0)
    readable = tmp_path / "bash_history"
    readable.write_text("cd ~/w/site\n")
    sources = [("zsh", locked), ("bash", readable)]
    monkeypatch.setattr(evidence, "_history_sources", lambda: sources)
    if os.access(locked, os.R_OK):
        pytest.skip("running with permission to read any file")

    report = evidence.cmd_shell(["~/w/site"], top_n=5)

    assert report["unreadable"] == [evidence.tilde(str(locked))]
    assert [s["shell"] for s in report["sources"]] == ["bash"]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_paths_skips_an_unreadable_sibling(tmp_path: Path) -> None:
    """A sibling directory the user cannot enter does not stop the scan."""
    repo = _repo(tmp_path / "work" / "site")
    locked = tmp_path / "work" / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        report = evidence.cmd_paths(repo, [tmp_path / "work"])
    finally:
        locked.chmod(0o755)

    assert report["root_name"] == "site"


def test_a_lone_surrogate_does_not_sink_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A truncated emoji in a prompt is replaced, and the report still prints."""
    export = tmp_path / "export.ndjson"
    export.write_text(
        '{"store": "a.history", "text": "cut \\ud83d here", "origin": {"cwd": "/w"}}',
        encoding="utf-8",
    )

    assert evidence.main(["transcripts", str(export)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["prompts"][0]["text"] == "cut ? here"


@pytest.mark.integration(reason="executes native Git repository queries")
def test_link_after_moving_real_skills_into_agents(tmp_path: Path) -> None:
    """Once real skill directories move to .agents/skills, the link replaces the rest."""
    repo = _repo(tmp_path / "site")
    local = repo / ".claude" / "skills" / "local"
    local.mkdir(parents=True)
    (local / "SKILL.md").write_text("---\n", encoding="utf-8")
    (repo / ".agents" / "skills").mkdir(parents=True)
    _git(repo, "add", "--force", ".claude")
    _git(repo, "commit", "-q", "-m", "local skill")
    with pytest.raises(evidence.UsageError, match="real-skills"):
        evidence.cmd_link(repo, check=True)

    _git(repo, "mv", ".claude/skills/local", ".agents/skills/local")
    report = evidence.cmd_link(repo, check=False)

    assert report["changed"] is True
    assert (repo / ".claude" / "skills" / "local" / "SKILL.md").is_file()


def test_shell_reads_a_named_history_file_and_infers_its_shell(tmp_path: Path) -> None:
    """A history kept outside the defaults is read with the right parser."""
    saved = tmp_path / "saved.txt"
    saved.write_text(
        "- cmd: cd ~/w/site\n  when: 5\n- cmd: make test\n  when: 6\n", encoding="utf-8"
    )

    report = evidence.cmd_shell(["~/w/site"], top_n=5, histories=[saved])

    source = report["sources"][0]
    assert (source["shell"], source["file"], source["attributed"]) == (
        "fish",
        evidence.tilde(str(saved)),
        2,
    )


@pytest.mark.integration(reason="executes native Git repository queries")
def test_a_staged_but_uncommitted_link_still_needs_commit_2(tmp_path: Path) -> None:
    """Only a link in HEAD counts as committed; a staged one still reports a change."""
    repo = _repo(tmp_path / "site")
    (repo / ".agents" / "skills" / "a").mkdir(parents=True)
    (repo / ".agents" / "skills" / "a" / "SKILL.md").write_text("---\n", encoding="utf-8")
    _git(repo, "add", ".agents")
    _git(repo, "commit", "-q", "-m", "skills")

    assert evidence.cmd_link(repo, check=False)["changed"] is True
    assert evidence.cmd_link(repo, check=False)["changed"] is True
    _git(repo, "commit", "-q", "-m", "link")
    assert evidence.cmd_link(repo, check=False)["changed"] is False


def test_prompts_sharing_a_long_opening_stay_distinct(tmp_path: Path) -> None:
    """Deduplication compares whole prompts, so templated requests keep their variants."""
    opening = "update the dependency " + "a" * 90
    rows = [
        {"agent": "a", "store": "a.history", "text": f"{opening} requests", "timestamp": "2026-01"},
        {"agent": "a", "store": "a.history", "text": f"{opening} django", "timestamp": "2026-02"},
        {"agent": "a", "store": "a.history", "text": f"{opening}  django", "timestamp": "2026-03"},
    ]
    export = tmp_path / "export.ndjson"
    export.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    assert evidence.cmd_transcripts(export, limit=10)["prompts_total"] == 2


@pytest.mark.integration(reason="executes native Git repository queries")
def test_agent_file_commits_include_nested_files(tmp_path: Path) -> None:
    """A commit touching only a nested AGENTS.md counts as an agent-file commit."""
    repo = _repo(tmp_path / "site")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "AGENTS.md").write_text("rules\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "ai(rules[pkg]) add nested rules")

    report = evidence.cmd_git(repo, since="10 years ago", top_n=5)

    assert [line.split(" ", 1)[1] for line in report["agent_file_commits"]] == [
        "ai(rules[pkg]) add nested rules"
    ]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_session_dirs_separate_own_from_lookalikes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout's own session directory is told apart from same-suffix ones."""
    repo = _repo(tmp_path / "w" / "site")
    worktree = tmp_path / "w" / "site-oxc"
    _git(repo, "worktree", "add", "-q", str(worktree), "-b", "oxc")
    home = tmp_path / "home"
    projects = home / ".claude" / "projects"
    own = sorted(evidence.encode_session_dir(str(p)) for p in (repo, worktree))
    for name in (*own, "-x-my-site", "-x-site", "-x-other"):
        (projects / name).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    report = evidence.cmd_paths(repo, [])

    assert report["session_dirs"] == own
    assert report["other_session_dirs"] == ["-x-my-site", "-x-site"]


@pytest.mark.integration(reason="executes native Git repository queries")
def test_a_stale_origin_head_falls_through_to_main(tmp_path: Path) -> None:
    """An origin/HEAD naming a deleted branch is skipped, not passed to git log."""
    repo = _repo(tmp_path / "site")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")

    assert evidence.cmd_git(repo, since="10 years ago", top_n=5)["trunk"] == "main"


@pytest.mark.integration(reason="executes native Git repository queries")
def test_hot_paths_keep_non_ascii_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Paths git would quote under its default config are bucketed by their real names."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    repo = _repo(tmp_path / "site")
    (repo / "wörk" / "sub").mkdir(parents=True)
    (repo / "wörk" / "sub" / "a.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add")

    report = evidence.cmd_git(repo, since="10 years ago", top_n=5)

    assert ["wörk/sub", 1] in [list(row) for row in report["hot_paths"]]


def test_merge_shape_counts_share_one_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Semi-linear and numbered merges are counted over the same checked merges."""
    log = "".join(f"a{i} b{i}\x00feat(x) n{i} (#{i})\n" for i in range(3))

    def fake_git(_repo: Path, *args: str, check: bool = True) -> str:
        del check
        if args[:2] == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        if args[:2] == ("symbolic-ref", "--quiet"):
            return "refs/remotes/origin/main"
        if args[:2] == ("rev-parse", "--verify"):
            return "x"
        if "--first-parent" in args:
            return log
        if args[0] == "merge-base":
            return args[1]
        return ""

    monkeypatch.setattr(evidence, "_git", fake_git)
    monkeypatch.setattr(evidence, "_MERGES_CHECKED", 2)

    report = evidence.cmd_git(tmp_path, since="1 year ago", top_n=5)

    assert (report["first_parent_merges"], report["merges_checked"]) == (3, 2)
    assert (report["merges_semi_linear"], report["merges_numbered"]) == (2, 2)


_TOKEN = "ghp_" + "c" * 36


@pytest.mark.parametrize(
    ("command", "secret"),
    [
        ("sshpass -p hunter2 ssh h", "hunter2"),
        ("curl -H 'X-Api-Key: abc123def456' u", "abc123def456"),
        ("curl -H 'Authorization: ApiKey abc123xyz' u", "abc123xyz"),
        ("redis-cli -a hunter2 ping", "hunter2"),
        ("echo 'password: hunter2'", "hunter2"),
        ("curl -u admin:hunter2 https://x", "hunter2"),
        ("mysql -uroot -phunter2 db", "hunter2"),
        ("SECRET_KEY = abc987", "abc987"),
        ('export TOKEN="abc def"', "abc def"),
        (f"GH_TOKEN={_TOKEN} gh pr list", _TOKEN),
        (f"gh auth --token {_TOKEN}", _TOKEN),
        ("psql postgres://u:pw987@host/db", "pw987"),
        ("export AWS_SECRET_ACCESS_KEY=abcd1234", "abcd1234"),
        (f"git clone https://{_TOKEN}@github.com/x/y", _TOKEN),
        ('curl -H "X-API-Key: abc123" x', "abc123"),
        ('curl -H "X-Auth-Token: abc123" x', "abc123"),
        ('curl -H "PRIVATE-TOKEN: abcdef" x', "abcdef"),
        ('curl -H "Authorization: abc123" x', "abc123"),
        ("docker login -u bob -p hunter2 reg", "hunter2"),
        ("az login -p pw12345", "pw12345"),
        ("REDIS_URL=redis://:hunter2@h:6379", "hunter2"),
        ("wget --http-password=abc123", "abc123"),
        ("aws --secret-access-key abc123", "abc123"),
        ("curl --oauth2-bearer abc123", "abc123"),
        ("curl -u bob:'p w' x", "p w"),
        ("pay " + "sk_" + "live_" + "Q1" * 12, "Q1" * 12),
        ("npm config set npm_" + "d" * 36, "d" * 36),
    ],
)
def test_redact_masks_each_credential_form(command: str, secret: str) -> None:
    """Every credential form in the corpus is masked."""
    assert secret not in evidence.redact_command(command)


@pytest.mark.parametrize(
    "command",
    [
        "docker run --rm -u 1000:1000 img",
        "llm --max-tokens=5 prompt",
        "TOKENIZER=bert make",
        "git switch feat/sk-implement-the-feature-xyzxyz",
        "curl 'https://x/?page=2'",
        "pnpm --filter @tony/nl-react run test",
        "git commit -m 'fix the parser'",
        "mkdir -p out/dir",
        "uv run pytest -q -k token",
        "make PASS=1",
        "cache_key = compute()",
        "python -c 'print(dict(key=1))'",
        "docker run -u node:node img",
        "docker run -p 8080:80 img",
        "sudo -u deploy:deploy ls",
        "tar -u foo:bar",
        "curl http://localhost:3000?x=a@b",
        "git log --grep='key: value'",
        "git commit -m 'fix(auth): rotate the token: 24h expiry'",
        "git clone ssh://git@github.com/o/r",
        "gh auth login --with-token < token.txt",
    ],
)
def test_redact_leaves_ordinary_commands_alone(command: str) -> None:
    """Commands that only look like credentials come back unchanged."""
    assert evidence.redact_command(command) == command


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        (f"use {_TOKEN} to push", _TOKEN),
        ("-----BEGIN RSA PRIVATE KEY-----\nMIIEabc123\n", "MIIEabc123"),
        ("the password: hunter2 expired", "hunter2"),
        ("db at postgres://u:pw987@h/db", "pw987"),
        ("my API key = abc123def", "abc123def"),
    ],
)
def test_redact_text_masks_credentials_in_prose(text: str, secret: str) -> None:
    """Credentials pasted into a prompt are masked."""
    assert secret not in evidence.redact_text(text)


@pytest.mark.parametrize(
    "text",
    [
        "all 12 tests pass: yes, rerun",
        "fix(auth): rotate the token: 24h expiry",
        "the cache key: value pairs are stale",
        "PASS=1 should be the default",
        "why does the token count differ?",
    ],
)
def test_redact_text_leaves_prose_alone(text: str) -> None:
    """Prose that mentions tokens, passes, or keys comes back unchanged."""
    assert evidence.redact_text(text) == text
